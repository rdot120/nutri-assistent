"""
Orquestrador de automacao nutricional.
Coordena: busca TBCA -> matching -> preenchimento -> salvamento.
"""
import time
import logging
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

from config.settings import Settings, DATA_DIR
from browser.session import SessionManager
from browser.platform import PlatformInteraction
from storage.db import Database
from nutrition.tbca import TBCAScraper, TBCAFood, TBCA_TO_PLATFORM
from nutrition.matcher import FoodMatcher, MatchResult
from nutrition.usda import USDAScraper, USDA_TO_PLATFORM
from nutrition.openfoodfacts import OpenFoodFactsSource
from nutrition.sanity import validate_fields, to_float, sanity_score
from nutrition.ai_provider import NutritionAIFinder, VerificationResult, create_default_finder

logger = logging.getLogger(__name__)

CACHE_DB = DATA_DIR / "tbca_cache.db"


@dataclass
class ProcessedFood:
    """Resultado do processamento de um alimento."""
    platform_name: str
    match: Optional[MatchResult] = None
    fields_to_fill: dict = None
    status: str = "pending"  # pending, matched, filled, saved, error, skipped
    skip_reason: str = ""  # filled, reviewed
    suggestion: str = ""  # Sugestao de correcao
    error: str = ""
    verification: Optional[VerificationResult] = None

    def __post_init__(self):
        if self.fields_to_fill is None:
            self.fields_to_fill = {}


class Orchestrator:
    """Coordena o fluxo completo de automacao."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(DATA_DIR / "nutri_auto.db")
        self.tbca = TBCAScraper(cache_db_path=CACHE_DB)
        self.matcher = FoodMatcher(
            high_threshold=settings.matching.high_confidence,
            medium_threshold=settings.matching.medium_confidence,
        )
        self.ai_finder = create_default_finder(settings)
        self.usda = USDAScraper(
            api_key=settings.usda.api_key,
            cache_db_path=DATA_DIR / "usda_cache.db"
        )
        self.session: Optional[SessionManager] = None
        self.platform: Optional[PlatformInteraction] = None

    def start_browser(self, headless: bool = None):
        """Inicia o navegador e faz login."""
        if headless is None:
            headless = self.settings.platform.headless

        self.session = SessionManager(
            user_data_dir=self.settings.platform.user_data_dir,
            headless=headless,
            slow_mo=self.settings.platform.slow_mo,
            timeout=self.settings.platform.timeout,
        )
        self.session.start()

        success = self.session.login(
            login_url=self.settings.platform.login_url,
            username=self.settings.platform.username,
            password=self.settings.platform.password,
        )
        if not success:
            raise RuntimeError("Falha no login da plataforma")

        self.session.navigate(self.settings.platform.nutri_url)
        time.sleep(3)
        self.platform = PlatformInteraction(self.session.page)
        logger.info("Navegador iniciado e logado")

    def stop_browser(self):
        """Para o navegador."""
        if self.session:
            self.session.stop()
            self.session = None
            self.platform = None

    def step1_collect_platform_foods(self) -> list[dict]:
        """Fase 1: Coleta nomes de todos os nutricionais da plataforma."""
        logger.info("Fase 1: Coletando nutricionais da plataforma")
        if not self.platform:
            raise RuntimeError("Navegador nao iniciado")

        self.platform.navigate_to_nutri(self.settings.platform.nutri_url)
        foods = self.platform.get_all_foods_with_status()
        logger.info(f"Coletados {len(foods)} nutricionais da plataforma")
        return foods

    def step1b_mark_prefilled(self, platform_foods: list[dict]) -> dict:
        """
        Fase 1b: Le os filtros da barra lateral da plataforma e marca
        itens ja concluidos (salvos/conferidos) ANTES do matching.

        Formula: pendentes = total - (associados + checados)
          - "Associado(s)"      = salvos, 100% concluidos (verde)
          - "Checado por nutricionista" = conferidos, nao salvos (azul)
        """
        logger.info("Fase 1b: Lendo filtros da barra lateral")
        sets = self.platform.capture_filter_sets()
        counts = sets["counts"]
        names = sets["names"]

        saved = set(names.get("associados", []))
        checked = set(names.get("checados", []))
        total = counts.get("total", len(names.get("total", [])))

        # Formula usa os contadores exibidos na barra lateral
        pendentes = total - (
            counts.get("associados", len(saved))
            + counts.get("checados", len(checked))
        )

        self.prefilled_tags = {}
        for food in platform_foods:
            name = food["name"]
            if name in saved:
                food["prefilled"] = "salvo"
                self.prefilled_tags[name] = "salvo"
            elif name in checked:
                food["prefilled"] = "conferido"
                self.prefilled_tags[name] = "conferido"

        marked = len(self.prefilled_tags)
        logger.info(
            f"Fase 1b: {total} totais - ({len(saved)} salvos + "
            f"{len(checked)} conferidos) = {pendentes} pendentes; "
            f"{marked} marcados por nome"
        )
        return {
            "counts": counts,
            "pendentes": pendentes,
            "marked": marked,
        }

    def apply_prefilled_to_processed(
        self, processed: list[ProcessedFood]
    ) -> list[ProcessedFood]:
        """Aplica as marcacoes da fase 1b a lista processada."""
        tags = getattr(self, "prefilled_tags", {}) or {}
        if not tags:
            return processed

        for pf in processed:
            kind = tags.get(pf.platform_name)
            if not kind or pf.status in ("filled", "saved"):
                continue
            pf.status = "skipped"
            pf.skip_reason = f"prefilled_{kind}"
            pf.suggestion = (
                "Ja salvo na plataforma" if kind == "salvo"
                else "Ja conferido pela nutricionista"
            )

        return processed

    def step2_build_tbca_index(self, search_terms: list[str] = None):
        """Fase 2: Constroi indice TBCA (busca listing ou usa cache)."""
        logger.info("Fase 2: Construindo indice TBCA")

        # Prioridade 1: listing index (2835+ alimentos, sem nutrientes detalhados)
        listing_index = self.tbca.load_listing_index()
        if listing_index:
            logger.info(f"Carregados {len(listing_index)} alimentos do listing index")
            self.matcher.load_tbca_index(listing_index)
            return listing_index

        # Prioridade 2: cache detalhado (nutrientes completos)
        cached_foods = self._load_all_cached_foods()
        if cached_foods:
            logger.info(f"Carregados {len(cached_foods)} alimentos do cache detalhado")
            self.matcher.load_tbca_index(cached_foods)
            return cached_foods

        # Prioridade 3: buscar por termos (lento)
        if not search_terms:
            logger.warning("Nenhum termo de busca e cache vazio")
            return []

        all_foods = []
        for term in search_terms:
            foods = self.tbca.search_and_fetch(term, max_results=5)
            for food in foods:
                self.tbca.to_cache(food)
                all_foods.append(food)
            time.sleep(1)

        self.matcher.load_tbca_index(all_foods)
        logger.info(f"Indice TBCA: {len(all_foods)} alimentos")
        return all_foods

    def step3_match_foods(self, platform_foods: list[dict],
                          gui_callback=None, on_item=None) -> list[ProcessedFood]:
        """Fase 3: Encontra correspondencias platform <-> TBCA (rapido, sem web requests)."""
        logger.info("Fase 3: Buscando correspondencias")

        platform_names = [f["name"] for f in platform_foods]
        matches = self.matcher.match_all(platform_names)

        processed = []
        no_match_foods = []

        for food in platform_foods:
            name = food["name"]

            if food.get("prefilled"):
                pf = ProcessedFood(platform_name=name)
                pf.status = "skipped"
                pf.skip_reason = f"prefilled_{food['prefilled']}"
                pf.suggestion = (
                    "Ja salvo na plataforma" if food["prefilled"] == "salvo"
                    else "Ja conferido pela nutricionista"
                )
                processed.append(pf)
                if on_item:
                    on_item(pf)
                continue

            match = matches.get(name)
            pf = ProcessedFood(platform_name=name, match=match)
            if match:
                pf.status = "matched"
                if on_item:
                    on_item(pf)
            else:
                pf.status = "no_match"
                no_match_foods.append(pf)
            processed.append(pf)

        matched_count = sum(1 for p in processed if p.status == "matched")
        logger.info(f"Correspondencias TBCA: {matched_count}/{len(processed)}")

        # Fase 3b2: Rotulos reais do Open Food Facts (produtos industrializados)
        still_unmatched = [p for p in processed if p.status == "no_match"]
        if still_unmatched:
            logger.info(f"Fase 3b2: Buscando rotulos OF para "
                        f"{len(still_unmatched)} alimentos")
            self._openfoodfacts_fallback(still_unmatched,
                                         gui_callback=gui_callback,
                                         on_item=on_item)

        # Fase 3c: Buscar via USDA para alimentos sem match TBCA/OF
        still_unmatched = [p for p in processed if p.status == "no_match"]
        if still_unmatched and self.settings.usda.api_key:
            logger.info(f"Fase 3c: Buscando via USDA para {len(still_unmatched)} alimentos")
            self._usda_fallback(still_unmatched, gui_callback=gui_callback,
                                on_item=on_item)

        # Fase 3d: Buscar via IA para alimentos sem match anterior
        still_unmatched = [p for p in processed if p.status == "no_match"]
        if self.ai_finder and self.settings.ai.auto_fallback and still_unmatched:
            logger.info(f"Fase 3d: Buscando via IA para {len(still_unmatched)} alimentos")
            self._ai_fallback(still_unmatched, gui_callback=gui_callback,
                              on_item=on_item)
            # Itens que ficaram sem match tambem sao exibidos
            if on_item:
                for p in [p for p in processed if p.status == "no_match"]:
                    on_item(p)

        # Fase 3e: Verificar matches suspeitos via IA
        matched_foods = [p for p in processed if p.status == "matched" and p.match]
        if self.ai_finder and matched_foods:
            logger.info(f"Fase 3e: Verificando {len(matched_foods)} matches via IA")
            self._verify_matches(matched_foods, gui_callback=gui_callback)

        # Fase 3f: Autoconsistencia - revalidar itens de IA com confianca baixa
        if self.ai_finder:
            suspicious = [
                p for p in processed
                if p.status == "matched" and p.match
                and (p.match.match_method or "").startswith("ai_")
                and p.match.confidence < 68
            ]
            if suspicious:
                logger.info(f"Fase 3f: Autoconsistencia em {len(suspicious)} "
                            f"itens de IA com baixa confianca")
                self._self_check_suspicious(suspicious, gui_callback=gui_callback)

        return processed

    def _ensure_nutrients(self, pf: ProcessedFood) -> bool:
        """Garante que um ProcessedFood tem campos preenchidos (busca nutrientes se necessario)."""
        if pf.fields_to_fill:
            return True
        if not pf.match:
            return False

        if pf.match.match_method == "usda":
            return False

        if not pf.match.tbca_nutrients:
            self._fetch_and_enrich_nutrients(pf.match)
        if pf.match.tbca_nutrients:
            pf.fields_to_fill = self._map_to_platform_fields(pf.match)
            return bool(pf.fields_to_fill)
        return False

    def _usda_fallback(self, no_match_foods: list[ProcessedFood],
                       gui_callback=None, on_item=None):
        """Busca dados nutricionais via USDA para alimentos sem match TBCA."""
        if not self.settings.usda.api_key:
            if gui_callback:
                gui_callback("  USDA: chave API nao configurada")
            return

        logger.info(f"USDA: buscando {len(no_match_foods)} alimentos sem match TBCA")
        if gui_callback:
            gui_callback(f"  USDA: consultando {len(no_match_foods)} alimentos...")

        usda_count = 0
        from rapidfuzz import fuzz

        for i, pf in enumerate(no_match_foods):
            try:
                if gui_callback and (i + 1) % 5 == 0:
                    gui_callback(f"  USDA: {i+1}/{len(no_match_foods)} consultados, {usda_count} encontrados")

                query = pf.platform_name.split(",")[0].strip()
                results = self.usda.search(query, page_size=5)
                if not results:
                    continue

                best_match = None
                best_score = 0

                for r in results:
                    desc = r.get("description", "").lower()
                    platform_norm = pf.platform_name.lower().split(",")[0].strip()
                    score = fuzz.token_set_ratio(platform_norm, desc)
                    if score > best_score:
                        best_score = score
                        best_match = r

                if best_match and best_score >= 65:
                    food_detail = self.usda.get_food(best_match["fdc_id"])
                    if food_detail and food_detail.nutrients:
                        fields = self.usda.to_platform_fields(food_detail)
                        if fields:
                            pf.match = MatchResult(
                                platform_name=pf.platform_name,
                                tbca_name=f"[USDA] {food_detail.description[:50]}",
                                tbca_code=f"USDA-{food_detail.fdc_id}",
                                confidence=best_score,
                                match_method="usda",
                                tbca_nutrients={},
                            )
                            pf.fields_to_fill = fields
                            pf.status = "matched"
                            usda_count += 1

                            logger.info(
                                f"  USDA: {pf.platform_name} -> "
                                f"{food_detail.description[:40]} "
                                f"({best_score:.0f}%, {len(fields)} campos)"
                            )

                            self.db.log_operation(
                                food_name=pf.platform_name,
                                food_code=f"USDA-{food_detail.fdc_id}",
                                operation="usda_lookup",
                                status="success",
                                details=f'{{"score": {best_score}, '
                                        f'"fields": {len(fields)}}}',
                            )
                        else:
                            logger.debug(
                                f"  USDA: {pf.platform_name} -> "
                                f"{best_match['description'][:40]} "
                                f"sem campos validos"
                            )
                    else:
                        logger.debug(
                            f"  USDA: {pf.platform_name} -> "
                            f"sem detalhes nutricionais"
                        )
                else:
                    logger.debug(
                        f"  USDA: {pf.platform_name} sem match "
                        f"(melhor: {best_score:.0f}%)"
                    )

                time.sleep(0.3)

            except Exception as e:
                logger.warning(f"  USDA erro para {pf.platform_name}: {e}")

            if on_item:
                on_item(pf)

        logger.info(f"USDA: {usda_count}/{len(no_match_foods)} alimentos encontrados")
        if gui_callback:
            gui_callback(f"  USDA: {usda_count}/{len(no_match_foods)} alimentos encontrados")

    def step3b_check_card_status(self, processed_foods: list[ProcessedFood]) -> list[ProcessedFood]:
        """
        Fase 3b: Verifica status dos cards na plataforma usando dados do listing.
        Detecta 'conferido' e 'preenchido' pelo conteudo do card (sem abrir dialog).
        """
        if not self.platform:
            return processed_foods

        logger.info("Fase 3b: Verificando status dos cards")

        # Ler status de todos os cards de uma vez (rápido, sem abrir dialog)
        all_foods = self.platform.get_all_foods_with_status()

        # Indexar por nome
        status_map = {}
        for f in all_foods:
            status_map[f["name"]] = f

        for pf in processed_foods:
            if pf.status != "matched":
                continue

            card_info = status_map.get(pf.platform_name)

            if not card_info:
                # Card nao encontrado no listing (pode ter sido removido)
                logger.debug(f"  Card nao encontrado no listing: {pf.platform_name}")
                continue

            # Verificar se marcado como conferido
            if card_info.get("reviewed"):
                pf.status = "skipped"
                pf.skip_reason = "reviewed"
                pf.suggestion = "Marcado como conferido pela nutricionista"
                logger.info(f"  SKIP (conferido): {pf.platform_name}")
                continue

            # Verificar se tem badge de preenchido
            if card_info.get("hasFilledBadge"):
                pf.status = "skipped"
                pf.skip_reason = "already_filled"
                pf.suggestion = f"Ja preenchido ({card_info.get('filledText', 'com dados')})"
                logger.info(f"  SKIP (preenchido): {pf.platform_name}")
                continue

            # Card vazio e nao conferido - pode preencher
            logger.debug(f"  OK (vazio): {pf.platform_name}")

        skipped = sum(1 for p in processed_foods if p.status == "skipped")
        logger.info(
            f"Fase 3b concluida: {skipped} cards ignorados"
        )

        return processed_foods

    def _fetch_and_enrich_nutrients(self, match: MatchResult):
        """Busca nutrientes detalhados do TBCA para um match que so tem listing data."""
        # Primeiro tentar cache detalhado
        cached = self.tbca.from_cache(match.tbca_code)
        if cached and cached.nutrients:
            match.tbca_nutrients = cached.nutrients
            return

        # Buscar URL do listing index
        listing = self.tbca.load_listing_index()
        url = None
        for item in listing:
            if item["code"] == match.tbca_code:
                url = item.get("url", "")
                break

        if not url:
            logger.warning(f"URL nao encontrada para {match.tbca_code}")
            return

        # Buscar detalhes
        logger.info(f"Buscando detalhes: {match.tbca_code} ({match.tbca_name[:40]})")
        food = self.tbca.fetch_food(url)
        if food and food.nutrients:
            match.tbca_nutrients = food.nutrients
            self.tbca.to_cache(food)
            logger.info(f"  {len(food.nutrients)} nutrientes carregados")

    # Confianca base por fonte (0-100)
    _SOURCE_BASE = {
        "tbca": 95,
        "off": 85,
        "usda": 80,
    }
    _AI_BASE = {"receita": 70, "tabela": 52}

    def _openfoodfacts_fallback(self, no_match_foods: list[ProcessedFood],
                                gui_callback=None, on_item=None):
        """Busca rotulos reais no Open Food Facts (produtos industrializados)."""
        if not hasattr(self, "_off_source"):
            self._off_source = OpenFoodFactsSource()

        names = [pf.platform_name for pf in no_match_foods]
        if gui_callback:
            gui_callback(f"  Rotulos OF: consultando {len(names)} produtos...")

        results = self._off_source.search_batch(names, gui_callback=gui_callback)

        off_count = 0
        for pf in no_match_foods:
            res = results.get(pf.platform_name.lower().strip())
            if res:
                fields = res["fields"]
                completeness = min(1.0, len(fields) / 20.0)
                conf = (self._SOURCE_BASE["off"]
                        - 15.0 * (1.0 - sanity_score(fields))
                        ) * (0.75 + 0.25 * completeness) \
                    * (res["score"] / 100.0)
                label = res["product_name"]
                if res.get("brands"):
                    label = f"{label} ({res['brands'][:24]})"
                pf.match = MatchResult(
                    platform_name=pf.platform_name,
                    tbca_name=f"[OF] {label}",
                    tbca_code="OFF",
                    confidence=round(min(conf, 92.0), 1),
                    match_method="off",
                    tbca_nutrients={},
                )
                pf.fields_to_fill = fields
                pf.status = "matched"
                off_count += 1
                logger.info(
                    f"  OF: {pf.platform_name} -> {res['product_name']} "
                    f"({pf.match.confidence:.0f}%, {len(fields)} campos)"
                )
            if on_item:
                on_item(pf)

        logger.info(f"OF: {off_count}/{len(no_match_foods)} com rotulo util")
        if gui_callback:
            gui_callback(f"  Rotulos OF: {off_count}/{len(no_match_foods)} encontrados")

    def _sanity_check_fields(self, fields: dict):
        """Retorna (score 0-1, issues)."""
        return validate_fields(fields or {})

    def _self_check_suspicious(self, foods: list[ProcessedFood],
                               gui_callback=None):
        """Fase 3f: reconsulta itens de IA duvidosos e compara respostas.

        Convergencia (<25% de desvio nos macros) sobe a confianca;
        divergencia forte (>45%) manda para revisao.
        """
        sample = foods[:40]
        names = [pf.platform_name for pf in sample]
        if gui_callback:
            gui_callback(f"  Autoconsistencia: revalidando {len(sample)} itens...")

        results = self.ai_finder.find_batch(
            names, batch_size=8, gui_callback=gui_callback
        )

        boosted = demoted = 0
        for pf in sample:
            res2 = results.get(pf.platform_name.lower().strip())
            if not (res2 and res2.success and res2.fields):
                continue

            dev = self._macro_deviation(pf.fields_to_fill, res2.fields)
            if dev is None:
                continue

            if dev <= 0.25:
                pf.match.confidence = min(88.0, pf.match.confidence + 15.0)
                boosted += 1
                logger.info(f"  Autocheck OK ({dev*100:.0f}%): "
                            f"{pf.platform_name} -> conf "
                            f"{pf.match.confidence:.0f}%")
            elif dev >= 0.45:
                pf.match.confidence = max(10.0, pf.match.confidence - 15.0)
                pf.status = "review_needed"
                pf.suggestion = (f"IA divergiu {dev*100:.0f}% na "
                                 f"revalidacao - revisar valores")
                demoted += 1
                logger.warning(f"  Autocheck DIVERGENTE ({dev*100:.0f}%): "
                               f"{pf.platform_name}")
            else:
                pf.match.confidence = max(10.0, pf.match.confidence - 5.0)

        logger.info(f"Autoconsistencia: +{boosted} confirmados, "
                    f"{demoted} para revisao")
        if gui_callback:
            gui_callback(f"  Autoconsistencia: {boosted} confirmados, "
                         f"{demoted} divergentes")

    @staticmethod
    def _macro_deviation(fields_a: dict, fields_b: dict) -> Optional[float]:
        """Desvio relativo medio dos macros principais entre duas respostas."""
        keys = ("valorEnergetico429", "carboidratos429",
                "proteinas429", "gordurasTotais429")
        devs = []
        for k in keys:
            a, b = to_float((fields_a or {}).get(k)), to_float((fields_b or {}).get(k))
            if a is None or b is None:
                continue
            base = max(abs(a), abs(b), 1.0)
            devs.append(abs(a - b) / base)
        return sum(devs) / len(devs) if devs else None

    def _ai_fallback(self, no_match_foods: list[ProcessedFood],
                     gui_callback=None, on_item=None):
        """Busca valores nutricionais via IA em lotes (rapido)."""
        if not self.ai_finder:
            if gui_callback:
                gui_callback("  IA: finder nao configurado")
            return

        available = self.ai_finder.get_available_providers()
        if not available:
            logger.warning("Nenhum provedor de IA disponivel")
            if gui_callback:
                gui_callback("  IA: nenhum provedor disponivel")
            return

        names = [pf.platform_name for pf in no_match_foods]
        logger.info(f"Provedores IA disponiveis: {available}")
        if gui_callback:
            gui_callback(
                f"  IA: consultando {len(names)} alimentos "
                f"em lotes de 12 (tabela ou receita calculada)..."
            )

        results = self.ai_finder.find_batch(
            names, batch_size=12, gui_callback=gui_callback
        )

        ai_count = 0
        for pf in no_match_foods:
            res = results.get(pf.platform_name.lower().strip())
            if res and res.success and res.fields:
                # Confianca: base por metodo x sanidade x completude
                score, issues = self._sanity_check_fields(res.fields)
                completeness = max(0.0, min(1.0, res.confidence / 100.0))
                is_recipe = res.method_note == "receita"
                base = self._AI_BASE["receita" if is_recipe else "tabela"]
                conf = (base - 20.0 * (1.0 - score)) \
                    * (0.7 + 0.3 * completeness)

                method = f"ai_{res.provider}" + ("_rec" if is_recipe else "")
                tag = "[IA:%s%s]" % (res.provider,
                                     ":receita" if is_recipe else "")
                pf.match = MatchResult(
                    platform_name=pf.platform_name,
                    tbca_name=f"{tag} {pf.platform_name}",
                    tbca_code=f"AI-{res.provider}",
                    confidence=round(min(conf, 90.0), 1),
                    match_method=method,
                    tbca_nutrients={},
                )
                pf.fields_to_fill = res.fields

                if score < 0.5:
                    pf.status = "review_needed"
                    pf.suggestion = "Sanidade: " + "; ".join(
                        i.split(": ", 1)[-1] for i in issues[:2]
                    )
                    logger.warning(
                        f"  IA ({res.provider}): {pf.platform_name} -> "
                        f"REVISAR (sanidade {score:.2f}: "
                        f"{issues[0] if issues else '?'})"
                    )
                else:
                    pf.status = "matched"
                    ai_count += 1
                    logger.info(
                        f"  IA ({res.provider}"
                        f"{':receita' if is_recipe else ''}): "
                        f"{pf.platform_name} -> "
                        f"{len(res.fields)} campos "
                        f"(conf {pf.match.confidence:.0f}%, "
                        f"sanidade {score:.2f})"
                    )
            elif res:
                logger.debug(f"  IA: {pf.platform_name} sem dados ({res.error})")

            if on_item:
                on_item(pf)

        logger.info(
            f"IA: {ai_count}/{len(no_match_foods)} alimentos "
            f"encontrados via IA"
        )
        if gui_callback:
            gui_callback(f"  IA: {ai_count}/{len(no_match_foods)} alimentos encontrados")

    def _verify_matches(self, matched_foods: list[ProcessedFood],
                        gui_callback=None):
        """Verifica matches via IA em batch para evitar associacoes erradas.

        Otimizacoes:
        - Pula matches identicos (mesmo nome)
        - Pula matches com confianca alta (>85%)
        - Envia 20 alimentos por request (batch)
        """
        if not self.ai_finder:
            return

        pairs_to_verify = []
        skipped_obvious = 0
        index_map = {}

        for i, pf in enumerate(matched_foods):
            if not pf.match:
                continue

            # Pular matches de IA (ja foram validados)
            if pf.match.match_method.startswith("ai_"):
                skipped_obvious += 1
                continue

            tbca_name = pf.match.tbca_name
            if tbca_name.startswith("[USDA] "):
                tbca_name = tbca_name[7:]

            platform_lower = pf.platform_name.lower().strip()
            tbca_lower = tbca_name.lower().strip()

            # Pular se nomes sao identicos
            if platform_lower == tbca_lower:
                skipped_obvious += 1
                continue

            # Pular se confianca alta
            if pf.match.confidence >= 85:
                skipped_obvious += 1
                continue

            idx = len(pairs_to_verify)
            index_map[idx] = i
            pairs_to_verify.append({
                "id": idx,
                "platform": pf.platform_name,
                "tbca": tbca_name,
            })

        if not pairs_to_verify:
            logger.info(f"Verificacao: {skipped_obvious} obvios pulados, 0 para verificar")
            if gui_callback:
                gui_callback(f"  Verificacao: {skipped_obvious} obvios, 0 para verificar")
            return

        total = len(pairs_to_verify)
        logger.info(f"Verificando {total} matches via IA "
                    f"({skipped_obvious} obvios pulados)")
        if gui_callback:
            gui_callback(f"  Verificacao: {total} para analisar "
                        f"({skipped_obvious} obvios)...")

        results = self.ai_finder.verify_matches_batch(pairs_to_verify)

        flagged = 0
        verified = 0

        for r in results:
            idx = r["id"]
            food_idx = index_map.get(idx)
            if food_idx is None:
                continue
            pf = matched_foods[food_idx]

            if not r["match"]:
                pf.status = "review_needed"
                pf.skip_reason = "match_suspeito"
                pf.suggestion = f"IA ({r['provider']}): {r['reason']}"
                flagged += 1
                logger.warning(
                    f"  Match suspeito: '{pf.platform_name}' -> "
                    f"'{pf.match.tbca_name[:30]}' ({r['reason']})"
                )
            else:
                verified += 1

            if gui_callback and (verified + flagged) % 10 == 0:
                gui_callback(f"  Verificacao: {verified + flagged}/{total}, "
                           f"{flagged} suspeitos")

        logger.info(f"Verificacao: {verified + skipped_obvious} OK, {flagged} suspeitos")
        if gui_callback:
            gui_callback(f"  Verificacao: {verified + skipped_obvious} ok, "
                        f"{flagged} suspeitos para revisao")

    def step4_fill_and_save(self, processed_foods: list[ProcessedFood],
                            dry_run: bool = True, max_items: int = None):
        """Fase 4: Preenche e salva dados na plataforma."""
        logger.info(f"Fase 4: Preenchimento ({'DRY RUN' if dry_run else 'LIVE'})")

        if not self.platform:
            raise RuntimeError("Navegador nao iniciado")

        filled_count = 0
        saved_count = 0
        errors = 0
        skipped_count = sum(1 for p in processed_foods if p.status == "skipped")

        for i, pf in enumerate(processed_foods):
            processed_total = filled_count + saved_count + errors
            if max_items and processed_total >= max_items:
                break
            if pf.status != "matched":
                continue

            # Buscar nutrientes sob demanda (lazy load)
            if not self._ensure_nutrients(pf):
                logger.warning(f"  Sem dados nutricionais: {pf.platform_name}")
                pf.status = "error"
                pf.error = "Sem dados nutricionais disponiveis"
                errors += 1
                continue

            logger.info(f"[{i+1}/{len(processed_foods)}] {pf.platform_name} -> {pf.match.tbca_name}")

            try:
                # Abrir dialog de edicao
                if not self.platform.open_edit_dialog(pf.platform_name):
                    pf.status = "error"
                    pf.error = "Nao foi possivel abrir dialog"
                    errors += 1
                    continue

                # Ler dados atuais
                current = self.platform.get_nutritional_data()

                # Preencher com dados TBCA
                if not dry_run:
                    filled = self.platform.fill_nutritional_data(pf.fields_to_fill)
                    pf.fields_to_fill = filled
                    pf.status = "filled"

                    # Salvar
                    if self.platform.click_save():
                        pf.status = "saved"
                        saved_count += 1

                        # === VERIFICACAO POS-PREENCHIMENTO ===
                        verify_result = self._verify_after_save(pf)
                        pf.verification = verify_result

                        if not verify_result.dom_match:
                            logger.warning(
                                f"  VERIFICACAO: {pf.platform_name} - "
                                f"DOM mismatch! {verify_result.summary}"
                            )
                            # Retry: reabrir, repreencher, salvar novamente
                            retry_ok = self._retry_fill(pf)
                            if retry_ok:
                                logger.info(
                                    f"  RETRY: {pf.platform_name} - "
                                    f"Repreenchido e salvo com sucesso"
                                )
                            else:
                                logger.error(
                                    f"  RETRY: {pf.platform_name} - "
                                    f"Falha no repreenchimento"
                                )

                        if verify_result.ai_validated and not verify_result.valid:
                            logger.warning(
                                f"  VERIFICACAO IA: {pf.platform_name} - "
                                f"Valores questionaveis: "
                                f"{verify_result.issues}"
                            )

                        self.db.log_operation(
                            food_name=pf.platform_name,
                            food_code=pf.match.tbca_code,
                            operation="fill_save_verify",
                            status="success" if verify_result.dom_match else "warning",
                            details=json.dumps({
                                "tbca_name": pf.match.tbca_name,
                                "confidence": pf.match.confidence,
                                "fields_filled": len(filled),
                                "dom_match": verify_result.dom_match,
                                "matched_fields": verify_result.values_matched,
                                "total_fields": verify_result.values_total,
                                "ai_validated": verify_result.ai_validated,
                                "ai_valid": verify_result.valid,
                                "issues": verify_result.issues,
                            })
                        )
                    else:
                        pf.status = "error"
                        pf.error = "Falha ao salvar"
                        errors += 1
                else:
                    # Dry run: apenas registrar o que seria feito
                    pf.status = "filled"
                    filled_count += 1
                    logger.info(f"  [DRY RUN] Campos: {list(pf.fields_to_fill.keys())[:5]}...")

                self.platform._close_all_popups()
                self.platform.clear_search()
                time.sleep(self.settings.automation.operation_interval)

                # Se page navegou apos save, garantir que estamos na pagina correta
                if not dry_run and pf.status == "saved":
                    try:
                        current_url = self.platform.page.url
                        if "nutri" not in current_url:
                            self.platform.navigate_to_nutri(self.settings.platform.nutri_url)
                    except Exception:
                        self.platform.navigate_to_nutri(self.settings.platform.nutri_url)

            except Exception as e:
                logger.error(f"Erro ao processar {pf.platform_name}: {e}")
                pf.status = "error"
                pf.error = str(e)
                errors += 1
                try:
                    self.platform._close_all_popups()
                    self.platform.clear_search()
                except Exception:
                    # Pagina pode ter navegado, tentar recuperar
                    try:
                        self.platform.navigate_to_nutri(self.settings.platform.nutri_url)
                    except Exception:
                        pass

        logger.info(f"Fase 4 concluida: {filled_count} preenchidos, {saved_count} salvos, {skipped_count} ignorados, {errors} erros")
        return {
            "total": len(processed_foods),
            "matched": sum(1 for p in processed_foods if p.status in ("matched", "filled", "saved")),
            "filled": filled_count,
            "saved": saved_count,
            "skipped": skipped_count,
            "errors": errors,
            "suggestions": [
                {"name": p.platform_name, "reason": p.skip_reason, "suggestion": p.suggestion}
                for p in processed_foods if p.status == "skipped"
            ],
        }

    def _verify_after_save(self, pf: ProcessedFood) -> VerificationResult:
        """Verifica preenchimento apos salvar: read-back DOM + validacao IA."""
        no_ai = (
            not self.ai_finder
            or not self.ai_finder.get_available_providers()
        )

        # Read-back DOM
        readback = self.platform.read_back_after_save(
            pf.platform_name, pf.fields_to_fill
        )

        if no_ai:
            # Sem IA disponivel: so faz comparacao simples
            vresult = VerificationResult(food_name=pf.platform_name)
            if readback and pf.fields_to_fill:
                matched = sum(
                    1 for k, v in pf.fields_to_fill.items()
                    if self._simple_equal(v, readback.get(k, ""))
                )
                vresult.values_matched = matched
                vresult.values_total = len(pf.fields_to_fill)
                vresult.dom_match = (matched == len(pf.fields_to_fill))
            return vresult

        # Verificacao completa (DOM + IA)
        vresult = self.ai_finder.verify_fill(
            pf.platform_name, pf.fields_to_fill, readback
        )
        return vresult

    @staticmethod
    def _simple_equal(expected: str, actual: str) -> bool:
        """Comparacao simples de valores normalizados."""
        if not expected or not actual:
            return False
        exp = str(expected).strip()
        act = str(actual).strip()
        if "," in exp:
            exp = exp.replace(".", "").replace(",", ".")
        if "," in act:
            act = act.replace(".", "").replace(",", ".")
        try:
            return abs(float(exp) - float(act)) < 0.05
        except (ValueError, TypeError):
            return exp.lower() == act.lower()

    def _retry_fill(self, pf: ProcessedFood) -> bool:
        """Tenta repreencher e salvar apos falha de verificacao."""
        try:
            if not self.platform.open_edit_dialog(pf.platform_name):
                return False

            time.sleep(0.5)
            filled = self.platform.fill_nutritional_data(pf.fields_to_fill)
            pf.fields_to_fill = filled
            time.sleep(0.3)

            if self.platform.click_save():
                pf.status = "saved"
                return True
            return False

        except Exception as e:
            logger.warning(f"Erro no retry de {pf.platform_name}: {e}")
            try:
                self.platform._close_all_popups()
            except Exception:
                pass
            return False

    def _map_to_platform_fields(self, match: MatchResult) -> dict:
        """Mapeia nutrientes TBCA para campos do formulario da plataforma."""
        fields = {}
        nutrients = match.tbca_nutrients

        for tbca_key, platform_field in TBCA_TO_PLATFORM.items():
            nutrient = nutrients.get(tbca_key)
            if nutrient:
                val = nutrient["value_per_100g"]
                # Formato brasileiro: virgula como decimal
                if isinstance(val, float):
                    if val == int(val):
                        fields[platform_field] = f"{int(val)},0"
                    else:
                        fields[platform_field] = f"{val}".replace(".", ",")
                else:
                    fields[platform_field] = str(val)

        return fields

    def _load_all_cached_foods(self) -> list[TBCAFood]:
        """Carrega todos os alimentos do cache TBCA."""
        try:
            import sqlite3
            conn = sqlite3.connect(str(CACHE_DB))
            rows = conn.execute("SELECT * FROM tbca_foods").fetchall()
            conn.close()
            return [
                TBCAFood(
                    code=r[0], name=r[1], scientific_name=r[2],
                    group=r[3], description=r[4],
                    nutrients=json.loads(r[5])
                )
                for r in rows
            ]
        except Exception:
            return []

    def run_full_pipeline(self, dry_run: bool = True, max_items: int = None):
        """Executa pipeline completo de automacao."""
        results = {
            "phase1_collect": None,
            "phase2_tbca": None,
            "phase3_match": None,
            "phase4_fill": None,
        }

        try:
            # Fase 1
            platform_foods = self.step1_collect_platform_foods()
            results["phase1_collect"] = {"count": len(platform_foods)}

            # Fase 2 - usar nomes dos alimentos da plataforma como termos de busca
            search_terms = list(set(
                f["name"].split(",")[0].strip()
                for f in platform_foods
                if len(f["name"]) > 3
            ))
            tbca_foods = self.step2_build_tbca_index(search_terms)
            results["phase2_tbca"] = {"count": len(tbca_foods)}

            # Fase 3
            processed = self.step3_match_foods(platform_foods)
            results["phase3_match"] = {
                "total": len(processed),
                "matched": sum(1 for p in processed if p.status == "matched"),
            }

            # Fase 3b: Verificar status dos cards
            processed = self.step3b_check_card_status(processed)
            results["phase3b_check"] = {
                "skipped": sum(1 for p in processed if p.status == "skipped"),
                "suggestions": [
                    {"name": p.platform_name, "reason": p.skip_reason,
                     "suggestion": p.suggestion}
                    for p in processed if p.status == "skipped"
                ],
            }

            # Fase 4
            fill_results = self.step4_fill_and_save(processed, dry_run=dry_run, max_items=max_items)
            results["phase4_fill"] = fill_results

        except Exception as e:
            logger.exception("Erro no pipeline")
            results["error"] = str(e)

        return results

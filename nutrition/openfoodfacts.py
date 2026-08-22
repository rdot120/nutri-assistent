"""Fonte Open Food Facts - rotulos reais de produtos industrializados.

Usa o Search API oficial (search.openfoodfacts.org), filtrando produtos
do Brasil e priorizando os mais populares/completos.
"""
import logging
import re
import time
from difflib import SequenceMatcher

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://search.openfoodfacts.org/search"
USER_AGENT = ("NutriAssistent/1.2 "
              "(https://github.com/rdot120; contato@qualihouse.com.br)")

# Campos OF -> plataforma
_NUTRI_MAP = {
    "valorEnergetico429": ["energy-kcal_100g", "energy_100g"],  # kcal
    "carboidratos429": ["carbohydrates_100g"],
    "acucaresTotais429": ["sugars_100g"],
    "proteinas429": ["proteins_100g"],
    "gordurasTotais429": ["fat_100g"],
    "gordurasSaturadas429": ["saturated-fat_100g"],
    "fibraAlimentar429": ["fiber_100g"],
    "sodio429": ["sodium_100g"],  # g -> mg
}


def _norm(texto: str) -> str:
    """Normaliza para comparacao de nomes."""
    t = texto.lower().strip()
    t = re.sub(r"[áàâãä]", "a", t)
    t = re.sub(r"[éèêë]", "e", t)
    t = re.sub(r"[íìîï]", "i", t)
    t = re.sub(r"[óòôõö]", "o", t)
    t = re.sub(r"[úùûü]", "u", t)
    t = re.sub(r"[ç]", "c", t)
    return re.sub(r"[^a-z0-9 ]", " ", t)


class OpenFoodFactsSource:
    """Busca rotulos reais no Open Food Facts."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        self._last_request = time.time()

    def _search(self, query: str) -> list[dict]:
        """Etapa 1: busca codigos candidatos no Search API."""
        self._throttle()
        resp = self.session.get(
            SEARCH_URL,
            params={
                "q": query,
                "page_size": 8,
                "countries_tags": "brazil",
                "sort_by": "popularity_key",
            },
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            logger.debug("OF search status %s para '%s'",
                         resp.status_code, query)
            return []
        return resp.json().get("hits") or []

    def _fetch_product(self, code: str) -> dict | None:
        """Etapa 2: tabela nutricional completa via API v2."""
        try:
            self._throttle()
            resp = self.session.get(
                f"https://world.openfoodfacts.org/api/v2/product/{code}.json",
                params={"fields": "product_name,brands,nutriments"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None
            return resp.json().get("product") or {}
        except Exception as exc:
            logger.warning("OF produto %s: %s", code, exc)
            return None

    def search_product(self, query: str) -> dict | None:
        """Busca um produto e retorna {"fields", "product_name", "brands",
        "score"} ou None se nada confiavel for encontrado."""
        try:
            hits = self._search(query)
        except Exception as exc:
            logger.warning("OF erro '%s': %s", query, exc)
            return None

        q_tokens = set(_norm(query).split())
        # Token principal (marca/produto) precisa constar no nome do hit
        _STOP = {"em", "de", "da", "do", "com", "para", "e"}
        main_tokens = q_tokens - _STOP

        best = None
        checked = 0
        for hit in hits:
            name = (hit.get("product_name") or "").strip()
            if not name or len(name) < 3:
                continue
            n_tokens = set(_norm(name).split())
            if main_tokens and not (main_tokens & n_tokens):
                continue
            if checked >= 3:  # no maximo 3 produtos completos por consulta
                break
            full = self._fetch_product(hit.get("code"))
            if not full:
                continue
            checked += 1

            full_name = ((full.get("product_name") or "").strip()
                         or name)
            fields = self._extract_fields(full.get("nutriments") or {})
            if len(fields) < 6 or "valorEnergetico429" not in fields:
                continue

            # Score: quantidade campos + sobreposicao de nome + similaridade
            fn_tokens = set(_norm(full_name).split())
            overlap = max(
                len(q_tokens & n_tokens),
                len(q_tokens & fn_tokens),
            ) / max(1, len(q_tokens)) if q_tokens else 0
            seq_ratio = SequenceMatcher(
                None, _norm(query), _norm(full_name)).ratio()

            # Portao: o primeiro token da busca (o produto em si, ex.
            # "nescau", "bolo") precisa constar no nome do hit; alternativa
            # e sobreposicao alta de tokens. Evita casar so pela marca
            # (ex. "Nescau 2.0" -> "Licuado Nestle").
            ordered_main = [t for t in _norm(query).split()
                            if t not in _STOP]
            fn_tokens = set(_norm(full_name).split())
            first_ok = bool(ordered_main) \
                and ordered_main[0] in fn_tokens
            overlap = max(
                len(q_tokens & set(n_tokens)),
                len(q_tokens & fn_tokens),
            ) / max(1, len(q_tokens)) if q_tokens else 0
            if not (first_ok or overlap >= 0.40):
                continue

            seq_ratio = SequenceMatcher(
                None, _norm(query), _norm(full_name)).ratio()
            score = (min(1.0, len(fields) / 8) * 30
                     + overlap * 35 + seq_ratio * 35)

            if not best or score > best["score"]:
                brands = ", ".join(full.get("brands") or [])[:60]
                best = {
                    "product_name": full_name,
                    "brands": brands,
                    "fields": fields,
                    "score": round(min(score, 100.0), 1),
                }

        if best and best["score"] >= 55:
            return best
        return None

    def _extract_fields(self, nutriments: dict) -> dict:
        """Converte nutriments do OF para campos da plataforma."""
        fields = {}
        for plat_key, of_keys in _NUTRI_MAP.items():
            value = None
            for k in of_keys:
                v = nutriments.get(k)
                if isinstance(v, (int, float)) and v == v:  # nao-NaN
                    value = float(v)
                    break
            if value is None:
                continue
            if plat_key == "valorEnergetico429" \
                    and "energy-kcal_100g" not in nutriments:
                value = value / 4.184  # veio em kJ
            if plat_key == "sodio429":
                value = value * 1000.0  # g -> mg
            fields[plat_key] = f"{value:.1f}".rstrip("0").rstrip(".")
        return fields

    def search_batch(self, names: list[str],
                     gui_callback=None) -> dict[str, dict]:
        """Busca varios produtos. Retorna {nome_normalizado: resultado}."""
        out = {}
        total = len(names)
        for i, name in enumerate(names, start=1):
            res = self.search_product(name)
            if gui_callback and i % 5 == 0:
                gui_callback(f"  Rotulos OF: {i}/{total}...")
            if res:
                out[name.lower().strip()] = res
        return out

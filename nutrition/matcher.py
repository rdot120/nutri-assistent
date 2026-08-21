"""
Correspondencia de alimentos entre plataforma e TBCA.
Usa fuzzy matching (rapidfuzz) para encontrar o melhor match.
"""
import logging
import re
import unicodedata
from typing import Optional
from dataclasses import dataclass

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Resultado de uma correspondencia."""
    platform_name: str
    tbca_name: str
    tbca_code: str
    confidence: float
    match_method: str
    tbca_nutrients: dict = None

    def __post_init__(self):
        if self.tbca_nutrients is None:
            self.tbca_nutrients = {}


def normalize_food_name(name: str) -> str:
    """Normaliza nome do alimento para matching."""
    name = name.strip().lower()
    nfkd = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in nfkd if not unicodedata.combining(c))
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def extract_food_base(name: str) -> str:
    """
    Extrai o 'nome base' do alimento (todas as palavras antes da primeira virgula).
    Ex: "Abacate, polpa, in natura, Brasil" -> "abacate"
    Ex: "Carne, frango, inteiro" -> "carne frango"
    """
    norm = normalize_food_name(name)
    first_part = norm.split(",")[0].strip()
    first_part = re.sub(r"\s*\(.*?\)", "", first_part)
    return first_part.strip()


class FoodMatcher:
    """Encontra correspondencias entre plataforma e TBCA."""

    def __init__(self, high_threshold: float = 70.0, medium_threshold: float = 50.0):
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self._tbca_names = []
        self._tbca_foods = {}
        self._exact_index = {}  # normalized -> entry para O(1)
        self._base_index = {}   # base_word -> [entries] para pre-filter

    def load_tbca_index(self, foods: list):
        """Carrega indice de nomes TBCA para matching."""
        self._tbca_names = []
        self._tbca_foods = {}
        self._exact_index = {}
        self._base_index = {}
        for food in foods:
            if hasattr(food, "name"):
                code = food.code
                name = food.name
                nutrients = food.nutrients if hasattr(food, "nutrients") else {}
            else:
                code = food.get("code", "")
                name = food.get("name", "")
                nutrients = food.get("nutrients", {})

            norm_name = normalize_food_name(name)
            base = extract_food_base(name)
            entry = {
                "original": name,
                "normalized": norm_name,
                "base": base,
                "base_words": base.split(),
                "code": code,
            }
            self._tbca_names.append(entry)
            self._exact_index[norm_name] = entry
            # Indexar por primeira palavra base
            if entry["base_words"]:
                first = entry["base_words"][0]
                if first not in self._base_index:
                    self._base_index[first] = []
                self._base_index[first].append(entry)
            self._tbca_foods[code] = type("Food", (), {
                "nutrients": nutrients,
                "name": name,
                "code": code,
            })()
        logger.info(f"Indice TBCA carregado: {len(self._tbca_names)} alimentos")

    # Palavras genericas que aparecem como primeira palavra em muitos TBCA entries
    GENERIC_FIRST_WORDS = {
        "carne", "leite", "oleo", "acucar", "sal", "bebida", "manteiga",
        "creme", "farinha", "macarrao", "molho", "ovo", "pao", "bolo",
        "arroz", "feijao", "iogurte", "queijo", "suco", "cha",
    }

    def _compute_score(self, entry: dict, platform_words: list[str]) -> float:
        """
        Calcula score de match entre um entry TBCA e o nome da plataforma.
        Retorna 0-100.
        """
        tbca_base = entry["base"]
        tbca_norm = entry["normalized"]
        tbca_first_words = entry["base_words"]

        if not tbca_first_words or not platform_words:
            return 0.0

        platform_first = platform_words[0]
        tbca_first = tbca_first_words[0]

        # === Criterio 1: primeira palavra ===
        first_score = 0
        direct_match = False

        if tbca_first == platform_first:
            first_score = 60
            direct_match = True
        elif (tbca_first.startswith(platform_first) and len(platform_first) > 2
              and len(tbca_first) <= len(platform_first) * 2):
            first_score = 50
            direct_match = True
        elif (platform_first.startswith(tbca_first) and len(tbca_first) > 3
              and len(platform_first) <= len(tbca_first) * 2):
            first_score = 45
            direct_match = True
        else:
            # Verificar se primeira palavra do TBCA e generica e platform_first
            # aparece como segunda palavra
            if (tbca_first in self.GENERIC_FIRST_WORDS
                    and len(tbca_first_words) > 1
                    and tbca_first_words[1] == platform_first):
                # Ex: TBCA="Carne, frango, inteiro", platform="FRANGO INTEIRO"
                first_score = 55  # Um pouco menos que match direto
            else:
                return 0.0

        # === Criterio 2: palavras adicionais ===
        extra_score = 0
        tbca_norm_words = set(tbca_norm.split())

        if len(platform_words) > 1:
            # Multi-word platform: contar quantas palavras extras aparecem no TBCA
            if direct_match:
                extra_matches = sum(1 for pw in platform_words[1:] if pw in tbca_norm_words)
            else:
                extra_matches = sum(1 for pw in platform_words[1:] if pw in tbca_norm_words)
            extra_ratio = extra_matches / (len(platform_words) - 1)
            extra_score = extra_ratio * 40  # Max 40 points
            if extra_matches == 0:
                first_score = int(first_score * 0.5)
        else:
            # Single-word platform: bonus por simplicidade
            if len(tbca_first_words) == 1:
                extra_score = 30  # Entrada simples
            elif len(tbca_first_words) == 2:
                extra_score = 20
            else:
                extra_score = 10

        return min(first_score + extra_score, 100.0)

    def _fuzzy_score(self, norm_a: str, norm_b: str) -> float:
        """Score fuzzy entre dois nomes normalizados."""
        return fuzz.token_set_ratio(norm_a, norm_b)

    def match(self, platform_name: str) -> Optional[MatchResult]:
        """
        Busca o melhor match para um alimento da plataforma no TBCA.
        """
        if not self._tbca_names:
            return None

        norm_platform = normalize_food_name(platform_name)
        platform_words = norm_platform.split()

        # 1. Match exato: O(1) via indice
        exact = self._exact_index.get(norm_platform)
        if exact:
            return MatchResult(
                platform_name=platform_name,
                tbca_name=exact["original"],
                tbca_code=exact["code"],
                confidence=100.0,
                match_method="exact",
                tbca_nutrients=self._tbca_foods[exact["code"]].nutrients,
            )

        # 2. Pre-filter: pegar apenas candidates cuja primeira palavra bate
        #    ou cuja primeira palavra do TBCA e generica
        platform_first = platform_words[0] if platform_words else ""
        candidates = set()
        if platform_first in self._base_index:
            candidates.update(id(e) for e in self._base_index[platform_first])
        # Incluir genericos (ex: platform="frango" vs TBCA="carne, frango")
        for gen in self.GENERIC_FIRST_WORDS:
            if gen in self._base_index:
                for entry in self._base_index[gen]:
                    if len(entry["base_words"]) > 1 and entry["base_words"][1] == platform_first:
                        candidates.add(id(entry))
        # Se poucos candidatos, incluir todos (para fuzzy)
        if len(candidates) < 10:
            candidates = set(id(e) for e in self._tbca_names)

        # 3. Match estruturado: so nos candidatos pre-filtrados
        best_structured = None
        best_structured_score = 0

        candidate_set = {id(e): e for e in self._tbca_names if id(e) in candidates}
        for entry in candidate_set.values():
            score = self._compute_score(entry, platform_words)
            if score > best_structured_score:
                best_structured_score = score
                best_structured = entry
            elif (score == best_structured_score and score > 0
                  and best_structured is not None):
                if len(entry["base_words"]) < len(best_structured["base_words"]):
                    best_structured = entry

        # Se estrutural ja e forte o suficiente, pular fuzzy
        if best_structured and best_structured_score >= self.high_threshold:
            return MatchResult(
                platform_name=platform_name,
                tbca_name=best_structured["original"],
                tbca_code=best_structured["code"],
                confidence=min(best_structured_score, 100),
                match_method="structured",
                tbca_nutrients=self._tbca_foods[best_structured["code"]].nutrients,
            )

        # 4. Fuzzy: so nos candidatos pre-filtrados
        best_fuzzy = None
        best_fuzzy_score = 0

        for entry in candidate_set.values():
            score = self._fuzzy_score(norm_platform, entry["normalized"])
            if score > best_fuzzy_score:
                tbca_first = entry["base_words"][0] if entry["base_words"] else ""
                if fuzz.ratio(tbca_first, platform_first) >= 70:
                    best_fuzzy_score = score
                    best_fuzzy = entry

        # 5. Decidir qual usar
        candidate = None
        candidate_score = 0
        candidate_method = ""

        if best_structured and best_structured_score >= self.high_threshold:
            candidate = best_structured
            candidate_score = best_structured_score
            candidate_method = "structured"
        elif best_fuzzy and best_fuzzy_score >= 80:
            penalty = 1.0
            if best_structured:
                if best_structured_score < 30:
                    penalty = 0.7
                elif best_structured_score < 50:
                    penalty = 0.85
            else:
                penalty = 0.75
            candidate = best_fuzzy
            candidate_score = best_fuzzy_score * penalty
            candidate_method = "fuzzy"
        elif best_structured and best_structured_score >= self.medium_threshold:
            candidate = best_structured
            candidate_score = best_structured_score
            candidate_method = "structured_weak"
        elif best_fuzzy and best_fuzzy_score >= self.medium_threshold:
            penalty = 0.65
            candidate = best_fuzzy
            candidate_score = best_fuzzy_score * penalty
            candidate_method = "fuzzy_weak"

        if candidate and candidate_score >= self.medium_threshold:
            return MatchResult(
                platform_name=platform_name,
                tbca_name=candidate["original"],
                tbca_code=candidate["code"],
                confidence=min(candidate_score, 100),
                match_method=candidate_method,
                tbca_nutrients=self._tbca_foods[candidate["code"]].nutrients,
            )

        return None

    def match_all(self, platform_names: list[str]) -> dict[str, Optional[MatchResult]]:
        """Busca matches para todos os nomes da plataforma."""
        results = {}
        total = len(platform_names)
        for i, name in enumerate(platform_names):
            if (i + 1) % 100 == 0:
                logger.info(f"Matching: {i+1}/{total}...")
            results[name] = self.match(name)
        matched = sum(1 for v in results.values() if v is not None)
        logger.info(f"Matches encontrados: {matched}/{total}")
        return results

"""
Deteccao e sugestao de merge de alimentos duplicados.
Detecta nomes parecidos e sugere unificacao.
"""
import logging
from typing import Optional
from dataclasses import dataclass, field
from rapidfuzz import fuzz

from nutrition.matcher import normalize_food_name, extract_food_base

logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """Grupo de alimentos potencialmente duplicados."""
    items: list = field(default_factory=list)
    similarity: float = 0
    suggested_keep: str = ""
    suggested_remove: list = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)


@dataclass
class DuplicateItem:
    """Item em um grupo de duplicatas."""
    name: str
    source: str  # "platform", "tbca", "manual"
    code: str = ""
    normalized: str = ""
    base_words: list = field(default_factory=list)


class Deduplicator:
    """Detecta e sugere merge de alimentos duplicados."""

    def __init__(self, similarity_threshold: float = 80.0):
        self.similarity_threshold = similarity_threshold

    def find_duplicates(self, platform_foods: list[dict],
                        tbca_foods: list[dict] = None,
                        manual_foods: dict = None) -> list[DuplicateGroup]:
        """
        Busca duplicatas entre alimentos da plataforma, TBCA e manuais.
        Retorna grupos de duplicatas.
        """
        all_items = []

        for food in platform_foods:
            name = food.get("name", "")
            if len(name) < 3:
                continue
            all_items.append(DuplicateItem(
                name=name,
                source="platform",
                code=food.get("code", ""),
                normalized=normalize_food_name(name),
                base_words=extract_food_base(name).split(),
            ))

        if tbca_foods:
            for food in tbca_foods:
                name = food.get("name", "")
                if len(name) < 3:
                    continue
                all_items.append(DuplicateItem(
                    name=name,
                    source="tbca",
                    code=food.get("code", ""),
                    normalized=normalize_food_name(name),
                    base_words=extract_food_base(name).split(),
                ))

        if manual_foods:
            for name in manual_foods:
                if len(name) < 3:
                    continue
                all_items.append(DuplicateItem(
                    name=name,
                    source="manual",
                    normalized=normalize_food_name(name),
                    base_words=extract_food_base(name).split(),
                ))

        groups = self._cluster_items(all_items)

        for group in groups:
            self._suggest_merge(group)

        logger.info(f"Encontrados {len(groups)} grupos de duplicatas")
        return groups

    def _cluster_items(self, items: list[DuplicateItem]) -> list[DuplicateGroup]:
        """Agrupa itens por similaridade usando Union-Find."""
        n = len(items)
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        similarities = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._compute_similarity(items[i], items[j])
                if sim >= self.similarity_threshold:
                    similarities.append((sim, i, j))

        similarities.sort(reverse=True)

        for sim, i, j in similarities:
            union(i, j)

        clusters = {}
        for i in range(n):
            root = find(i)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append((sim if similarities else 0, items[i]))

        groups = []
        for root, members in clusters.items():
            if len(members) < 2:
                continue
            group = DuplicateGroup(
                items=[item for _, item in members],
                similarity=members[0][0] if members else 0,
            )
            groups.append(group)

        return groups

    def _compute_similarity(self, a: DuplicateItem, b: DuplicateItem) -> float:
        """Calcula similaridade entre dois itens."""
        if a.normalized == b.normalized:
            return 100.0

        sim = fuzz.token_set_ratio(a.normalized, b.normalized)

        if a.base_words and b.base_words:
            if a.base_words[0] == b.base_words[0]:
                sim = max(sim, 85)
            elif (len(a.base_words) > 1 and a.base_words[1] == b.base_words[0]):
                sim = max(sim, 80)
            elif (len(b.base_words) > 1 and b.base_words[1] == a.base_words[0]):
                sim = max(sim, 80)

        return sim

    def _suggest_merge(self, group: DuplicateGroup):
        """Sugere qual item manter e quais remover."""
        if not group.items:
            return

        source_priority = {"platform": 3, "tbca": 2, "manual": 1}

        best = max(
            group.items,
            key=lambda x: (
                source_priority.get(x.source, 0),
                -len(x.name),
            )
        )

        group.suggested_keep = best.name
        group.suggested_remove = [
            item.name for item in group.items if item.name != best.name
        ]

    def apply_merge(self, food_name: str, merge_to: str,
                    platform_foods: list[dict]) -> list[dict]:
        """Aplica merge: redireciona food_name para merge_to."""
        for food in platform_foods:
            if food.get("name") == food_name:
                food["name"] = merge_to
                food["_merged_from"] = food_name
                break
        return platform_foods

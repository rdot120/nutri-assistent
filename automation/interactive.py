"""
Modo assistente interativo.
Permite revisao campo-a-campo antes de preencher, sem automacao.
"""
import time
import logging
from typing import Optional, Callable
from dataclasses import dataclass, field

from automation.orchestrator import Orchestrator, ProcessedFood

logger = logging.getLogger(__name__)


@dataclass
class FieldReview:
    """Revisao de um campo individual."""
    food_name: str
    field_name: str
    field_label: str
    old_value: str
    new_value: str
    approved: bool = False
    edited_value: Optional[str] = None

    @property
    def final_value(self) -> str:
        if self.approved:
            return self.edited_value if self.edited_value is not None else self.new_value
        return self.old_value


@dataclass
class FoodReview:
    """Revisao completa de um alimento."""
    processed: ProcessedFood
    fields: list = field(default_factory=list)
    status: str = "pending"  # pending, approved, rejected, edited
    notes: str = ""

    @property
    def approved_count(self) -> int:
        return sum(1 for f in self.fields if f.approved)

    @property
    def rejected_count(self) -> int:
        return sum(1 for f in self.fields if not f.approved)


# Labels dos campos
FIELD_LABELS = {
    "valorEnergetico429": "Valor Energetico (kcal)",
    "carboidratos429": "Carboidratos (g)",
    "acucaresTotais429": "Acucares Totais (g)",
    "acucaresAdicionados": "Acucares Adicionados (g)",
    "proteinas429": "Proteinas (g)",
    "gordurasTotais429": "Gorduras Totais (g)",
    "gordurasSaturadas429": "Gorduras Saturadas (g)",
    "gordurasTrans429": "Gorduras Trans (g)",
    "fibraAlimentar429": "Fibra Alimentar (g)",
    "sodio429": "Sodio (mg)",
    "lactose": "Lactose (g)",
    "galactose": "Galactose (g)",
    "colesterol": "Colesterol (mg)",
    "calcio": "Calcio (mg)",
    "ferro": "Ferro (mg)",
    "fosforo": "Fosforo (mg)",
    "magnesio": "Magnesio (mg)",
    "potassio": "Potassio (mg)",
    "zinco": "Zinco (mg)",
    "vitaminaA": "Vitamina A (mcg)",
    "vitaminaB1": "Vitamina B1 (mg)",
    "vitaminaB2": "Vitamina B2 (mg)",
    "vitaminaB3": "Vitamina B3 (mg)",
    "vitaminaB6": "Vitamina B6 (mg)",
    "vitaminaB9": "Vitamina B9/Folato (mcg)",
    "vitaminaB12": "Vitamina B12 (mcg)",
    "vitaminaC": "Vitamina C (mg)",
    "vitaminaD": "Vitamina D (mcg)",
    "vitaminaE": "Vitamina E (mg)",
    "vitaminaK": "Vitamina K (mcg)",
}


class InteractiveAssistant:
    """Modo assistente: mostra diffs e permite confirmar campo-a-campo."""

    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self.reviews: list[FoodReview] = []
        self._current_index = 0

    def prepare_reviews(self, processed_foods: list[ProcessedFood]):
        """Prepara revisoes para todos os alimentos com match."""
        self.reviews = []
        for pf in processed_foods:
            if pf.status != "matched" or not pf.fields_to_fill:
                continue
            food_review = FoodReview(processed=pf)
            for field_name, new_val in pf.fields_to_fill.items():
                label = FIELD_LABELS.get(field_name, field_name)
                food_review.fields.append(FieldReview(
                    food_name=pf.platform_name,
                    field_name=field_name,
                    field_label=label,
                    old_value="",
                    new_value=str(new_val),
                ))
            self.reviews.append(food_review)
        self._current_index = 0
        logger.info(f"Preparadas {len(self.reviews)} revisoes")

    def get_current_review(self) -> Optional[FoodReview]:
        """Retorna revisao atual."""
        if self._current_index < len(self.reviews):
            return self.reviews[self._current_index]
        return None

    def approve_current(self):
        """Aprova todos os campos do alimento atual."""
        review = self.get_current_review()
        if review:
            for field in review.fields:
                field.approved = True
            review.status = "approved"
            self._current_index += 1

    def reject_current(self):
        """Rejeita alimento atual."""
        review = self.get_current_review()
        if review:
            for field in review.fields:
                field.approved = False
            review.status = "rejected"
            self._current_index += 1

    def approve_field(self, field_index: int, edited_value: str = None):
        """Aprova um campo individual."""
        review = self.get_current_review()
        if review and field_index < len(review.fields):
            review.fields[field_index].approved = True
            if edited_value is not None:
                review.fields[field_index].edited_value = edited_value

    def reject_field(self, field_index: int):
        """Rejeita um campo individual."""
        review = self.get_current_review()
        if review and field_index < len(review.fields):
            review.fields[field_index].approved = False

    def edit_field(self, field_index: int, new_value: str):
        """Edita valor de um campo."""
        review = self.get_current_review()
        if review and field_index < len(review.fields):
            review.fields[field_index].edited_value = new_value
            review.fields[field_index].approved = True
            review.status = "edited"

    def skip_current(self):
        """Pula para proximo alimento sem alterar."""
        self._current_index += 1

    def go_back(self):
        """Volta para alimento anterior."""
        if self._current_index > 0:
            self._current_index -= 1

    def get_approved_fields(self) -> dict:
        """Retorna campos aprovados para preenchimento."""
        review = self.get_current_review()
        if not review:
            return {}
        return {f.field_name: f.final_value for f in review.fields if f.approved}

    def apply_approved(self) -> list[dict]:
        """Retorna lista de acoes aprovadas para todos os alimentos."""
        actions = []
        for review in self.reviews:
            if review.status in ("approved", "edited"):
                fields = {}
                for f in review.fields:
                    if f.approved:
                        fields[f.field_name] = f.final_value
                if fields:
                    actions.append({
                        "food_name": review.processed.platform_name,
                        "fields": fields,
                        "match": review.processed.match,
                    })
        return actions

    def get_summary(self) -> dict:
        """Retorna resumo da revisao."""
        total = len(self.reviews)
        approved = sum(1 for r in self.reviews if r.status == "approved")
        rejected = sum(1 for r in self.reviews if r.status == "rejected")
        edited = sum(1 for r in self.reviews if r.status == "edited")
        pending = total - approved - rejected - edited

        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "edited": edited,
            "pending": pending,
            "current_index": self._current_index,
        }

    def auto_approve_high_confidence(self, threshold: float = 90.0):
        """Aprova automaticamente itens com alta confianca."""
        for review in self.reviews:
            if review.status != "pending":
                continue
            if review.processed.match and review.processed.match.confidence >= threshold:
                for field in review.fields:
                    field.approved = True
                review.status = "approved"

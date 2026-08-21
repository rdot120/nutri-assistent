"""
Importacao de dados de planilhas (CSV/Excel) e OCR de imagens.
Permite importar valores nutricionais de fontes externas.
"""
import csv
import json
import re
import time
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Mapeamento de nomes comuns de colunas para campos do formulario
COLUMN_MAPPING = {
    # Portugues
    "energia": "valorEnergetico429",
    "caloria": "valorEnergetico429",
    "calorias": "valorEnergetico429",
    "energia (kcal)": "valorEnergetico429",
    "carboidrato": "carboidratos429",
    "carboidratos": "carboidratos429",
    "proteina": "proteinas429",
    "proteinas": "proteinas429",
    "gordura": "gordurasTotais429",
    "gorduras": "gordurasTotais429",
    "gorduras totais": "gordurasTotais429",
    "lipidios": "gordurasTotais429",
    "gordura saturada": "gordurasSaturadas429",
    "gorduras saturadas": "gordurasSaturadas429",
    "gordura trans": "gordurasTrans429",
    "gorduras trans": "gordurasTrans429",
    "fibra": "fibraAlimentar429",
    "fibra alimentar": "fibraAlimentar429",
    "acucar": "acucaresTotais429",
    "acucares": "acucaresTotais429",
    "acucares totais": "acucaresTotais429",
    "sodio": "sodio429",
    "sal": "sodio429",
    "colesterol": "colesterol",
    "calcio": "calcio",
    "ferro": "ferro",
    "fosforo": "fosforo",
    "magnesio": "magnesio",
    "potassio": "potassio",
    "zinco": "zinco",
    "vitamina a": "vitaminaA",
    "vitamina b1": "vitaminaB1",
    "vitamina b2": "vitaminaB2",
    "vitamina b3": "vitaminaB3",
    "vitamina b6": "vitaminaB6",
    "vitamina b9": "vitaminaB9",
    "folato": "vitaminaB9",
    "vitamina b12": "vitaminaB12",
    "vitamina c": "vitaminaC",
    "vitamina d": "vitaminaD",
    "vitamina e": "vitaminaE",
    "vitamina k": "vitaminaK",
    "lactose": "lactose",
    "lactose (g)": "lactose",
    "galactose": "galactose",
    "galactose (g)": "galactose",
    # Ingles
    "energy": "valorEnergetico429",
    "calories": "valorEnergetico429",
    "carbohydrate": "carboidratos429",
    "carbs": "carboidratos429",
    "protein": "proteinas429",
    "fat": "gordurasTotais429",
    "total fat": "gordurasTotais429",
    "saturated fat": "gordurasSaturadas429",
    "trans fat": "gordurasTrans429",
    "fiber": "fibraAlimentar429",
    "dietary fiber": "fibraAlimentar429",
    "sugar": "acucaresTotais429",
    "sugars": "acucaresTotais429",
    "sodium": "sodio429",
    "calcium": "calcio",
    "iron": "ferro",
    "potassium": "potassio",
    "vitamin a": "vitaminaA",
    "vitamin c": "vitaminaC",
    "vitamin d": "vitaminaD",
    "vitamin e": "vitaminaE",
}


@dataclass
class ImportResult:
    """Resultado de uma importacao."""
    source_file: str = ""
    import_type: str = ""  # "csv", "ocr", "paste"
    total_rows: int = 0
    imported: int = 0
    errors: int = 0
    skipped: int = 0
    food_name: str = ""
    fields: dict = field(default_factory=dict)
    error_messages: list = field(default_factory=list)


class SpreadsheetImporter:
    """Importa dados nutricionais de planilhas CSV."""

    def __init__(self):
        self._column_map = {}

    def detect_columns(self, headers: list[str]) -> dict[str, str]:
        """Detecta automaticamente colunas do CSV."""
        mapping = {}
        for i, header in enumerate(headers):
            normalized = header.strip().lower().replace("_", " ")
            if normalized in COLUMN_MAPPING:
                mapping[str(i)] = COLUMN_MAPPING[normalized]
            elif normalized in ("nome", "name", "alimento", "food", "descricao"):
                mapping[str(i)] = "_name"
            elif normalized in ("porcao", "portion", "quantidade", "serving"):
                mapping[str(i)] = "_portion"
        return mapping

    def import_csv(self, file_path: Path,
                   food_name: str = None) -> ImportResult:
        """Importa dados de um arquivo CSV."""
        result = ImportResult(
            source_file=str(file_path),
            import_type="csv",
        )

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    content = f.read()
            except Exception as e:
                result.errors = 1
                result.error_messages.append(f"Erro ao ler arquivo: {e}")
                return result

        lines = content.strip().split("\n")
        if len(lines) < 2:
            result.errors = 1
            result.error_messages.append("Arquivo vazio ou sem dados")
            return result

        headers = [h.strip() for h in lines[0].split(",")]
        result.total_rows = len(lines) - 1

        col_map = self.detect_columns(headers)
        if not col_map:
            result.errors = 1
            result.error_messages.append("Nenhuma coluna nutricional detectada")
            return result

        for line_num, line in enumerate(lines[1:], start=2):
            try:
                values = [v.strip() for v in line.split(",")]
                food_name_found = food_name

                for col_idx, field_name in col_map.items():
                    idx = int(col_idx)
                    if idx >= len(values):
                        continue

                    val = values[idx]
                    if not val or val == "-":
                        continue

                    if field_name == "_name" and not food_name_found:
                        food_name_found = val
                    elif field_name == "_portion":
                        continue
                    else:
                        cleaned = self._clean_value(val)
                        if cleaned is not None:
                            result.fields[field_name] = cleaned

                result.imported += 1

            except Exception as e:
                result.errors += 1
                result.error_messages.append(f"Linha {line_num}: {e}")

        result.food_name = food_name_found or ""
        return result

    def import_paste(self, text: str, food_name: str = None) -> ImportResult:
        """Importa dados de texto copiado (formato tabulado)."""
        result = ImportResult(import_type="paste")

        lines = text.strip().split("\n")
        if not lines:
            result.errors = 1
            result.error_messages.append("Texto vazio")
            return result

        result.total_rows = len(lines)
        result.food_name = food_name or ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Tentar formato "campo: valor" ou "campo = valor"
            match = re.match(r"(.+?)\s*[:=]\s*(.+)", line)
            if match:
                label = match.group(1).strip().lower()
                value = match.group(2).strip()

                if label in COLUMN_MAPPING:
                    field = COLUMN_MAPPING[label]
                    cleaned = self._clean_value(value)
                    if cleaned is not None:
                        result.fields[field] = cleaned
                        result.imported += 1
                else:
                    result.skipped += 1
            else:
                result.skipped += 1

        return result

    def _clean_value(self, val: str) -> Optional[float]:
        """Limpa e converte valor numerico."""
        val = val.strip()
        val = val.replace("mg", "").replace("g", "").replace("mcg", "")
        val = val.replace("kcal", "").replace("kJ", "")
        val = val.strip()

        if val.upper() in ("NA", "N/D", "-", "N.D.", ""):
            return None

        val = val.replace(",", ".")
        val = re.sub(r"[^\d.]", "", val)

        try:
            return float(val)
        except ValueError:
            return None

    def format_for_platform(self, fields: dict) -> dict:
        """Formata campos importados para formato da plataforma."""
        result = {}
        for field, value in fields.items():
            if isinstance(value, float):
                if value == int(value):
                    result[field] = f"{int(value)},0"
                else:
                    result[field] = f"{value}".replace(".", ",")
            else:
                result[field] = str(value)
        return result


class OCRImporter:
    """Importa dados de imagens usando OCR basico."""

    def __init__(self):
        self._available = False
        try:
            import pytesseract
            self._available = True
        except ImportError:
            logger.info("pytesseract nao disponivel, OCR desabilitado")

    @property
    def is_available(self) -> bool:
        return self._available

    def extract_text(self, image_path: Path) -> str:
        """Extrai texto de imagem."""
        if not self._available:
            raise RuntimeError("pytesseract nao esta instalado")

        import pytesseract
        from PIL import Image

        img = Image.open(str(image_path))
        text = pytesseract.image_to_string(img, lang="por")
        return text

    def import_from_image(self, image_path: Path,
                          food_name: str = None) -> ImportResult:
        """Importa dados nutricionais de uma imagem."""
        result = ImportResult(
            source_file=str(image_path),
            import_type="ocr",
        )

        try:
            text = self.extract_text(image_path)
        except Exception as e:
            result.errors = 1
            result.error_messages.append(f"Erro OCR: {e}")
            return result

        importer = SpreadsheetImporter()
        return importer.import_paste(text, food_name)

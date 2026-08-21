"""
Scraper do TBCA (Tabela Brasileira de Composicao de Alimentos).
Busca alimentos por nome e extrai dados nutricionais detalhados.
Usa requests + BeautifulSoup para parsing (mais leve que Playwright).
"""
import re
import time
import logging
import sqlite3
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TBCA_BASE = "https://www.tbca.net.br/base-dados"
TBCA_SEARCH = f"{TBCA_BASE}/composicao_alimentos.php"
TBCA_DETAIL = f"{TBCA_BASE}/int_composicao_alimentos.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# Mapeamento nome TBCA do componente -> chave normalizada
COMPONENT_MAP = {
    "energia": "energia_kcal",
    "energia kJ": "energia_kj",
    "energia kcal": "energia_kcal",
    "umidade": "umidade",
    "carboidrato total": "carboidrato_total",
    "carboidrato disponivel": "carboidrato_disponivel",
    "proteina": "proteina",
    "lipidios": "lipidios",
    "fibra alimentar": "fibra_alimentar",
    "alcool": "alcool",
    "cinzas": "cinzas",
    "colesterol": "colesterol",
    "acidos graxos saturados": "gorduras_saturadas",
    "acidos graxos monoinsaturados": "gorduras_monoinsaturadas",
    "acidos graxos poliinsaturados": "gorduras_poliinsaturadas",
    "acidos graxos trans": "gorduras_trans",
    "acido linoleico": "acido_linoleico",
    "acido linolenico": "acido_linolenico",
    "acido oleico": "acido_oleico",
    "acido araquidonico": "acido_araquidonico",
    "acido docosaexaenoico": "acido_docosaexaenoico_dha",
    "acido eicosapentaenoico": "acido_eicosapentaenoico_epa",
    "calcio": "calcio",
    "ferro": "ferro",
    "sodio": "sodio",
    "magnesio": "magnesio",
    "fosforo": "fósforo",
    "potassio": "potassio",
    "manganes": "manganes",
    "zinco": "zinco",
    "cobre": "cobre",
    "selenio": "selenio",
    "cromo": "cromo",
    "molibdenio": "molibdenio",
    "iodo": "iodo",
    "fluor": "fluor",
    "cloreto": "cloreto",
    "vitamina a (re)": "vitamina_a_re",
    "vitamina a (rae)": "vitamina_a_rae",
    "vitamina d": "vitamina_d",
    "alfa-tocoferol (vitamina e)": "vitamina_e",
    "tiamina": "vitamina_b1",
    "riboflavina": "vitamina_b2",
    "niacina": "vitamina_b3",
    "vitamina b6": "vitamina_b6",
    "vitamina b12": "vitamina_b12",
    "vitamina c": "vitamina_c",
    "equivalente de folato": "folato",
    "colina": "colina",
    "acucar de adicao": "acucar_adicionado",
    "sal de adicao": "sal_adicionado",
    "gordura de adicao": "gordura_adicionada",
    "proteina vegetal": "proteina_vegetal",
    "proteina animal": "proteina_animal",
}

# TBCA -> campo do formulario da plataforma
TBCA_TO_PLATFORM = {
    "energia_kcal": "valorEnergetico429",
    "carboidrato_total": "carboidratos429",
    "proteina": "proteinas429",
    "lipidios": "gordurasTotais429",
    "gorduras_saturadas": "gordurasSaturadas429",
    "gorduras_trans": "gordurasTrans429",
    "fibra_alimentar": "fibraAlimentar429",
    "sodio": "sodio429",
    "acucar_adicionado": "acucaresAdicionados",
    "colesterol": "colesterol",
    "calcio": "calcio",
    "ferro": "ferro",
    "magnesio": "magnesio",
    "fosforo": "fósforo",
    "potassio": "potassio",
    "manganes": "manganes",
    "zinco": "zinco",
    "cobre": "cobre",
    "selenio": "selenio",
    "vitamina_a_rae": "vitaminaA",
    "vitamina_d": "vitaminaD",
    "vitamina_e": "vitaminaE",
    "vitamina_b1": "vitaminaB1",
    "vitamina_b2": "vitaminaB2",
    "vitamina_b3": "vitaminaB3",
    "vitamina_b6": "vitaminaB6",
    "vitamina_b12": "vitaminaB12",
    "vitamina_c": "vitaminaC",
    "folato": "vitaminaB9",
    "acido_linoleico": "acidoLinoleico",
    "acido_linolenico": "acidoLinolenico",
    "acido_oleico": "acidoOleico",
    "acido_araquidonico": "acidoAraquidonico",
    "acido_docosaexaenoico_dha": "acidoDocosaexaenoico",
    "acido_eicosapentaenoico_epa": "acidoEicosapentaenoico",
    "gorduras_monoinsaturadas": "gordurasMonoInsaturadas",
    "gorduras_poliinsaturadas": "gordurasPoliInsaturadas",
    "cromo": "cromo",
    "molibdenio": "molibdenio",
    "iodo": "iodo",
    "fluor": "fluor",
    "cloreto": "cloreto",
    "colina": "colina",
}


@dataclass
class TBCAFood:
    """Dados de um alimento do TBCA."""
    code: str = ""
    name: str = ""
    scientific_name: str = ""
    group: str = ""
    food_type: str = ""
    description: str = ""
    nutrients: dict = None  # chave_normalizada -> {"value_per_100g": float, "unit": str}

    def __post_init__(self):
        if self.nutrients is None:
            self.nutrients = {}


class TBCAScraper:
    """Busca e extrai dados do TBCA."""

    def __init__(self, cache_db_path: Optional[Path] = None):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.cache_db_path = cache_db_path

    def _parse_value(self, text: str) -> Optional[float]:
        """Parse valor numerico do TBCA (usa virgula como decimal)."""
        if not text:
            return None
        text = text.strip()
        if text.upper() in ("NA", "N/D", "-", "N.D.", "NA.", ""):
            return None
        if text.lower() == "tr":
            return 0.0
        text = text.replace(" ", "")
        text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    def _parse_listing_page(self, html: str) -> list[dict]:
        """Parse uma pagina de listagem TBCA, retornando alimentos encontrados."""
        soup = BeautifulSoup(html, "html.parser")
        from collections import defaultdict
        href_groups = defaultdict(list)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "int_composicao_alimentos.php" in href:
                text = a.get_text(strip=True)
                if text and len(text) > 1:
                    full_url = f"{TBCA_BASE}/{href}" if not href.startswith("http") else href
                    href_groups[full_url].append(text)

        results = []
        for url, texts in href_groups.items():
            code = ""
            name = ""
            scientific = ""
            group = ""
            for t in texts:
                if re.match(r"^BRC\d+\w*$", t):
                    code = t
                elif any(g in t for g in ["Frutas", "Vegetais", "Carnes", "Cereais",
                                           "Leguminosas", "Latic", "Bebidas", "Gorduras",
                                           "Ovos", "Pescados", "Nozes", "Azucares",
                                           "Fast", "Miscel", "Refei"]):
                    group = t
                elif re.match(r"^[A-Z][a-z]+ [a-z]+", t):
                    scientific = t
                elif len(t) > 5:
                    name = t

            if code and name:
                results.append({
                    "code": code,
                    "name": name,
                    "scientific_name": scientific,
                    "group": group,
                    "url": url,
                })

        return results

    def fetch_all_listings(self, max_pages: int = 110, delay: float = 0.3) -> list[dict]:
        """
        Busca TODAS as paginas de listagem do TBCA e retorna indice completo.
        Cada entrada: {code, name, scientific_name, group, url}.
        """
        logger.info(f"Buscando todas as paginas de listagem TBCA (max {max_pages})")
        all_results = []
        seen_codes = set()

        for page in range(1, max_pages + 1):
            url = f"{TBCA_SEARCH}?pagina={page}&atuald=1"
            try:
                resp = self.session.get(url, timeout=15)
                resp.encoding = "utf-8"
            except requests.RequestException as e:
                logger.warning(f"Erro na pagina {page}: {e}")
                continue

            items = self._parse_listing_page(resp.text)
            if not items:
                logger.info(f"Pagina {page}: vazia, fim da listagem")
                break

            new_count = 0
            for item in items:
                if item["code"] not in seen_codes:
                    seen_codes.add(item["code"])
                    all_results.append(item)
                    new_count += 1

            logger.debug(f"Pagina {page}: {len(items)} itens, {new_count} novos")
            time.sleep(delay)

        logger.info(f"Total: {len(all_results)} alimentos unicos em {page} paginas")
        return all_results

    def save_listing_index(self, items: list[dict]):
        """Salva indice de listagem no SQLite (sem nutrientes detalhados)."""
        if not self.cache_db_path:
            return
        conn = sqlite3.connect(str(self.cache_db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tbca_index (
                code TEXT PRIMARY KEY,
                name TEXT,
                scientific_name TEXT,
                group_name TEXT,
                url TEXT,
                fetched_at REAL
            )
        """)
        now = time.time()
        for item in items:
            conn.execute(
                "INSERT OR REPLACE INTO tbca_index VALUES (?, ?, ?, ?, ?, ?)",
                (item["code"], item["name"], item["scientific_name"],
                 item["group"], item["url"], now)
            )
        conn.commit()
        conn.close()
        logger.info(f"Indice salvo: {len(items)} alimentos")

    def load_listing_index(self) -> list[dict]:
        """Carrega indice de listagem do SQLite."""
        if not self.cache_db_path:
            return []
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            # Verificar se tabela existe
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tbca_index'"
            ).fetchall()
            if not tables:
                conn.close()
                return []
            rows = conn.execute(
                "SELECT code, name, scientific_name, group_name, url FROM tbca_index"
            ).fetchall()
            conn.close()
            return [
                {"code": r[0], "name": r[1], "scientific_name": r[2],
                 "group": r[3], "url": r[4]}
                for r in rows
            ]
        except Exception:
            return []

    def _normalize_component(self, name: str) -> str:
        """Normaliza nome do componente TBCA para chave padronizada."""
        import unicodedata
        name = name.strip().lower()
        # Remover acentos via Unicode decomposition
        nfkd = unicodedata.normalize("NFKD", name)
        name = "".join(c for c in nfkd if not unicodedata.combining(c))
        # Buscar no mapa
        return COMPONENT_MAP.get(name, name)

    def search(self, query: str, page: int = 1) -> list[dict]:
        """
        Busca alimentos no TBCA por nome.
        Cada resultado tem: code, name, scientific_name, group, url.
        """
        logger.info(f"Buscando TBCA: '{query}' pagina {page}")

        params = {"q": query}
        try:
            resp = self.session.get(TBCA_SEARCH, params=params, timeout=15)
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            logger.error(f"Erro na busca TBCA: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # TBCA agrupa links por href (cada alimento = 3-4 links com mesmo href)
        from collections import defaultdict
        href_groups = defaultdict(list)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "int_composicao_alimentos.php" in href:
                text = a.get_text(strip=True)
                if text and len(text) > 1:
                    full_url = f"{TBCA_BASE}/{href}" if not href.startswith("http") else href
                    href_groups[full_url].append(text)

        results = []
        for url, texts in href_groups.items():
            code = ""
            name = ""
            scientific = ""
            group = ""
            for t in texts:
                if re.match(r"^BRC\d+\w*$", t):
                    code = t
                elif any(g in t for g in ["Frutas", "Vegetais", "Carnes", "Cereais",
                                           "Leguminosas", "Latic", "Bebidas", "Gorduras",
                                           "Ovos", "Pescados", "Nozes", "Azucares",
                                           "Fast", "Miscel", "Refei"]):
                    group = t
                elif re.match(r"^[A-Z][a-z]+ [a-z]+", t):
                    scientific = t
                elif len(t) > 5:
                    name = t

            if code and name:
                results.append({
                    "code": code,
                    "name": name,
                    "scientific_name": scientific,
                    "group": group,
                    "url": url,
                })

        logger.info(f"Encontrados {len(results)} resultados para '{query}'")
        return results

    def fetch_food(self, url: str) -> Optional[TBCAFood]:
        """Busca detalhes de um alimento do TBCA pela URL."""
        logger.info(f"Buscando detalhes: {url}")

        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar alimento: {e}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        food = TBCAFood()

        # Extrair metadados
        page_text = soup.get_text(" ", strip=True)

        code_match = re.search(r"C[oó]digo:\s*(BRC\d+\w*)", page_text)
        if code_match:
            food.code = code_match.group(1)

        group_match = re.search(r"Grupo:\s*(.+?)(?=Tipo|$)", page_text)
        if group_match:
            food.group = group_match.group(1).strip()

        type_match = re.search(r"Tipo de Alimento:\s*(.+?)(?=Nome|$)", page_text)
        if type_match:
            food.food_type = type_match.group(1).strip()

        name_match = re.search(r"Descri[cc][aã]o:\s*(.+?)(?=\s*<<|$)", page_text)
        if name_match:
            food.description = name_match.group(1).strip()
            food.name = food.description.split(",")[0].strip()

        sci_match = re.search(r"Nome Cient[ií]fico:\s*(.+?)(?=Descri|$)", page_text)
        if sci_match:
            food.scientific_name = sci_match.group(1).strip()

        # Extrair tabela de nutrientes
        # TBCA usa tabela HTML com colunas: Componente | Unidades | Valor por 100g | Pedaço/Unidade
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:
                    comp_text = cells[0].get_text(strip=True)
                    unit_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    val_100g_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                    # Pular cabecalhos
                    if comp_text.lower() in ("componente", ""):
                        continue
                    if "valor por 100g" in comp_text.lower():
                        continue

                    # Normalizar componente
                    comp_key = self._normalize_component(comp_text)

                    # Parse do valor
                    val = self._parse_value(val_100g_text)
                    if val is not None:
                        food.nutrients[comp_key] = {
                            "value_per_100g": val,
                            "unit": unit_text,
                            "original_name": comp_text,
                        }

        # Se nao encontrou tabela, tentar extrair de texto
        if not food.nutrients:
            # Padrao do TBCA: "ComponenteUnidadeValor por 100g..."
            # Tentar extrair pares componente-valor de texto
            nutrient_pattern = re.compile(
                r"([A-Za-zÀ-ÿ\s\(\)]+?)\s*(mg|g|mcg|kJ|kcal|%)\s*([\d,\.]+|NA)",
                re.IGNORECASE
            )
            for match in nutrient_pattern.finditer(page_text):
                comp_text, unit, val_text = match.groups()
                comp_key = self._normalize_component(comp_text)
                val = self._parse_value(val_text)
                if val is not None:
                    food.nutrients[comp_key] = {
                        "value_per_100g": val,
                        "unit": unit,
                        "original_name": comp_text.strip(),
                    }

        logger.info(f"Alimento: {food.name} ({food.code}) - {len(food.nutrients)} nutrientes")
        return food

    def search_and_fetch(self, query: str, max_results: int = 3) -> list[TBCAFood]:
        """Busca e retorna detalhes dos primeiros resultados."""
        results = self.search(query)
        foods = []
        for r in results[:max_results]:
            url = r.get("url", "")
            if url:
                food = self.fetch_food(url)
                if food:
                    # Enriquecer com dados da busca
                    if not food.name:
                        food.name = r.get("name", "")
                    if not food.code:
                        food.code = r.get("code", "")
                    if not food.group:
                        food.group = r.get("group", "")
                    if not food.scientific_name:
                        food.scientific_name = r.get("scientific_name", "")
                    foods.append(food)
                time.sleep(0.5)
        return foods

    def to_platform_fields(self, food: TBCAFood) -> dict:
        """
        Converte nutrientes TBCA para campos do formulario da plataforma.
        Retorna dict {campo_plataforma: valor_str}.
        """
        fields = {}
        for tbca_key, platform_field in TBCA_TO_PLATFORM.items():
            nutrient = food.nutrients.get(tbca_key)
            if nutrient:
                val = nutrient["value_per_100g"]
                # Formatar com virgula decimal (padrao BR)
                if val == int(val):
                    fields[platform_field] = f"{int(val)},0"
                else:
                    fields[platform_field] = f"{val}".replace(".", ",")
        return fields

    def to_cache(self, food: TBCAFood):
        """Salva alimento no cache SQLite (dados detalhados com nutrientes)."""
        if not self.cache_db_path:
            return
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tbca_foods (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    scientific_name TEXT,
                    group_name TEXT,
                    description TEXT,
                    nutrients_json TEXT,
                    fetched_at REAL
                )
            """)
            conn.execute(
                "INSERT OR REPLACE INTO tbca_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                (food.code, food.name, food.scientific_name,
                 food.group, food.description,
                 json.dumps(food.nutrients, ensure_ascii=False),
                 time.time())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erro ao salvar cache TBCA: {e}")

    def from_cache(self, code: str) -> Optional[TBCAFood]:
        """Busca alimento no cache SQLite."""
        if not self.cache_db_path:
            return None
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            row = conn.execute(
                "SELECT * FROM tbca_foods WHERE code = ?", (code,)
            ).fetchone()
            conn.close()
            if row:
                food = TBCAFood(
                    code=row[0], name=row[1], scientific_name=row[2],
                    group=row[3], description=row[4],
                    nutrients=json.loads(row[5])
                )
                return food
        except Exception:
            pass
        return None

    def search_cached(self, query: str) -> list[TBCAFood]:
        """Busca alimentos no cache por nome (LIKE)."""
        if not self.cache_db_path:
            return []
        try:
            conn = sqlite3.connect(str(self.cache_db_path))
            rows = conn.execute(
                "SELECT * FROM tbca_foods WHERE name LIKE ? OR description LIKE ?",
                (f"%{query}%", f"%{query}%")
            ).fetchall()
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

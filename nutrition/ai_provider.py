"""
Provedores de IA para busca de valores nutricionais.
Suporta: Groq, OpenAI, Claude, Ollama.
Fallback automatico entre provedores.
"""
import json
import re
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NUTRITION_PROMPT_TEMPLATE = """Voce e um especialista em nutricao brasileira. Forneca os valores nutricionais por 100g do alimento "{food_name}".

Retorne APENAS um JSON valido (sem markdown, sem explicacoes) com os seguintes campos:
{{
  "valorEnergetico429": "valor em kcal",
  "carboidratos429": "valor em g",
  "acucaresTotais429": "valor em g",
  "acucaresAdicionados": "valor em g",
  "proteinas429": "valor em g",
  "gordurasTotais429": "valor em g",
  "gordurasSaturadas429": "valor em g",
  "gordurasTrans429": "valor em g",
  "fibraAlimentar429": "valor em g",
  "sodio429": "valor em mg",
  "lactose": "valor em g",
  "galactose": "valor em g",
  "colesterol": "valor em mg",
  "calcio": "valor em mg",
  "ferro": "valor em mg",
  "fosforo": "valor em mg",
  "magnesio": "valor em mg",
  "potassio": "valor em mg",
  "zinco": "valor em mg",
  "vitaminaA": "valor em mcg",
  "vitaminaB1": "valor em mg",
  "vitaminaB2": "valor em mg",
  "vitaminaB3": "valor em mg",
  "vitaminaB6": "valor em mg",
  "vitaminaB9": "valor em mcg",
  "vitaminaB12": "valor em mcg",
  "vitaminaC": "valor em mg",
  "vitaminaD": "valor em mcg",
  "vitaminaE": "valor em mg",
  "vitaminaK": "valor em mcg"
}}

Regras:
- Use ponto como separador decimal (ex: 12.5)
- Use "0" para valores nao disponiveis ou nao aplicaveis
- Seja preciso baseado em tabelas nutricionais oficiais (TBCA/USDA)
- Retorne APENAS o JSON, nada mais
"""

# Campos obrigatorios RDC 429 que a IA deve sempre retornar
MANDATORY_FIELDS = [
    "valorEnergetico429", "carboidratos429", "acucaresTotais429",
    "acucaresAdicionados", "proteinas429", "gordurasTotais429",
    "gordurasSaturadas429", "gordurasTrans429", "fibraAlimentar429",
    "sodio429", "lactose", "galactose",
]

MATCH_PROMPT_TEMPLATE = """Voce e um nutricionista brasileiro verificando associacoes de alimentos.

Para cada par abaixo, verifique se o alimento da plataforma e o mesmo da tabela nutricional.

{pairs}

Retorne APENAS um JSON valido com a lista de resultados:
{{"results": [{{"id": 0, "match": true, "reason": "motivo"}}, ...]}}

Regras:
- "bolo de cookies" NAO e o mesmo que "cookies" (e um bolo)
- "suco de laranja" e o mesmo que "suco de laranja natural"
- "arroz integral" NAO e o mesmo que "arroz branco"
- Se tem ingredientes diferentes, NAO e match
- Se e a mesma coisa com nomes diferentes, SIM e match
- Retorne APENAS o JSON, nada mais"""

VERIFICATION_PROMPT_TEMPLATE = """Voce e um auditor nutricional. Verifique se os valores abaixo sao plausiveis para 100g de "{food_name}".

Valores preenchidos:
{filled_json}

Responda APENAS um JSON valido com:
{{
  "valid": true ou false,
  "issues": ["lista de problemas encontrados, se houver"],
  "suggestions": {{"campo": "valor_correto"}} 
}}

Regras de validacao:
- Calorias devem ser 0-900 kcal/100g (alimentos puros)
- Proteinas 0-100g, Gorduras 0-100g, Carboidratos 0-100g
- Soma approx de calorias: (proteinas*4 + gorduras*9 + carboidratos*4) deve ser proxima do valor calorico
- Gorduras trans geralmente 0 para alimentos naturais
- Sodio < 5000mg para maioria dos alimentos
- Se valid=true e issues=[], os valores estao OK
- Retorne APENAS o JSON, nada mais"""


@dataclass
class VerificationResult:
    """Resultado da verificacao pos-preenchimento."""
    food_name: str
    valid: bool = True
    issues: list = None
    suggestions: dict = None
    values_matched: int = 0
    values_total: int = 0
    dom_match: bool = False
    ai_validated: bool = False
    confidence: float = 0
    duration_ms: int = 0
    error: str = ""

    def __post_init__(self):
        if self.issues is None:
            self.issues = []
        if self.suggestions is None:
            self.suggestions = {}

    @property
    def match_rate(self) -> float:
        if self.values_total == 0:
            return 0
        return (self.values_matched / self.values_total) * 100

    @property
    def summary(self) -> str:
        parts = []
        if self.dom_match:
            parts.append(f"DOM: {self.values_matched}/{self.values_total} campos")
        if self.ai_validated:
            parts.append(f"IA: {'OK' if self.valid else f'{len(self.issues)} problemas'}")
        if self.issues:
            parts.append(f"Issues: {'; '.join(self.issues[:3])}")
        return " | ".join(parts) if parts else "Sem verificacao"


@dataclass
class AIResult:
    """Resultado de uma consulta IA."""
    food_name: str
    provider: str
    fields: dict = None
    raw_response: str = ""
    confidence: float = 0
    duration_ms: int = 0
    error: str = ""

    def __post_init__(self):
        if self.fields is None:
            self.fields = {}

    @property
    def success(self) -> bool:
        return bool(self.fields) and not self.error

    @property
    def has_mandatory(self) -> bool:
        return all(f in self.fields for f in MANDATORY_FIELDS)


class AIProvider(ABC):
    """Interface base para provedores de IA."""

    def __init__(self, name: str, api_key: str = "",
                 model: str = "", base_url: str = "",
                 timeout: int = 30):
        self.name = name
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    @abstractmethod
    def _call_api(self, prompt: str) -> str:
        """Chama a API e retorna a resposta bruta."""
        pass

    def query_nutrition(self, food_name: str) -> AIResult:
        """Busca valores nutricionais via IA."""
        result = AIResult(food_name=food_name, provider=self.name)
        start = time.time()

        try:
            prompt = NUTRITION_PROMPT_TEMPLATE.format(food_name=food_name)
            raw = self._call_api(prompt)
            result.raw_response = raw

            fields = self._parse_json_response(raw)
            if fields:
                result.fields = self._convert_values(fields)
                result.confidence = self._estimate_confidence(result.fields)
            else:
                result.error = "Nao foi possivel extrair JSON da resposta"

        except Exception as e:
            result.error = str(e)
            logger.warning(f"Erro no provedor {self.name}: {e}")

        result.duration_ms = int((time.time() - start) * 1000)
        return result

    def query_verification(self, food_name: str,
                           filled_fields: dict) -> VerificationResult:
        """Verifica se valores preenchidos sao plausiveis via IA."""
        vresult = VerificationResult(food_name=food_name)
        start = time.time()

        try:
            prompt = VERIFICATION_PROMPT_TEMPLATE.format(
                food_name=food_name,
                filled_json=json.dumps(filled_fields, indent=2,
                                       ensure_ascii=False)
            )
            raw = self._call_api(prompt)
            parsed = self._parse_json_response(raw)

            if parsed:
                vresult.valid = parsed.get("valid", True)
                vresult.issues = parsed.get("issues", [])
                vresult.suggestions = parsed.get("suggestions", {})
                vresult.ai_validated = True
                vresult.confidence = 90.0 if vresult.valid else 50.0
            else:
                vresult.error = "Nao foi possivel interpretar resposta IA"

        except Exception as e:
            vresult.error = str(e)
            logger.warning(f"Erro na verificacao IA ({self.name}): {e}")

        vresult.duration_ms = int((time.time() - start) * 1000)
        return vresult

    def _parse_json_response(self, text: str) -> Optional[dict]:
        """Extrai JSON da resposta da IA."""
        text = text.strip()

        # Remover thinking tags (Qwen, etc)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
        text = text.strip()

        # Remover blocos de codigo markdown
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        # Tentar parse direto
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Tentar extrair JSON de texto misto
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Tentar pegar ultimo objeto JSON na resposta
        matches = re.findall(r"\{[^{}]*\}", text, re.DOTALL)
        for m in reversed(matches):
            try:
                return json.loads(m)
            except json.JSONDecodeError:
                continue

        return None

    def _convert_values(self, fields: dict) -> dict:
        """Converte valores string para formato da plataforma (virgula BR)."""
        result = {}
        for key, val in fields.items():
            if not isinstance(val, (str, int, float)):
                continue

            val_str = str(val).strip()
            if val_str.upper() in ("NA", "N/D", "-", "N.D.", "NONE", "NULL", ""):
                continue

            # Limpar valor
            val_str = val_str.replace(",", ".")
            val_str = re.sub(r"[^\d.]", "", val_str)

            try:
                num = float(val_str)
                if num == int(num):
                    result[key] = f"{int(num)},0"
                else:
                    result[key] = f"{num}".replace(".", ",")
            except ValueError:
                continue

        return result

    def _estimate_confidence(self, fields: dict) -> float:
        """Estima confianca baseado na completude dos campos."""
        if not fields:
            return 0

        mandatory_count = sum(1 for f in MANDATORY_FIELDS if f in fields)
        total_count = len(fields)

        mandatory_ratio = mandatory_count / len(MANDATORY_FIELDS)
        total_ratio = min(total_count / 20, 1.0)

        return (mandatory_ratio * 0.7 + total_ratio * 0.3) * 100

    def is_available(self) -> bool:
        """Verifica se o provedor esta configurado."""
        return bool(self.api_key) or self.name == "ollama"


class OpenAIProvider(AIProvider):
    """OpenAI GPT (pago, ~$0.001/req)."""

    def __init__(self, **kwargs):
        super().__init__(name="openai", **kwargs)
        if not self.model:
            self.model = "gpt-4o-mini"

    def _call_api(self, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai nao instalado. "
                             "Execute: pip install openai")

        client = OpenAI(api_key=self.api_key, timeout=self.timeout)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                 "content": "Voce e um nutricionista brasileiro. "
                           "Retorne APENAS JSON valido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        return response.choices[0].message.content

    def is_available(self) -> bool:
        try:
            import openai
            return bool(self.api_key)
        except ImportError:
            return False


class ClaudeProvider(AIProvider):
    """Anthropic Claude (pago)."""

    def __init__(self, **kwargs):
        super().__init__(name="claude", **kwargs)
        if not self.model:
            self.model = "claude-3-haiku-20240307"

    def _call_api(self, prompt: str) -> str:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic nao instalado. "
                             "Execute: pip install anthropic")

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.1,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text

    def is_available(self) -> bool:
        try:
            import anthropic
            return bool(self.api_key)
        except ImportError:
            return False


class OllamaProvider(AIProvider):
    """Ollama (local, gratuito, sem API key)."""

    def __init__(self, **kwargs):
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "http://localhost:11434"
        if not kwargs.get("model"):
            kwargs["model"] = "llama3.2"
        super().__init__(name="ollama", **kwargs)

    def _call_api(self, prompt: str) -> str:
        try:
            import ollama as ollama_lib
        except ImportError:
            # Fallback para requests direto
            import requests
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 1024}
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

        response = ollama_lib.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": 0.1, "num_predict": 1024}
        )
        return response.get("response", "")

    def is_available(self) -> bool:
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False


class GroqProvider(AIProvider):
    """Groq (rapido, gratuito ate 14K req/dia, compativel OpenAI)."""

    def __init__(self, **kwargs):
        super().__init__(name="groq", **kwargs)
        if not self.model:
            self.model = "openai/gpt-oss-20b"
        if not self.base_url:
            self.base_url = "https://api.groq.com/openai/v1"
        self._last_request_time = 0
        self._min_interval = 2.1

    def _call_api(self, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai nao instalado. "
                             "Execute: pip install openai")

        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

        self._last_request_time = time.time()
        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                 "content": "Voce e um nutricionista brasileiro. "
                           "Retorne APENAS JSON valido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    def is_available(self) -> bool:
        return bool(self.api_key)


class NutritionAIFinder:
    """Coordena busca via IA com fallback entre provedores."""

    def __init__(self, providers: list[AIProvider] = None):
        self.providers = providers or []
        self._cache = {}

    def add_provider(self, provider: AIProvider):
        self.providers.append(provider)

    def find(self, food_name: str) -> Optional[dict]:
        """
        Busca valores nutricionais via IA.
        Tenta cada provedor em ordem ate encontrar resultado valido.
        Retorna dict de campos ou None.
        """
        cache_key = food_name.lower().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]

        for provider in self.providers:
            if not provider.is_available():
                continue

            logger.info(f"Buscando via IA ({provider.name}): {food_name}")
            result = provider.query_nutrition(food_name)

            if result.success and result.fields:
                logger.info(
                    f"IA ({provider.name}) retornou {len(result.fields)} campos "
                    f"para '{food_name}' (confianca: {result.confidence:.0f}%)"
                )
                self._cache[cache_key] = result.fields
                return result.fields
            else:
                logger.warning(
                    f"IA ({provider.name}) falhou para '{food_name}': "
                    f"{result.error}"
                )

        return None

    def find_with_result(self, food_name: str) -> AIResult:
        """Busca e retorna resultado detalhado."""
        for provider in self.providers:
            if not provider.is_available():
                continue

            result = provider.query_nutrition(food_name)
            if result.success and result.fields:
                return result

        return AIResult(food_name=food_name, provider="none",
                       error="Nenhum provedor disponivel ou retornou dados")

    def test_provider(self, provider_name: str = None) -> dict:
        """Testa um provedor especifico com alimento de exemplo."""
        test_foods = ["arroz", "feijao", "leite"]

        for provider in self.providers:
            if provider_name and provider.name != provider_name:
                continue
            if not provider.is_available():
                continue

            food = test_foods[0]
            result = provider.query_nutrition(food)
            return {
                "provider": provider.name,
                "available": True,
                "success": result.success,
                "fields_count": len(result.fields),
                "confidence": result.confidence,
                "duration_ms": result.duration_ms,
                "error": result.error,
            }

        return {"provider": provider_name or "all",
                "available": False, "error": "Nenhum provedor disponivel"}

    def get_available_providers(self) -> list[str]:
        """Retorna nomes dos provedores disponiveis."""
        return [p.name for p in self.providers if p.is_available()]

    def clear_cache(self):
        """Limpa cache de consultas."""
        self._cache.clear()

    def verify_fill(self, food_name: str, expected: dict,
                    readback: dict) -> VerificationResult:
        """
        Verifica preenchimento pos-save.
        1. Compara expected vs readback (DOM match)
        2. Valida plausibilidade nutricional via IA
        """
        vresult = VerificationResult(food_name=food_name)

        # Camada 1: Comparacao DOM
        if expected and readback:
            matched = 0
            for key, expected_val in expected.items():
                rb_val = readback.get(key, "")
                if self._values_equal(expected_val, rb_val):
                    matched += 1
            vresult.values_matched = matched
            vresult.values_total = len(expected)
            vresult.dom_match = (matched == len(expected))
        elif expected and not readback:
            vresult.issues.append("Nao foi possivel reler campos apos salvar")

        # Camada 2: Validacao IA
        if self.providers:
            for provider in self.providers:
                if not provider.is_available():
                    continue
                try:
                    ai_result = provider.query_verification(
                        food_name, expected
                    )
                    if ai_result.ai_validated:
                        vresult.valid = ai_result.valid
                        vresult.issues.extend(ai_result.issues)
                        vresult.suggestions.update(ai_result.suggestions)
                        vresult.ai_validated = True
                        vresult.confidence = ai_result.confidence
                        vresult.duration_ms = ai_result.duration_ms
                        break
                except Exception as e:
                    logger.warning(f"Verificacao IA falhou ({provider.name}): {e}")

        return vresult

    def verify_match(self, platform_name: str, tbca_name: str) -> dict:
        """Verifica se a associacao entre plataforma e TBCA esta correta.

        Retorna: {"match": bool, "reason": str, "provider": str}
        """
        for provider in self.providers:
            if not provider.is_available():
                continue
            try:
                prompt = MATCH_PROMPT_TEMPLATE.format(
                    platform_name=platform_name,
                    tbca_name=tbca_name,
                )
                raw = provider._call_api(prompt)
                parsed = provider._parse_json_response(raw)
                if parsed and "match" in parsed:
                    return {
                        "match": bool(parsed["match"]),
                        "reason": parsed.get("reason", ""),
                        "provider": provider.name,
                    }
            except Exception as e:
                logger.warning(f"Verificacao de match IA falhou ({provider.name}): {e}")

        return {"match": True, "reason": "IA indisponivel, assumindo match", "provider": "none"}

    def verify_matches_batch(self, pairs: list[dict], batch_size: int = 20) -> list[dict]:
        """Verifica multiplos matches em batch (muito mais rapido).

        Args:
            pairs: [{"id": 0, "platform": "bolo de cookies", "tbca": "Cookies"}, ...]
            batch_size: quantos pares por request (20 = ~15s para 200 alimentos)

        Returns:
            [{"id": 0, "match": true, "reason": "...", "provider": "groq"}, ...]
        """
        if not pairs:
            return []

        for provider in self.providers:
            if not provider.is_available():
                continue

            all_results = []
            try:
                for start in range(0, len(pairs), batch_size):
                    batch = pairs[start:start + batch_size]

                    lines = []
                    for item in batch:
                        lines.append(
                            f"{item['id']}. Plataforma: \"{item['platform']}\" | "
                            f"Tabela: \"{item['tbca']}\""
                        )
                    pairs_text = "\n".join(lines)

                    prompt = MATCH_PROMPT_TEMPLATE.format(pairs=pairs_text)
                    raw = provider._call_api(prompt)
                    parsed = provider._parse_json_response(raw)

                    if parsed and "results" in parsed:
                        for r in parsed["results"]:
                            all_results.append({
                                "id": r.get("id", 0),
                                "match": bool(r.get("match", True)),
                                "reason": r.get("reason", ""),
                                "provider": provider.name,
                            })
                    else:
                        for item in batch:
                            all_results.append({
                                "id": item["id"],
                                "match": True,
                                "reason": "Parse falhou, assumindo match",
                                "provider": provider.name,
                            })

                    logger.info(
                        f"  Batch {start // batch_size + 1}: "
                        f"{len(batch)} verificados, "
                        f"{sum(1 for r in all_results if not r['match'])} suspeitos"
                    )

                return all_results

            except Exception as e:
                logger.warning(f"Batch verification falhou ({provider.name}): {e}")
                continue

        return [{"id": p["id"], "match": True,
                 "reason": "IA indisponivel", "provider": "none"} for p in pairs]

    @staticmethod
    def _values_equal(expected: str, actual: str) -> bool:
        """Compara dois valores normalizando formato brasileiro."""
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


def create_default_finder(settings) -> NutritionAIFinder:
    """Cria NutritionAIFinder com provedores configurados nas settings.

    Prioridade: Groq (rapido, 14K/dia) > Gemini (20/dia) > Ollama (local).
    """
    from config.settings import AIConfig

    finder = NutritionAIFinder()
    ai = settings.ai

    if not ai.enabled:
        return finder

    # Sempre adicionar Groq se chave disponivel
    if ai.groq_api_key:
        finder.add_provider(GroqProvider(
            api_key=ai.groq_api_key,
            model=ai.groq_model or "",
            timeout=ai.timeout,
        ))

    # Adicionar provedor principal configurado
    provider_classes = {
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "ollama": OllamaProvider,
        "groq": GroqProvider,
    }

    if ai.provider != "groq":
        cls = provider_classes.get(ai.provider)
        if cls:
            kwargs = dict(api_key=ai.api_key, model=ai.model,
                         base_url=ai.base_url, timeout=ai.timeout)
            if ai.provider == "ollama":
                kwargs["model"] = ai.ollama_model or ai.model
                kwargs["base_url"] = ai.ollama_url or ai.base_url
            provider = cls(**kwargs)
            finder.add_provider(provider)

    # Adicionar Ollama como fallback final (local, sem limite)
    if ai.ollama_url or ai.provider != "ollama":
        ollama = OllamaProvider(
            base_url=ai.ollama_url or "",
            model=ai.ollama_model or "",
            timeout=ai.timeout,
        )
        if ollama.is_available():
            finder.add_provider(ollama)

    return finder

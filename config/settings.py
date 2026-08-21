"""
Configurações do sistema de automação nutricional.
Gerencia configurações, credenciais e parâmetros.
"""
import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
BACKUPS_DIR = BASE_DIR / "backups"

for d in [DATA_DIR, LOGS_DIR, CACHE_DIR, BACKUPS_DIR]:
    d.mkdir(exist_ok=True)


@dataclass
class PlatformConfig:
    url: str = "https://balancas.tecnosoftapps.com"
    login_url: str = "https://balancas.tecnosoftapps.com/login"
    nutri_url: str = "https://balancas.tecnosoftapps.com/nutri"
    username: str = ""
    password: str = ""
    user_data_dir: str = str(DATA_DIR / "browser_profile")
    headless: bool = True
    timeout: int = 30000
    slow_mo: int = 0


@dataclass
class TBCAConfig:
    site_url: str = "https://www.tbca.net.br"
    api_base_url: str = "https://parse.bot"
    api_scraper_id: str = "d776a04f-b80d-4e68-a9e9-365f2bee2eb0"
    api_key: str = ""
    cache_ttl: int = 86400  # 24 horas
    enabled: bool = True


@dataclass
class USDAConfig:
    api_key: str = "DEMO_KEY"
    enabled: bool = True
    base_url: str = "https://api.nal.usda.gov/fdc/v1"
    cache_ttl: int = 86400  # 24 horas


@dataclass
class MatchingConfig:
    high_confidence: float = 80.0
    medium_confidence: float = 60.0
    auto_confirm_threshold: float = 80.0
    ask_user_threshold: float = 60.0


@dataclass
class AutomationConfig:
    mode: str = "DRY_RUN"  # READ_ONLY, DRY_RUN, TEST, LIVE
    max_retries: int = 3
    retry_delay: float = 2.0
    backoff_factor: float = 2.0
    operation_interval: float = 1.0
    max_concurrent: int = 1
    confirm_before_save: bool = True
    confirm_before_modify: bool = True
    update_interval_hours: float = 24.0
    auto_check_updates: bool = True


@dataclass
class AIConfig:
    """Configuracao de IA para busca nutricional."""
    enabled: bool = False
    provider: str = "gemini"  # gemini, openai, claude, ollama, groq
    api_key: str = ""
    model: str = ""  # Modelo especifico (vazio = padrao do provedor)
    base_url: str = ""  # Para ollama ou custom
    auto_fallback: bool = True  # Buscar via IA automaticamente para no_match
    confidence_threshold: float = 70.0
    max_retries: int = 2
    timeout: int = 30
    groq_api_key: str = ""
    groq_model: str = ""  # vazio = llama-3.3-70b-versatile
    ollama_model: str = ""  # vazio = llama3.2
    ollama_url: str = ""  # vazio = http://localhost:11434


@dataclass
class LogConfig:
    level: str = "INFO"
    file: str = str(LOGS_DIR / "app.log")
    max_bytes: int = 2 * 1024 * 1024
    backup_count: int = 5
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


@dataclass
class Settings:
    platform: PlatformConfig = field(default_factory=PlatformConfig)
    tbca: TBCAConfig = field(default_factory=TBCAConfig)
    usda: USDAConfig = field(default_factory=USDAConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    automation: AutomationConfig = field(default_factory=AutomationConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    log: LogConfig = field(default_factory=LogConfig)

    def save(self, path: Optional[Path] = None):
        path = path or CONFIG_DIR / "config.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        path = path or CONFIG_DIR / "config.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            settings = cls()
            if "platform" in data:
                settings.platform = PlatformConfig(**data["platform"])
            if "tbca" in data:
                settings.tbca = TBCAConfig(**data["tbca"])
            if "usda" in data:
                settings.usda = USDAConfig(**data["usda"])
            if "matching" in data:
                settings.matching = MatchingConfig(**data["matching"])
            if "automation" in data:
                settings.automation = AutomationConfig(**data["automation"])
            if "ai" in data:
                settings.ai = AIConfig(**data["ai"])
            if "log" in data:
                settings.log = LogConfig(**data["log"])
            return settings
        return cls()

    def load_env(self):
        """Carrega credenciais do arquivo .env"""
        env_path = CONFIG_DIR / ".env"
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key == "PLATFORM_USERNAME":
                            self.platform.username = value
                        elif key == "PLATFORM_PASSWORD":
                            self.platform.password = value
                        elif key == "TBCA_API_KEY":
                            self.tbca.api_key = value
                        elif key == "USDA_API_KEY":
                            self.usda.api_key = value
                        elif key == "AI_PROVIDER":
                            self.ai.provider = value
                        elif key == "AI_API_KEY":
                            self.ai.api_key = value
                        elif key == "AI_MODEL":
                            self.ai.model = value
                        elif key == "AI_ENABLED":
                            self.ai.enabled = value.lower() in ("true", "1", "yes")
                        elif key == "GROQ_API_KEY":
                            self.ai.groq_api_key = value
                        elif key == "GROQ_MODEL":
                            self.ai.groq_model = value
                        elif key == "OLLAMA_MODEL":
                            self.ai.ollama_model = value
                        elif key == "OLLAMA_URL":
                            self.ai.ollama_url = value

    def save_env(self):
        """Salva credenciais no arquivo .env"""
        env_path = CONFIG_DIR / ".env"
        lines = [
            "# Automação Nutricional - Credenciais",
            "# NÃO COMMITAR ESTE ARQUIVO",
            "",
            "# Plataforma Tecnosoft",
            f'PLATFORM_USERNAME="{self.platform.username}"',
            f'PLATFORM_PASSWORD="{self.platform.password}"',
            "",
            "# TBCA API (Parse)",
            f'TBCA_API_KEY="{self.tbca.api_key}"',
            "",
            "# USDA API",
            f'USDA_API_KEY="{self.usda.api_key}"',
            "",
            "# AI Provider",
            f'AI_PROVIDER="{self.ai.provider}"',
            f'AI_API_KEY="{self.ai.api_key}"',
            f'AI_MODEL="{self.ai.model}"',
            f'AI_ENABLED="{str(self.ai.enabled).lower()}"',
            "",
            "# Groq (gratuito, 14K req/dia)",
            f'GROQ_API_KEY="{self.ai.groq_api_key}"',
            f'GROQ_MODEL="{self.ai.groq_model}"',
            "",
            "# Ollama (local, gratuito)",
            f'OLLAMA_MODEL="{self.ai.ollama_model}"',
            f'OLLAMA_URL="{self.ai.ollama_url}"',
            "",
        ]
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

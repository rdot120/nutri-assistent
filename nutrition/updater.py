"""
Verificador periodico de atualizacoes nas fontes de dados.
Checa TBCA e USDA por novos alimentos ou alteracoes.
"""
import time
import logging
import threading
import sqlite3
import json
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field

from config.settings import Settings, DATA_DIR
from nutrition.tbca import TBCAScraper
from nutrition.usda import USDAScraper

logger = logging.getLogger(__name__)

CACHE_DB = DATA_DIR / "tbca_cache.db"


@dataclass
class UpdateResult:
    """Resultado de uma verificacao de atualizacao."""
    source: str  # "tbca" ou "usda"
    checked_at: float = 0
    total_items: int = 0
    new_items: int = 0
    updated_items: int = 0
    errors: int = 0
    message: str = ""
    details: list = field(default_factory=list)


class UpdateChecker:
    """
    Verifica periodico de atualizacoes nas fontes de dados.
    Roda em thread separada e notifica a GUI via callback.
    """

    def __init__(self, settings: Settings, callback: Callable = None):
        self.settings = settings
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_check = {"tbca": 0, "usda": 0}
        self._check_interval = settings.automation.update_interval_hours * 3600

        # Scrapers
        self.tbca = TBCAScraper(cache_db_path=CACHE_DB)
        self.usda = USDAScraper(
            api_key=settings.usda.api_key,
            cache_db_path=CACHE_DB,
        )

    def start(self):
        """Inicia verificacao periodica."""
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Verificador de atualizacoes iniciado")

    def stop(self):
        """Para verificacao periodica."""
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Verificador de atualizacoes parado")

    def check_now(self):
        """Executa verificacao imediata (nao bloqueante)."""
        threading.Thread(target=self._check_all, daemon=True).start()

    def _run_loop(self):
        """Loop principal de verificacao periodica."""
        while not self._stop_event.is_set():
            try:
                self._check_all()
            except Exception as e:
                logger.error("Erro na verificacao: %s", e)
                self._notify("error", str(e))

            # Aguardar proxima verificacao
            self._stop_event.wait(self._check_interval)

    def _check_all(self):
        """Verifica todas as fontes habilitadas."""
        if self.settings.tbca.enabled:
            self._check_tbca()

    def _check_tbca(self):
        """Verifica TBCA por atualizacoes."""
        self._notify("checking", "TBCA")
        result = UpdateResult(source="tbca", checked_at=time.time())

        try:
            # Carregar listing atual
            current_listing = self.tbca.load_listing_index()
            current_codes = {item["code"] for item in current_listing}
            result.total_items = len(current_listing)

            # Buscar listing atualizado do site
            new_listing = self.tbca.fetch_all_listings()
            new_codes = {item["code"] for item in new_listing}

            # Encontrar novos
            added = new_codes - current_codes
            removed = current_codes - new_codes

            result.new_items = len(added)
            result.updated_items = len(removed)

            if added:
                for code in added:
                    item = next((i for i in new_listing if i["code"] == code), None)
                    if item:
                        result.details.append({
                            "code": code,
                            "name": item.get("name", ""),
                            "type": "new",
                        })

            if removed:
                for code in removed:
                    item = next((i for i in current_listing if i["code"] == code), None)
                    if item:
                        result.details.append({
                            "code": code,
                            "name": item.get("name", ""),
                            "type": "removed",
                        })

            # Atualizar cache se houver mudancas
            if added or removed:
                self.tbca.save_listing_index(new_listing)
                result.message = (
                    f"TBCA: {len(added)} novos, {len(removed)} removidos"
                )
            else:
                result.message = "TBCA: sem atualizacoes"

            self._last_check["tbca"] = time.time()

        except Exception as e:
            result.errors += 1
            result.message = f"TBCA erro: {e}"
            logger.error("Erro ao verificar TBCA: %s", e)

        self._notify("result", result)

    def _notify(self, event: str, data):
        """Notifica a GUI via callback."""
        if self.callback:
            try:
                self.callback(event, data)
            except Exception as e:
                logger.error("Erro ao notificar GUI: %s", e)

    def get_status(self) -> dict:
        """Retorna status da verificacao."""
        return {
            "running": self._running,
            "last_check_tbca": self._last_check.get("tbca", 0),
            "interval_hours": self._check_interval / 3600,
        }

    def force_check_tbca(self):
        """Forca verificacao imediata do TBCA."""
        threading.Thread(target=self._check_tbca, daemon=True).start()

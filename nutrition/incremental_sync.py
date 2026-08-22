"""
Sincronizacao incremental de fontes de dados.
Detecta apenas itens novos ou alterados no TBCA e USDA.
"""
import time
import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from contextlib import contextmanager

from nutrition.tbca import TBCAScraper
from nutrition.usda import USDAScraper

logger = logging.getLogger(__name__)


@dataclass
class SyncState:
    """Estado de sincronizacao de uma fonte."""
    source: str
    last_sync_at: float = 0
    last_full_sync_at: float = 0
    item_count: int = 0
    checksum: str = ""
    new_since_last: int = 0
    updated_since_last: int = 0
    removed_since_last: int = 0


@dataclass
class SyncResult:
    """Resultado de uma operacao de sincronizacao."""
    source: str
    sync_type: str  # "full", "incremental"
    started_at: float = 0
    finished_at: float = 0
    total_items: int = 0
    new_items: int = 0
    updated_items: int = 0
    removed_items: int = 0
    errors: int = 0
    details: list = field(default_factory=list)
    message: str = ""

    @property
    def duration(self) -> float:
        return self.finished_at - self.started_at


class IncrementalSync:
    """Gerencia sincronizacao incremental de TBCA e USDA."""

    def __init__(self, db_path: Path, cache_db_path: Path):
        self.db_path = db_path
        self.cache_db_path = cache_db_path
        self.tbca = TBCAScraper(cache_db_path=cache_db_path)
        self.usda = USDAScraper(cache_db_path=cache_db_path)
        self._init_db()

    def _init_db(self):
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sync_state (
                    source TEXT PRIMARY KEY,
                    last_sync_at REAL,
                    last_full_sync_at REAL,
                    item_count INTEGER DEFAULT 0,
                    checksum TEXT DEFAULT '',
                    new_since_last INTEGER DEFAULT 0,
                    updated_since_last INTEGER DEFAULT 0,
                    removed_since_last INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    sync_type TEXT,
                    started_at REAL,
                    finished_at REAL,
                    total_items INTEGER DEFAULT 0,
                    new_items INTEGER DEFAULT 0,
                    updated_items INTEGER DEFAULT 0,
                    removed_items INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    message TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_sync_history_source
                    ON sync_history(source);
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_state(self, source: str) -> SyncState:
        """Retorna estado de sincronizacao de uma fonte."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sync_state WHERE source=?",
                (source,)
            ).fetchone()
            if row:
                return SyncState(**dict(row))
        return SyncState(source=source)

    def sync_tbca(self, force_full: bool = False) -> SyncResult:
        """Sincroniza TBCA (incremental ou full)."""
        result = SyncResult(source="tbca", sync_type="incremental",
                            started_at=time.time())
        state = self.get_state("tbca")

        try:
            current_listing = self.tbca.load_listing_index()
            current_map = {item["code"]: item for item in current_listing}

            if force_full or state.last_full_sync_at == 0:
                result.sync_type = "full"
                new_listing = self.tbca.fetch_all_listings()
            else:
                new_listing = self.tbca.fetch_all_listings()

            new_map = {item["code"]: item for item in new_listing}
            current_codes = set(current_map.keys())
            new_codes = set(new_map.keys())

            added = new_codes - current_codes
            removed = current_codes - new_codes

            potentially_updated = current_codes & new_codes
            updated = set()
            for code in potentially_updated:
                old = current_map[code]
                new = new_map[code]
                if old.get("name") != new.get("name") or old.get("url") != new.get("url"):
                    updated.add(code)

            result.total_items = len(new_listing)
            result.new_items = len(added)
            result.updated_items = len(updated)
            result.removed_items = len(removed)

            for code in added:
                item = new_map[code]
                result.details.append({
                    "code": code, "name": item.get("name", ""),
                    "type": "new"
                })
            for code in updated:
                item = new_map[code]
                result.details.append({
                    "code": code, "name": item.get("name", ""),
                    "type": "updated"
                })

            if added or updated or removed or force_full:
                self.tbca.save_listing_index(new_listing)

            state.last_sync_at = time.time()
            if force_full or state.last_full_sync_at == 0:
                state.last_full_sync_at = time.time()
            state.item_count = len(new_listing)
            state.new_since_last = len(added)
            state.updated_since_last = len(updated)
            state.removed_since_last = len(removed)
            self._save_state(state)

            result.message = (
                f"TBCA: {len(added)} novos, {len(updated)} atualizados, "
                f"{len(removed)} removidos"
            )
            result.finished_at = time.time()

        except Exception as e:
            result.errors += 1
            result.message = f"Erro TBCA: {e}"
            result.finished_at = time.time()
            logger.error("Erro na sincronizacao TBCA: %s", e)

        self._save_history(result)
        return result

    def sync_usda(self, since: float = 0) -> SyncResult:
        """Sincroniza USDA (endpoint de mudancas indisponivel na API)."""
        result = SyncResult(source="usda", sync_type="incremental",
                            started_at=time.time())
        state = self.get_state("usda")

        # A API publica do USDA nao expoe endpoint de mudancas;
        # /food/changes responde 400. A busca (/foods/search)
        # permanece funcional e nao depende desta sincronizacao.
        result.message = (
            "USDA: sincronizacao de mudancas indisponivel "
            "(endpoint nao exposto pela API)"
        )
        state.last_sync_at = time.time()
        self._save_state(state)
        result.finished_at = time.time()

        self._save_history(result)
        return result

    def _save_state(self, state: SyncState):
        """Salva estado de sincronizacao."""
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sync_state "
                "(source, last_sync_at, last_full_sync_at, item_count, "
                "checksum, new_since_last, updated_since_last, removed_since_last) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (state.source, state.last_sync_at, state.last_full_sync_at,
                 state.item_count, state.checksum, state.new_since_last,
                 state.updated_since_last, state.removed_since_last)
            )

    def _save_history(self, result: SyncResult):
        """Salva historico de sincronizacao."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO sync_history "
                "(source, sync_type, started_at, finished_at, total_items, "
                "new_items, updated_items, removed_items, errors, message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (result.source, result.sync_type, result.started_at,
                 result.finished_at, result.total_items, result.new_items,
                 result.updated_items, result.removed_items, result.errors,
                 result.message)
            )

    def get_history(self, source: str = None, limit: int = 50) -> list[dict]:
        """Retorna historico de sincronizacao."""
        with self.connect() as conn:
            if source:
                rows = conn.execute(
                    "SELECT * FROM sync_history WHERE source=? "
                    "ORDER BY started_at DESC LIMIT ?",
                    (source, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sync_history "
                    "ORDER BY started_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def needs_sync(self, source: str) -> bool:
        """Verifica se uma fonte precisa de sincronizacao."""
        state = self.get_state(source)
        if state.last_sync_at == 0:
            return True
        elapsed = time.time() - state.last_sync_at
        return elapsed > 86400  # 24 horas

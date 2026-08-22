"""
Armazenamento local com SQLite.
Cache, histórico e configurações persistidas.
"""
import sqlite3
import json
import logging
import time
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """Gerencia banco de dados SQLite."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Inicializa schema do banco."""
        with self.connect() as conn:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL
                );

                CREATE TABLE IF NOT EXISTS match_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform_name TEXT NOT NULL,
                    tbca_name TEXT NOT NULL,
                    tbca_code TEXT,
                    confidence REAL,
                    confirmed_by_user INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS operation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    food_name TEXT,
                    food_code TEXT,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details TEXT,
                    duration_ms INTEGER,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS nutritionals (
                    id INTEGER PRIMARY KEY,
                    codigo_nutricional TEXT,
                    descricao TEXT,
                    data_json TEXT NOT NULL,
                    synced_at REAL
                );

                CREATE INDEX IF NOT EXISTS idx_cache_expires
                    ON cache(expires_at);
                CREATE INDEX IF NOT EXISTS idx_match_platform
                    ON match_history(platform_name);
                CREATE INDEX IF NOT EXISTS idx_log_created
                    ON operation_log(created_at);

                CREATE TABLE IF NOT EXISTS backup_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    food_name TEXT NOT NULL,
                    food_index INTEGER,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_backup_session
                    ON backup_fields(session_id);

                CREATE TABLE IF NOT EXISTS manual_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    food_name TEXT NOT NULL UNIQUE,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_manual_food
                    ON manual_entries(food_name);

                CREATE TABLE IF NOT EXISTS validated_values (
                    food_name TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    fields_count INTEGER NOT NULL DEFAULT 0,
                    captured_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_validated_food
                    ON validated_values(food_name);
            """)
            logger.debug("Banco de dados inicializado")

    @contextmanager
    def connect(self):
        """Context manager para conexão."""
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

    # === Cache ===

    def cache_get(self, key: str) -> Optional[Any]:
        """Busca valor no cache."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,)
            ).fetchone()
            if row:
                if row["expires_at"] and row["expires_at"] < time.time():
                    conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                    return None
                return json.loads(row["value"])
        return None

    def cache_set(self, key: str, value: Any, ttl: int = 86400):
        """Salva valor no cache."""
        expires_at = time.time() + ttl if ttl else None
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, created_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (key, json.dumps(value, ensure_ascii=False), time.time(), expires_at)
            )

    def cache_clear(self):
        """Limpa cache expirado."""
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                (time.time(),)
            )

    # === Match History ===

    def save_match(self, platform_name: str, tbca_name: str,
                   tbca_code: str = None, confidence: float = 0,
                   confirmed_by_user: bool = False):
        """Salva correspondência confirmada."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO match_history "
                "(platform_name, tbca_name, tbca_code, confidence, confirmed_by_user, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (platform_name, tbca_name, tbca_code, confidence,
                 1 if confirmed_by_user else 0, time.time())
            )

    def get_saved_match(self, platform_name: str) -> Optional[dict]:
        """Busca correspondência salva para um alimento."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT tbca_name, tbca_code, confidence "
                "FROM match_history WHERE platform_name = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (platform_name,)
            ).fetchone()
            if row:
                return dict(row)
        return None

    # === Operation Log ===

    def log_operation(self, food_name: str = None, food_code: str = None,
                      operation: str = "", status: str = "success",
                      details: str = None, duration_ms: int = None):
        """Registra operação no log."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO operation_log "
                "(food_name, food_code, operation, status, details, duration_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (food_name, food_code, operation, status, details,
                 duration_ms, time.time())
            )

    def get_operation_history(self, limit: int = 100,
                              food_name: str = None) -> list[dict]:
        """Busca histórico de operações."""
        with self.connect() as conn:
            if food_name:
                rows = conn.execute(
                    "SELECT * FROM operation_log "
                    "WHERE food_name LIKE ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (f"%{food_name}%", limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM operation_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    # === Nutritionals ===

    def save_nutritional(self, nutri_id: int, codigo: str = None,
                         descricao: str = None, data: dict = None):
        """Salva dados nutricionais."""
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nutritionals "
                "(id, codigo_nutricional, descricao, data_json, synced_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (nutri_id, codigo, descricao,
                 json.dumps(data, ensure_ascii=False), time.time())
            )

    def get_nutritional(self, nutri_id: int) -> Optional[dict]:
        """Busca dados nutricionais."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM nutritionals WHERE id = ?",
                (nutri_id,)
            ).fetchone()
            if row:
                result = dict(row)
                result["data"] = json.loads(result["data_json"])
                return result
        return None

    def get_stats(self) -> dict:
        """Retorna estatisticas do banco."""
        with self.connect() as conn:
            return {
                "cache_entries": conn.execute(
                    "SELECT COUNT(*) FROM cache"
                ).fetchone()[0],
                "matches": conn.execute(
                    "SELECT COUNT(*) FROM match_history"
                ).fetchone()[0],
                "operations": conn.execute(
                    "SELECT COUNT(*) FROM operation_log"
                ).fetchone()[0],
                "nutritionals": conn.execute(
                    "SELECT COUNT(*) FROM nutritionals"
                ).fetchone()[0],
            }

    # === Backup Fields (para desfazer) ===

    def save_backup(self, session_id: str, food_name: str,
                    food_index: int, field_name: str,
                    old_value: str, new_value: str):
        """Salva valor anterior de um campo para poder desfazer."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO backup_fields "
                "(session_id, food_name, food_index, field_name, "
                "old_value, new_value, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, food_name, food_index,
                 field_name, old_value, new_value, time.time())
            )

    def get_backups(self, session_id: str) -> list[dict]:
        """Retorna todos os backups de uma sessao."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backup_fields "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_backups_by_food(self, session_id: str,
                            food_name: str) -> list[dict]:
        """Retorna backups de um alimento especifico."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backup_fields "
                "WHERE session_id = ? AND food_name = ? "
                "ORDER BY id ASC",
                (session_id, food_name)
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_backups(self, session_id: str):
        """Limpa todos os backups de uma sessao."""
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM backup_fields WHERE session_id = ?",
                (session_id,)
            )

    def get_distinct_foods_backed_up(self, session_id: str) -> list[str]:
        """Retorna nomes dos alimentos que tem backup."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT food_name FROM backup_fields "
                "WHERE session_id = ? ORDER BY food_name",
                (session_id,)
            ).fetchall()
            return [r[0] for r in rows]

    # === Manual Entries (entradas manuais) ===

    def save_manual_entry(self, food_name: str, data: dict):
        """Salva ou atualiza entrada manual de um alimento."""
        now = time.time()
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM manual_entries WHERE food_name = ?",
                (food_name,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE manual_entries SET data_json = ?, updated_at = ? "
                    "WHERE food_name = ?",
                    (json.dumps(data, ensure_ascii=False), now, food_name)
                )
            else:
                conn.execute(
                    "INSERT INTO manual_entries "
                    "(food_name, data_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (food_name, json.dumps(data, ensure_ascii=False), now, now)
                )

    def get_manual_entry(self, food_name: str) -> Optional[dict]:
        """Busca entrada manual de um alimento."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM manual_entries WHERE food_name = ?",
                (food_name,)
            ).fetchone()
            if row:
                return json.loads(row["data_json"])
        return None

    def get_all_manual_entries(self) -> dict[str, dict]:
        """Retorna todas as entradas manuais."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT food_name, data_json FROM manual_entries "
                "ORDER BY food_name"
            ).fetchall()
            return {r["food_name"]: json.loads(r["data_json"]) for r in rows}

    def delete_manual_entry(self, food_name: str):
        """Deleta entrada manual de um alimento."""
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM manual_entries WHERE food_name = ?",
                (food_name,)
            )

    def clear_manual_entries(self):
        """Limpa todas as entradas manuais."""
        with self.connect() as conn:
            conn.execute("DELETE FROM manual_entries")

    def get_manual_entry_count(self) -> int:
        """Retorna numero de entradas manuais."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM manual_entries"
            ).fetchone()
            return row[0]

    # === Valores validados (capturados da plataforma) ===

    def save_validated_value(self, food_name: str, data: dict):
        """Arquiva valores conferidos pela nutricionista na plataforma."""
        now = time.time()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO validated_values "
                "(food_name, data_json, fields_count, captured_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(food_name) DO UPDATE SET "
                "data_json = excluded.data_json, "
                "fields_count = excluded.fields_count, "
                "captured_at = excluded.captured_at",
                (food_name, json.dumps(data, ensure_ascii=False),
                 len(data), now)
            )

    def get_validated_value(self, food_name: str) -> Optional[dict]:
        """Busca valores arquivados de um alimento."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM validated_values "
                "WHERE food_name = ?",
                (food_name,)
            ).fetchone()
            if row:
                return json.loads(row["data_json"])
        return None

    def get_all_validated_entries(self) -> dict[str, dict]:
        """Retorna todos os valores arquivados {nome: campos}."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT food_name, data_json FROM validated_values "
                "ORDER BY food_name"
            ).fetchall()
            return {r["food_name"]: json.loads(r["data_json"])
                    for r in rows}

    def has_validated_value(self, food_name: str) -> bool:
        """Verifica se ja existe arquivo para o alimento."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM validated_values WHERE food_name = ?",
                (food_name,)
            ).fetchone()
            return row is not None

    def get_validated_count(self) -> int:
        """Retorno numero de alimentos com valores arquivados."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM validated_values"
            ).fetchone()
            return row[0]

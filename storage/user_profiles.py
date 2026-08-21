"""
Perfis de usuario e log de auditoria.
Suporte a multiplos usuarios com configuracoes proprias.
"""
import json
import time
import sqlite3
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """Perfil de usuario."""
    user_id: str = ""
    username: str = ""
    display_name: str = ""
    role: str = "operator"  # admin, operator, viewer
    created_at: float = 0
    last_login: float = 0
    preferences: dict = field(default_factory=dict)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def can_modify(self) -> bool:
        return self.role in ("admin", "operator")


@dataclass
class AuditEntry:
    """Entrada de log de auditoria."""
    id: int = 0
    user_id: str = ""
    action: str = ""
    resource: str = ""
    details: str = ""
    timestamp: float = 0
    ip_address: str = ""

    @property
    def time_str(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S",
                             time.localtime(self.timestamp))


class UserManager:
    """Gerencia perfis de usuario."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._audit = AuditLogger(db_path)
        self._init_db()

    def _init_db(self):
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    display_name TEXT,
                    role TEXT DEFAULT 'operator',
                    created_at REAL,
                    last_login REAL,
                    preferences TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    action TEXT,
                    resource TEXT,
                    details TEXT DEFAULT '',
                    timestamp REAL,
                    ip_address TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_audit_user
                    ON audit_log(user_id);
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_action
                    ON audit_log(action);
            """)

            # Criar usuario padrao se nao existe
            row = conn.execute(
                "SELECT COUNT(*) FROM user_profiles"
            ).fetchone()
            if row[0] == 0:
                now = time.time()
                conn.execute(
                    "INSERT INTO user_profiles "
                    "(user_id, username, display_name, role, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    ("default", "admin", "Administrador", "admin", now)
                )

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

    def create_user(self, username: str, display_name: str,
                    role: str = "operator") -> UserProfile:
        """Cria novo usuario."""
        import uuid
        user_id = str(uuid.uuid4())[:8]
        now = time.time()

        prefs = {
            "theme": "light",
            "auto_approve_threshold": 80,
            "default_mode": "DRY_RUN",
        }

        with self.connect() as conn:
            conn.execute(
                "INSERT INTO user_profiles "
                "(user_id, username, display_name, role, created_at, preferences) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, display_name, role, now,
                 json.dumps(prefs))
            )

        self._audit.log("system", "user_create", f"user:{user_id}",
                   f"Criado usuario {username} ({role})")

        return UserProfile(
            user_id=user_id, username=username,
            display_name=display_name, role=role,
            created_at=now, preferences=prefs,
        )

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        """Busca usuario por ID."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_profiles WHERE user_id=?",
                (user_id,)
            ).fetchone()
            if row:
                return self._row_to_profile(row)
        return None

    def get_user_by_username(self, username: str) -> Optional[UserProfile]:
        """Busca usuario por nome."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_profiles WHERE username=?",
                (username,)
            ).fetchone()
            if row:
                return self._row_to_profile(row)
        return None

    def get_all_users(self) -> list[UserProfile]:
        """Retorna todos os usuarios."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM user_profiles ORDER BY username"
            ).fetchall()
            return [self._row_to_profile(r) for r in rows]

    def update_user(self, user_id: str, **kwargs):
        """Atualiza dados de um usuario."""
        allowed = {"display_name", "role", "preferences"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        set_parts = []
        values = []
        for key, val in updates.items():
            if key == "preferences":
                val = json.dumps(val)
            set_parts.append(f"{key}=?")
            values.append(val)

        values.append(user_id)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE user_profiles SET {', '.join(set_parts)} "
                "WHERE user_id=?",
                values
            )

        self._audit.log("system", "user_update", f"user:{user_id}",
                   f"Atualizado: {', '.join(updates.keys())}")

    def login(self, username: str) -> Optional[UserProfile]:
        """Registra login de usuario."""
        user = self.get_user_by_username(username)
        if user:
            with self.connect() as conn:
                conn.execute(
                    "UPDATE user_profiles SET last_login=? WHERE user_id=?",
                    (time.time(), user.user_id)
                )
            user.last_login = time.time()
            self._audit.log("system", "user_login", f"user:{user.user_id}",
                       f"Login: {username}")
        return user

    def delete_user(self, user_id: str):
        """Deleta usuario."""
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM user_profiles WHERE user_id=?",
                (user_id,)
            )
        self._audit.log("system", "user_delete", f"user:{user_id}", "Usuario removido")

    def _row_to_profile(self, row) -> UserProfile:
        """Converte Row para UserProfile."""
        data = dict(row)
        prefs = json.loads(data.get("preferences", "{}"))
        return UserProfile(
            user_id=data["user_id"],
            username=data.get("username", ""),
            display_name=data.get("display_name", ""),
            role=data.get("role", "operator"),
            created_at=data.get("created_at", 0),
            last_login=data.get("last_login", 0),
            preferences=prefs,
        )


class AuditLogger:
    """Log de auditoria para rastrear acoes."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

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

    def log(self, user_id: str, action: str, resource: str,
            details: str = "", ip_address: str = ""):
        """Registra acao na auditoria."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO audit_log "
                "(user_id, action, resource, details, timestamp, ip_address) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, action, resource, details, time.time(), ip_address)
            )

    def get_entries(self, user_id: str = None, action: str = None,
                    limit: int = 100) -> list[dict]:
        """Busca entradas de auditoria."""
        with self.connect() as conn:
            conditions = []
            params = []
            if user_id:
                conditions.append("user_id=?")
                params.append(user_id)
            if action:
                conditions.append("action=?")
                params.append(action)

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)

            rows = conn.execute(
                f"SELECT * FROM audit_log {where} "
                "ORDER BY timestamp DESC LIMIT ?",
                params
            ).fetchall()
            return [dict(r) for r in rows]

    def get_action_summary(self, days: int = 30) -> dict:
        """Retorna resumo de acoes por periodo."""
        since = time.time() - (days * 86400)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT action, COUNT(*) as cnt "
                "FROM audit_log WHERE timestamp > ? "
                "GROUP BY action ORDER BY cnt DESC",
                (since,)
            ).fetchall()
            return {r["action"]: r["cnt"] for r in rows}

    def clear_old(self, days: int = 90):
        """Remove entradas antigas."""
        cutoff = time.time() - (days * 86400)
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM audit_log WHERE timestamp < ?",
                (cutoff,)
            )

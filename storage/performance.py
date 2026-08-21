"""
Historico de performance e metricas.
Rastreia tempo por operacao, taxa de sucesso, e gera relatorios.
"""
import csv
import time
import json
import sqlite3
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class SessionMetrics:
    """Metricas de uma sessao de operacao."""
    session_id: str
    started_at: float = 0
    finished_at: float = 0
    total_foods: int = 0
    matched: int = 0
    filled: int = 0
    saved: int = 0
    errors: int = 0
    no_match: int = 0
    avg_time_per_item: float = 0
    total_duration: float = 0
    source_distribution: dict = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if self.total_foods == 0:
            return 0
        return (self.saved / self.total_foods) * 100

    @property
    def error_rate(self) -> float:
        if self.total_foods == 0:
            return 0
        return (self.errors / self.total_foods) * 100

    @property
    def match_rate(self) -> float:
        if self.total_foods == 0:
            return 0
        return (self.matched / self.total_foods) * 100


@dataclass
class ItemMetrics:
    """Metricas de um item individual."""
    session_id: str
    food_name: str
    food_code: str = ""
    match_source: str = ""
    confidence: float = 0
    status: str = ""
    fields_filled: int = 0
    duration_ms: int = 0
    error_message: str = ""
    timestamp: float = 0


class PerformanceTracker:
    """Rastreia performance de operacoes de preenchimento."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS performance_sessions (
                    session_id TEXT PRIMARY KEY,
                    started_at REAL,
                    finished_at REAL,
                    total_foods INTEGER DEFAULT 0,
                    matched INTEGER DEFAULT 0,
                    filled INTEGER DEFAULT 0,
                    saved INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    no_match INTEGER DEFAULT 0,
                    avg_time_per_item REAL DEFAULT 0,
                    total_duration REAL DEFAULT 0,
                    source_distribution TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS performance_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    food_name TEXT,
                    food_code TEXT,
                    match_source TEXT,
                    confidence REAL DEFAULT 0,
                    status TEXT,
                    fields_filled INTEGER DEFAULT 0,
                    duration_ms INTEGER DEFAULT 0,
                    error_message TEXT DEFAULT '',
                    timestamp REAL
                );
                CREATE INDEX IF NOT EXISTS idx_perf_session
                    ON performance_items(session_id);
                CREATE INDEX IF NOT EXISTS idx_perf_status
                    ON performance_items(status);
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

    def start_session(self, session_id: str) -> SessionMetrics:
        """Inicia uma nova sessao de metricas."""
        metrics = SessionMetrics(
            session_id=session_id,
            started_at=time.time(),
        )
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO performance_sessions "
                "(session_id, started_at) VALUES (?, ?)",
                (session_id, metrics.started_at)
            )
        return metrics

    def finish_session(self, metrics: SessionMetrics):
        """Finaliza sessao e calcula metricas."""
        metrics.finished_at = time.time()
        metrics.total_duration = metrics.finished_at - metrics.started_at

        if metrics.total_foods > 0:
            metrics.avg_time_per_item = metrics.total_duration / metrics.total_foods

        with self.connect() as conn:
            conn.execute(
                "UPDATE performance_sessions SET "
                "finished_at=?, total_foods=?, matched=?, filled=?, "
                "saved=?, errors=?, no_match=?, avg_time_per_item=?, "
                "total_duration=?, source_distribution=? "
                "WHERE session_id=?",
                (metrics.finished_at, metrics.total_foods, metrics.matched,
                 metrics.filled, metrics.saved, metrics.errors, metrics.no_match,
                 metrics.avg_time_per_item, metrics.total_duration,
                 json.dumps(metrics.source_distribution), metrics.session_id)
            )

    def log_item(self, item: ItemMetrics):
        """Registra metricas de um item."""
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO performance_items "
                "(session_id, food_name, food_code, match_source, "
                "confidence, status, fields_filled, duration_ms, "
                "error_message, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item.session_id, item.food_name, item.food_code,
                 item.match_source, item.confidence, item.status,
                 item.fields_filled, item.duration_ms,
                 item.error_message, item.timestamp)
            )

    def get_sessions(self, limit: int = 50) -> list[dict]:
        """Retorna historico de sessoes."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM performance_sessions "
                "ORDER BY started_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session_items(self, session_id: str) -> list[dict]:
        """Retorna itens de uma sessao."""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM performance_items "
                "WHERE session_id=? ORDER BY timestamp",
                (session_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_global_stats(self) -> dict:
        """Retorna estatisticas globais."""
        with self.connect() as conn:
            sessions = conn.execute(
                "SELECT COUNT(*) as cnt, SUM(total_foods) as total, "
                "SUM(saved) as saved, SUM(errors) as errors, "
                "AVG(avg_time_per_item) as avg_time "
                "FROM performance_sessions WHERE finished_at IS NOT NULL"
            ).fetchone()

            items = conn.execute(
                "SELECT match_source, COUNT(*) as cnt, "
                "AVG(confidence) as avg_conf, "
                "AVG(duration_ms) as avg_dur "
                "FROM performance_items GROUP BY match_source"
            ).fetchall()

            error_items = conn.execute(
                "SELECT food_name, error_message "
                "FROM performance_items WHERE status='error' "
                "ORDER BY timestamp DESC LIMIT 20"
            ).fetchall()

            return {
                "total_sessions": sessions["cnt"] or 0,
                "total_foods_processed": sessions["total"] or 0,
                "total_saved": sessions["saved"] or 0,
                "total_errors": sessions["errors"] or 0,
                "avg_time_per_item": sessions["avg_time"] or 0,
                "source_stats": [
                    {"source": r["match_source"], "count": r["cnt"],
                     "avg_confidence": r["avg_conf"],
                     "avg_duration_ms": r["avg_dur"]}
                    for r in items
                ],
                "recent_errors": [
                    {"food": r["food_name"], "error": r["error_message"]}
                    for r in error_items
                ],
            }

    def export_session_csv(self, session_id: str, path: Path) -> bool:
        """Exporta itens de uma sessao para CSV."""
        items = self.get_session_items(session_id)
        if not items:
            return False

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "food_name", "food_code", "match_source",
                    "confidence", "status", "fields_filled",
                    "duration_ms", "error_message", "timestamp"
                ])
                writer.writeheader()
                for item in items:
                    writer.writerow({
                        "food_name": item.get("food_name", ""),
                        "food_code": item.get("food_code", ""),
                        "match_source": item.get("match_source", ""),
                        "confidence": item.get("confidence", 0),
                        "status": item.get("status", ""),
                        "fields_filled": item.get("fields_filled", 0),
                        "duration_ms": item.get("duration_ms", 0),
                        "error_message": item.get("error_message", ""),
                        "timestamp": time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(item.get("timestamp", 0))
                        ),
                    })
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar CSV: {e}")
            return False

    def export_global_csv(self, path: Path) -> bool:
        """Exporta todas as sessoes para CSV."""
        sessions = self.get_sessions(limit=1000)
        if not sessions:
            return False

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "session_id", "started_at", "finished_at",
                    "total_foods", "matched", "filled", "saved",
                    "errors", "avg_time_per_item", "total_duration"
                ])
                writer.writeheader()
                for s in sessions:
                    writer.writerow({
                        "session_id": s.get("session_id", ""),
                        "started_at": time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(s.get("started_at", 0))
                        ),
                        "finished_at": time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            time.localtime(s.get("finished_at", 0))
                        ) if s.get("finished_at") else "",
                        "total_foods": s.get("total_foods", 0),
                        "matched": s.get("matched", 0),
                        "filled": s.get("filled", 0),
                        "saved": s.get("saved", 0),
                        "errors": s.get("errors", 0),
                        "avg_time_per_item": round(
                            s.get("avg_time_per_item", 0), 2
                        ),
                        "total_duration": round(
                            s.get("total_duration", 0), 2
                        ),
                    })
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar CSV global: {e}")
            return False

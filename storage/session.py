"""
Persistencia de sessao: salva/carrega dados de platform_foods e processed
para retomar de onde parou ao reabrir o app.
"""
import json
import time
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SESSION_VERSION = 1


class SessionManager:
    """Gerencia persistencia da sessao (platform_foods + processed)."""

    def __init__(self, data_dir: Path):
        self.session_path = data_dir / "session.json"

    def save(self, platform_foods: list[dict], processed: list) -> bool:
        """Salva sessao atual em JSON."""
        try:
            data = {
                "version": SESSION_VERSION,
                "saved_at": time.time(),
                "platform_foods": platform_foods,
                "processed": [self._serialize_pf(pf) for pf in processed],
            }

            tmp_path = str(self.session_path) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            os.replace(tmp_path, str(self.session_path))
            logger.info(
                f"Sessao salva: {len(platform_foods)} alimentos, "
                f"{len(processed)} processados"
            )
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar sessao: {e}")
            return False

    def load(self) -> Optional[dict]:
        """Carrega sessao do JSON. Retorna dict com platform_foods e processed, ou None."""
        if not self.session_path.exists():
            return None

        try:
            with open(self.session_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("version") != SESSION_VERSION:
                logger.warning(
                    f"Versao da sessao incompativel: {data.get('version')} "
                    f"(esperado {SESSION_VERSION})"
                )
                return None

            platform_foods = data.get("platform_foods", [])
            processed_raw = data.get("processed", [])

            logger.info(
                f"Sessao carregada: {len(platform_foods)} alimentos, "
                f"{len(processed_raw)} processados "
                f"(salvo em {time.strftime('%d/%m/%Y %H:%M', time.localtime(data.get('saved_at', 0)))})"
            )

            return {
                "platform_foods": platform_foods,
                "processed_raw": processed_raw,
            }

        except Exception as e:
            logger.error(f"Erro ao carregar sessao: {e}")
            return None

    def has_session(self) -> bool:
        """Verifica se existe sessao salva."""
        return self.session_path.exists()

    def clear(self):
        """Remove sessao salva."""
        if self.session_path.exists():
            self.session_path.unlink()
            logger.info("Sessao limpa")

    def _serialize_pf(self, pf) -> dict:
        """Serializa um ProcessedFood para dict JSON-friendly."""
        match_dict = None
        if pf.match:
            match_dict = {
                "platform_name": pf.match.platform_name,
                "tbca_name": pf.match.tbca_name,
                "tbca_code": pf.match.tbca_code,
                "confidence": pf.match.confidence,
                "match_method": pf.match.match_method,
                "tbca_nutrients": pf.match.tbca_nutrients or {},
            }

        return {
            "platform_name": pf.platform_name,
            "match": match_dict,
            "fields_to_fill": pf.fields_to_fill or {},
            "status": pf.status,
            "skip_reason": pf.skip_reason or "",
            "suggestion": pf.suggestion or "",
            "error": pf.error or "",
        }

    def deserialize_pf(self, raw: dict):
        """Deserializa dict para ProcessedFood (importa aqui para evitar circular)."""
        from automation.orchestrator import ProcessedFood
        from nutrition.matcher import MatchResult

        pf = ProcessedFood(
            platform_name=raw["platform_name"],
            status=raw.get("status", "pending"),
            skip_reason=raw.get("skip_reason", ""),
            suggestion=raw.get("suggestion", ""),
            error=raw.get("error", ""),
            fields_to_fill=raw.get("fields_to_fill") or None,
        )

        match_data = raw.get("match")
        if match_data:
            pf.match = MatchResult(
                platform_name=match_data["platform_name"],
                tbca_name=match_data["tbca_name"],
                tbca_code=match_data["tbca_code"],
                confidence=match_data.get("confidence", 0),
                match_method=match_data.get("match_method", ""),
                tbca_nutrients=match_data.get("tbca_nutrients", {}),
            )

        return pf

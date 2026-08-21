"""
Testes automatizados para o Nutri Assistent.
Executa: python -m pytest tests/ -v
"""
import sys
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Settings, PlatformConfig, MatchingConfig
from storage.db import Database
from nutrition.matcher import FoodMatcher, normalize_food_name, extract_food_base
from nutrition.tbca import TBCAScraper, COMPONENT_MAP, TBCA_TO_PLATFORM
from nutrition.importer import SpreadsheetImporter, COLUMN_MAPPING
from storage.performance import PerformanceTracker, SessionMetrics
from storage.user_profiles import UserManager, AuditLogger
from nutrition.incremental_sync import IncrementalSync
from nutrition.dedup import Deduplicator


@pytest.fixture
def tmp_db(tmp_path):
    """Fixture para banco temporario."""
    return Database(tmp_path / "test.db")


@pytest.fixture
def perf_tracker(tmp_path):
    """Fixture para performance tracker."""
    return PerformanceTracker(tmp_path / "perf.db")


@pytest.fixture
def user_manager(tmp_path):
    """Fixture para user manager."""
    return UserManager(tmp_path / "users.db")


class TestMatcher:
    """Testes do matcher de alimentos."""

    def test_normalize_food_name(self):
        assert normalize_food_name("Abacate, Polpa") == "abacate polpa"
        assert normalize_food_name("FRANGO INTEIRO") == "frango inteiro"
        assert normalize_food_name("Leite (desnatado)") == "leite desnatado"
        assert normalize_food_name("  Arroz  ") == "arroz"

    def test_extract_food_base(self):
        assert extract_food_base("Carne, frango, inteiro") == "carne frango inteiro"
        assert extract_food_base("Arroz") == "arroz"

    def test_matcher_exact(self):
        matcher = FoodMatcher()
        foods = [
            {"code": "BRC001", "name": "Abacate, polpa", "nutrients": {}},
            {"code": "BRC002", "name": "Arroz, integral", "nutrients": {}},
        ]
        matcher.load_tbca_index(foods)

        result = matcher.match("Abacate, polpa")
        assert result is not None
        assert result.confidence == 100.0
        assert result.tbca_code == "BRC001"

    def test_matcher_no_match(self):
        matcher = FoodMatcher()
        foods = [
            {"code": "BRC001", "name": "Abacate, polpa", "nutrients": {}},
        ]
        matcher.load_tbca_index(foods)

        result = matcher.match("Chocolate Belga Premium")
        assert result is None

    def test_matcher_structured(self):
        matcher = FoodMatcher(high_threshold=60, medium_threshold=40)
        foods = [
            {"code": "BRC001", "name": "Carne, frango, inteiro, cru", "nutrients": {}},
            {"code": "BRC002", "name": "Carne, bovina, acem", "nutrients": {}},
        ]
        matcher.load_tbca_index(foods)

        result = matcher.match("FRANGO INTEIRO")
        assert result is not None
        assert "frango" in result.tbca_name.lower()


class TestDatabase:
    """Testes do banco de dados."""

    def test_cache_operations(self, tmp_db):
        tmp_db.cache_set("test_key", {"data": 123}, ttl=3600)
        result = tmp_db.cache_get("test_key")
        assert result == {"data": 123}

    def test_cache_expiry(self, tmp_db):
        tmp_db.cache_set("expired", "value", ttl=-1)
        result = tmp_db.cache_get("expired")
        assert result is None

    def test_manual_entries(self, tmp_db):
        tmp_db.save_manual_entry("Test Food", {"calories": "100"})
        entry = tmp_db.get_manual_entry("Test Food")
        assert entry == {"calories": "100"}

        entries = tmp_db.get_all_manual_entries()
        assert "Test Food" in entries

        tmp_db.delete_manual_entry("Test Food")
        assert tmp_db.get_manual_entry("Test Food") is None

    def test_backup_fields(self, tmp_db):
        tmp_db.save_backup("sess1", "food1", 0, "field1", "old", "new")
        backups = tmp_db.get_backups("sess1")
        assert len(backups) == 1
        assert backups[0]["field_name"] == "field1"

    def test_operation_log(self, tmp_db):
        tmp_db.log_operation("food1", "BRC001", "fill", "success")
        history = tmp_db.get_operation_history()
        assert len(history) == 1


class TestTBCAScraper:
    """Testes do scraper TBCA."""

    def test_parse_value(self):
        scraper = TBCAScraper()
        assert scraper._parse_value("12,5") == 12.5
        assert scraper._parse_value("0,0") == 0.0
        assert scraper._parse_value("NA") is None
        assert scraper._parse_value("N/D") is None
        assert scraper._parse_value("tr") == 0.0

    def test_component_map_coverage(self):
        essential = [
            "energia", "proteina", "carboidrato total", "lipidios",
            "fibra alimentar", "sodio", "calcio", "ferro",
        ]
        for comp in essential:
            assert comp in COMPONENT_MAP, f"Componente '{comp}' nao mapeado"

    def test_tbca_to_platform_coverage(self):
        mandatory_fields = [
            "valorEnergetico429", "carboidratos429", "proteinas429",
            "gordurasTotais429", "gordurasSaturadas429", "gordurasTrans429",
            "fibraAlimentar429", "sodio429",
        ]
        for field in mandatory_fields:
            assert field in TBCA_TO_PLATFORM.values(), \
                f"Campo '{field}' nao mapeado no TBCA_TO_PLATFORM"


class TestImporter:
    """Testes do importador."""

    def test_column_detection(self):
        importer = SpreadsheetImporter()
        headers = ["Nome", "Calorias", "Proteina", "Gorduras Totais"]
        mapping = importer.detect_columns(headers)

        assert "_name" in mapping.values()
        assert "valorEnergetico429" in mapping.values()
        assert "proteinas429" in mapping.values()
        assert "gordurasTotais429" in mapping.values()

    def test_clean_value(self):
        importer = SpreadsheetImporter()
        assert importer._clean_value("12,5 g") == 12.5
        assert importer._clean_value("100 mg") == 100.0
        assert importer._clean_value("NA") is None
        assert importer._clean_value("-") is None
        assert importer._clean_value("0,0") == 0.0

    def test_import_paste(self):
        importer = SpreadsheetImporter()
        text = """
Energia: 100 kcal
Proteina: 5 g
Gorduras Totais: 2 g
Sodio: 150 mg
"""
        result = importer.import_paste(text, "Test Food")
        assert result.food_name == "Test Food"
        assert result.fields.get("valorEnergetico429") == 100.0
        assert result.fields.get("proteinas429") == 5.0

    def test_format_for_platform(self):
        importer = SpreadsheetImporter()
        fields = {"valorEnergetico429": 100.0, "proteinas429": 5.5}
        result = importer.format_for_platform(fields)
        assert result["valorEnergetico429"] == "100,0"
        assert result["proteinas429"] == "5,5"


class TestPerformance:
    """Testes de performance tracker."""

    def test_session_lifecycle(self, perf_tracker):
        metrics = perf_tracker.start_session("test-001")
        assert metrics.session_id == "test-001"

        metrics.total_foods = 10
        metrics.saved = 8
        metrics.errors = 2
        perf_tracker.finish_session(metrics)

        sessions = perf_tracker.get_sessions()
        assert len(sessions) == 1
        assert sessions[0]["total_foods"] == 10

    def test_item_metrics(self, perf_tracker):
        perf_tracker.start_session("test-002")

        item = SessionMetrics(session_id="test-002")
        from storage.performance import ItemMetrics
        item_m = ItemMetrics(
            session_id="test-002",
            food_name="Test Food",
            status="saved",
            duration_ms=1500,
            timestamp=time.time(),
        )
        perf_tracker.log_item(item_m)

        items = perf_tracker.get_session_items("test-002")
        assert len(items) == 1

    def test_global_stats(self, perf_tracker):
        stats = perf_tracker.get_global_stats()
        assert "total_sessions" in stats
        assert "total_foods_processed" in stats


class TestUserProfiles:
    """Testes de perfis de usuario."""

    def test_create_user(self, user_manager):
        user = user_manager.create_user("test_user", "Test User", "operator")
        assert user.username == "test_user"
        assert user.role == "operator"

    def test_login(self, user_manager):
        user_manager.create_user("login_test", "Login Test")
        logged = user_manager.login("login_test")
        assert logged is not None
        assert logged.last_login > 0

    def test_default_admin(self, user_manager):
        users = user_manager.get_all_users()
        assert len(users) >= 1
        assert users[0].role == "admin"


class TestDedup:
    """Testes de deduplicacao."""

    def test_find_duplicates(self):
        dedup = Deduplicator(similarity_threshold=80)
        foods = [
            {"name": "Arroz Tipo 1"},
            {"name": "Arroz Tipo 2"},
            {"name": "Feijao Carioca"},
            {"name": "Feijao Preto"},
            {"name": "Chocolate Premium"},
        ]
        groups = dedup.find_duplicates(foods)
        assert len(groups) >= 1

    def test_exact_duplicates(self):
        dedup = Deduplicator(similarity_threshold=80)
        foods = [
            {"name": "Arroz Integral"},
            {"name": "ARROZ INTEGRAL"},
        ]
        groups = dedup.find_duplicates(foods)
        assert len(groups) == 1
        assert groups[0].count == 2


class TestIncrementalSync:
    """Testes de sincronizacao incremental."""

    def test_needs_sync(self, tmp_path):
        sync = IncrementalSync(tmp_path / "sync.db", tmp_path / "cache.db")
        assert sync.needs_sync("tbca") is True


class TestAIProvider:
    """Testes de provedores IA."""

    def test_ai_result_creation(self):
        from nutrition.ai_provider import AIResult
        result = AIResult(
            food_name="arroz",
            provider="gemini",
            fields={"carboidratos429": "28.2"},
            confidence=75.0,
            duration_ms=1200
        )
        assert result.success is True
        assert result.fields["carboidratos429"] == "28.2"

    def test_ai_result_error(self):
        from nutrition.ai_provider import AIResult
        result = AIResult(
            food_name="arroz",
            provider="gemini",
            error="Timeout"
        )
        assert result.success is False
        assert result.error == "Timeout"

    def test_parse_json_response(self):
        from nutrition.ai_provider import OpenAIProvider
        provider = OpenAIProvider(api_key="fake")
        response_text = json.dumps({
            "descricaoProduto": "Arroz",
            "valorEnergetico429": "130",
            "carboidratos429": "28.2",
            "proteinas429": "2.7",
            "gordurasTotais429": "0.3",
            "sodio429": "2"
        })
        fields = provider._parse_json_response(response_text)
        assert "valorEnergetico429" in fields
        assert fields["carboidratos429"] == "28.2"

    def test_parse_json_response_invalid_json(self):
        from nutrition.ai_provider import OpenAIProvider
        provider = OpenAIProvider(api_key="fake")
        fields = provider._parse_json_response("not json at all")
        assert fields is None or len(fields) == 0

    def test_provider_availability_no_key(self):
        from nutrition.ai_provider import OpenAIProvider
        provider = OpenAIProvider(api_key="")
        assert provider.is_available() is False

    def test_provider_availability_with_key(self):
        from nutrition.ai_provider import AIProvider
        class DummyProvider(AIProvider):
            def _call_api(self, prompt):
                return ""
        provider = DummyProvider(name="dummy", api_key="some-key")
        assert provider.is_available() is True

    def test_provider_availability_openai_no_lib(self):
        from nutrition.ai_provider import OpenAIProvider
        provider = OpenAIProvider(api_key="fake-key-123")
        try:
            import openai
            assert provider.is_available() is True
        except ImportError:
            assert provider.is_available() is False

    def test_ollama_available(self):
        from nutrition.ai_provider import OllamaProvider
        provider = OllamaProvider()
        assert isinstance(provider.is_available(), bool)

    def test_create_default_finder(self):
        from nutrition.ai_provider import create_default_finder, NutritionAIFinder
        from config.settings import Settings
        settings = Settings()
        finder = create_default_finder(settings)
        assert isinstance(finder, NutritionAIFinder)

    def test_create_finder_custom_config(self):
        from nutrition.ai_provider import (
            create_default_finder, NutritionAIFinder
        )
        from config.settings import Settings
        settings = Settings()
        settings.ai.enabled = True
        settings.ai.provider = "gemini"
        settings.ai.api_key = ""
        settings.ai.auto_fallback = False
        finder = create_default_finder(settings)
        assert isinstance(finder, NutritionAIFinder)
        providers = finder.get_available_providers()
        assert len(providers) == 0


class TestVerification:
    """Testes de verificacao pos-preenchimento."""

    def test_verification_result_creation(self):
        from nutrition.ai_provider import VerificationResult
        vr = VerificationResult(
            food_name="arroz",
            valid=True,
            dom_match=True,
            values_matched=10,
            values_total=10,
        )
        assert vr.valid is True
        assert vr.dom_match is True
        assert vr.match_rate == 100.0

    def test_verification_result_with_issues(self):
        from nutrition.ai_provider import VerificationResult
        vr = VerificationResult(
            food_name="feijao",
            valid=False,
            issues=["Calorias muito altas", "Proteinas negativas"],
            values_matched=8,
            values_total=10,
        )
        assert vr.valid is False
        assert len(vr.issues) == 2
        assert vr.match_rate == 80.0

    def test_values_equal_normalization(self):
        from nutrition.ai_provider import NutritionAIFinder
        assert NutritionAIFinder._values_equal("28,2", "28.2") is True
        assert NutritionAIFinder._values_equal("130,0", "130") is True
        assert NutritionAIFinder._values_equal("0,3", "0.3") is True
        assert NutritionAIFinder._values_equal("28,2", "30,0") is False

    def test_verify_fill_no_ai(self):
        from nutrition.ai_provider import NutritionAIFinder
        finder = NutritionAIFinder()
        expected = {"valorEnergetico429": "130", "carboidratos429": "28,2"}
        readback = {"valorEnergetico429": "130", "carboidratos429": "28,2"}
        vr = finder.verify_fill("arroz", expected, readback)
        assert vr.dom_match is True
        assert vr.values_matched == 2
        assert vr.values_total == 2

    def test_verify_fill_mismatch(self):
        from nutrition.ai_provider import NutritionAIFinder
        finder = NutritionAIFinder()
        expected = {"valorEnergetico429": "130", "carboidratos429": "28,2"}
        readback = {"valorEnergetico429": "130", "carboidratos429": "50,0"}
        vr = finder.verify_fill("arroz", expected, readback)
        assert vr.dom_match is False
        assert vr.values_matched == 1

    def test_simple_equal(self):
        from automation.orchestrator import Orchestrator
        assert Orchestrator._simple_equal("28,2", "28.2") is True
        assert Orchestrator._simple_equal("130,0", "130") is True
        assert Orchestrator._simple_equal("28,2", "50,0") is False
        assert Orchestrator._simple_equal("", "130") is False

    def test_verification_summary(self):
        from nutrition.ai_provider import VerificationResult
        vr = VerificationResult(
            food_name="arroz",
            valid=True,
            dom_match=True,
            ai_validated=True,
            values_matched=10,
            values_total=10,
        )
        summary = vr.summary
        assert "DOM" in summary
        assert "IA" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

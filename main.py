"""
Automacao Nutricional - Main Entry Point
Sistema de automacao para preenchimento de dados nutricionais.
"""
import sys
import json
import logging
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import Settings, DATA_DIR
from storage.db import Database
from browser.session import SessionManager

logger = logging.getLogger("nutri_auto")


def setup_logging(settings: Settings):
    """Configura sistema de logs."""
    from logging.handlers import RotatingFileHandler

    formatter = logging.Formatter(settings.log.format)

    file_handler = RotatingFileHandler(
        settings.log.file,
        maxBytes=settings.log.max_bytes,
        backupCount=settings.log.backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log.level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def cmd_test(settings: Settings):
    """Testa conexao com a plataforma."""
    print("=" * 60)
    print("AUTOMACAO NUTRICIONAL - Teste de Conexao")
    print("=" * 60)

    session = SessionManager(
        user_data_dir=settings.platform.user_data_dir,
        headless=settings.platform.headless,
        slow_mo=settings.platform.slow_mo,
        timeout=settings.platform.timeout,
    )

    try:
        print("\n[1/4] Iniciando navegador...")
        session.start()
        print("  OK: Navegador iniciado")

        print(f"\n[2/4] Testando login em: {settings.platform.login_url}")
        success = session.login(
            login_url=settings.platform.login_url,
            username=settings.platform.username,
            password=settings.platform.password,
        )

        if success:
            print("  OK: Login realizado com sucesso")
        else:
            print("  FALHA: Login nao funcionou")
            return False

        print(f"\n[3/4] Navegando para: {settings.platform.nutri_url}")
        session.navigate(settings.platform.nutri_url)
        time.sleep(3)
        print(f"  URL atual: {session.page.url}")

        cards_count = session.page.evaluate("""
            () => document.querySelectorAll('[data-slot="popover-trigger"]').length
        """)
        print(f"  Cards encontrados: {cards_count}")

        print("\n[4/4] Verificando sessao...")
        is_valid = session.check_session_valid(
            settings.platform.login_url,
            ['button:has-text("Aplicativo de nutricionais")']
        )
        print(f"  Sessao valida: {'SIM' if is_valid else 'NAO'}")

        print("\n--- Amostra de alimentos ---")
        foods = session.page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
                return Array.from(cards).slice(0, 10).map(c => c.textContent.trim());
            }
        """)
        for i, food in enumerate(foods, 1):
            print(f"  {i}. {food}")

        print("\n" + "=" * 60)
        print("TESTE CONCLUIDO COM SUCESSO")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\nERRO: {e}")
        logger.exception("Erro durante teste de conexao")
        return False

    finally:
        session.stop()


def cmd_tbca_search(settings: Settings):
    """Busca alimentos no TBCA e mostra resultados."""
    from nutrition.tbca import TBCAScraper

    scraper = TBCAScraper(cache_db_path=DATA_DIR / "tbca_cache.db")

    query = input("Buscar no TBCA (nome do alimento): ").strip()
    if not query:
        print("Busca vazia")
        return

    print(f"\nBuscando '{query}' no TBCA...")
    results = scraper.search(query)

    if not results:
        print("Nenhum resultado encontrado")
        return

    print(f"\nEncontrados {len(results)} resultados:")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['code']}] {r['name']}")

    # Buscar detalhes do primeiro
    choice = input("\nVer detalhes de qual? (numero ou Enter para pular): ").strip()
    if choice and choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            food = scraper.fetch_food(results[idx]["url"])
            if food:
                print(f"\n{'='*60}")
                print(f"Alimento: {food.name}")
                print(f"Codigo: {food.code}")
                print(f"Grupo: {food.group}")
                print(f"Cientifico: {food.scientific_name}")
                print(f"Descricao: {food.description}")
                print(f"\nNutrientes ({len(food.nutrients)}):")
                for key, data in sorted(food.nutrients.items()):
                    print(f"  {key}: {data['value_per_100g']} {data['unit']}")
                print(f"{'='*60}")

                # Converter para campos da plataforma
                fields = scraper.to_platform_fields(food)
                print(f"\nCampos da plataforma ({len(fields)}):")
                for field, val in fields.items():
                    print(f"  {field} = {val}")

                # Salvar no cache
                scraper.to_cache(food)
                print("\nSalvo no cache local")


def cmd_tbca_build_index(settings: Settings):
    """Constoi indice TBCA a partir da plataforma."""
    from nutrition.tbca import TBCAScraper
    from nutrition.matcher import FoodMatcher

    scraper = TBCAScraper(cache_db_path=DATA_DIR / "tbca_cache.db")
    session = SessionManager(
        user_data_dir=settings.platform.user_data_dir,
        headless=settings.platform.headless,
        slow_mo=settings.platform.slow_mo,
        timeout=settings.platform.timeout,
    )

    try:
        print("Iniciando navegador...")
        session.start()
        session.login(
            login_url=settings.platform.login_url,
            username=settings.platform.username,
            password=settings.platform.password,
        )
        session.navigate(settings.platform.nutri_url)
        time.sleep(3)

        from browser.platform import PlatformInteraction
        platform = PlatformInteraction(session.page)

        foods = platform.get_all_foods()
        print(f"\n{len(foods)} nutricionais na plataforma")

        # Usar primeiras palavras como termos de busca unicos
        search_terms = set()
        for f in foods:
            base = f["name"].split(",")[0].strip()
            if len(base) > 3:
                search_terms.add(base)

        print(f"{len(search_terms)} termos de busca unicos")
        print(f"\nBuscando no TBCA (pode demorar)...")

        all_foods = []
        for i, term in enumerate(sorted(search_terms)):
            print(f"  [{i+1}/{len(search_terms)}] {term}...", end=" ", flush=True)
            found = scraper.search_and_fetch(term, max_results=2)
            for food in found:
                scraper.to_cache(food)
                all_foods.append(food)
            print(f"{len(found)} encontrados")
            time.sleep(0.5)

        print(f"\nTotal TBCA: {len(all_foods)} alimentos salvos no cache")

    finally:
        session.stop()


def cmd_match(settings: Settings):
    """Testa matching entre plataforma e TBCA."""
    from nutrition.tbca import TBCAScraper
    from nutrition.matcher import FoodMatcher

    scraper = TBCAScraper(cache_db_path=DATA_DIR / "tbca_cache.db")
    matcher = FoodMatcher(
        high_threshold=settings.matching.high_confidence,
        medium_threshold=settings.matching.medium_confidence,
    )

    # Carregar indice do cache
    import sqlite3
    try:
        conn = sqlite3.connect(str(DATA_DIR / "tbca_cache.db"))
        rows = conn.execute("SELECT code, name, nutrients_json FROM tbca_foods").fetchall()
        conn.close()
    except Exception:
        rows = []

    if not rows:
        print("Cache TBCA vazio. Execute 'tbca_build_index' primeiro.")
        return

    from nutrition.tbca import TBCAFood
    foods = [TBCAFood(code=r[0], name=r[1], nutrients=json.loads(r[2])) for r in rows]
    matcher.load_tbca_index(foods)
    print(f"Indice TBCA: {len(foods)} alimentos")

    # Testar com nomes do teclado
    print("\nDigite nomes de alimentos da plataforma (Enter para sair):")
    while True:
        name = input("\nNome: ").strip()
        if not name:
            break
        result = matcher.match(name)
        if result:
            print(f"  Match: {result.tbca_name}")
            print(f"  Codigo: {result.tbca_code}")
            print(f"  Confianca: {result.confidence:.1f}%")
            print(f"  Metodo: {result.match_method}")
        else:
            print("  Nenhum match encontrado")


def cmd_run(settings: Settings, dry_run: bool = True, max_items: int = None):
    """Executa pipeline completo de automacao."""
    from automation.orchestrator import Orchestrator

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"{'='*60}")
    print(f"AUTOMACAO NUTRICIONAL - Modo: {mode}")
    print(f"{'='*60}")

    orch = Orchestrator(settings)

    try:
        print("\nIniciando navegador...")
        orch.start_browser(headless=False)

        print("\nExecutando pipeline completo...")
        results = orch.run_full_pipeline(dry_run=dry_run, max_items=max_items)

        print(f"\n{'='*60}")
        print("RESULTADOS:")
        for phase, data in results.items():
            if data:
                print(f"  {phase}: {json.dumps(data, indent=2, ensure_ascii=False)}")
        print(f"{'='*60}")

    except Exception as e:
        print(f"\nERRO: {e}")
        logger.exception("Erro no pipeline")
    finally:
        orch.stop_browser()


def cmd_list_platform(settings: Settings):
    """Lista todos os nutricionais da plataforma."""
    session = SessionManager(
        user_data_dir=settings.platform.user_data_dir,
        headless=settings.platform.headless,
        slow_mo=settings.platform.slow_mo,
        timeout=settings.platform.timeout,
    )

    try:
        session.start()
        session.login(
            login_url=settings.platform.login_url,
            username=settings.platform.username,
            password=settings.platform.password,
        )
        session.navigate(settings.platform.nutri_url)
        time.sleep(3)

        from browser.platform import PlatformInteraction
        platform = PlatformInteraction(session.page)
        foods = platform.get_all_foods()

        print(f"\n{len(foods)} nutricionais na plataforma:\n")
        for i, f in enumerate(foods, 1):
            print(f"  {i:3d}. {f['name']}")

        # Salvar em arquivo
        output_file = DATA_DIR / "platform_foods.json"
        with open(output_file, "w", encoding="utf-8") as fp:
            json.dump(foods, fp, ensure_ascii=False, indent=2)
        print(f"\nSalvo em: {output_file}")

    finally:
        session.stop()


def main():
    """Funcao principal."""
    settings = Settings.load()
    settings.load_env()
    setup_logging(settings)

    if len(sys.argv) < 2:
        print("Uso: python main.py <comando>")
        print("\nComandos:")
        print("  test             - Testa conexao com a plataforma")
        print("  list             - Lista nutricionais da plataforma")
        print("  tbca_search      - Busca alimentos no TBCA")
        print("  tbca_build       - Constoi indice TBCA completo")
        print("  match            - Testa matching platform <-> TBCA")
        print("  run              - Executa pipeline (DRY RUN)")
        print("  run_live         - Executa pipeline (LIVE)")
        print("  config           - Salva configuracoes")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "test":
        cmd_test(settings)
    elif command == "list":
        cmd_list_platform(settings)
    elif command == "tbca_search":
        cmd_tbca_search(settings)
    elif command == "tbca_build":
        cmd_tbca_build_index(settings)
    elif command == "match":
        cmd_match(settings)
    elif command == "run":
        max_items = int(sys.argv[2]) if len(sys.argv) > 2 else None
        cmd_run(settings, dry_run=True, max_items=max_items)
    elif command == "run_live":
        max_items = int(sys.argv[2]) if len(sys.argv) > 2 else None
        cmd_run(settings, dry_run=False, max_items=max_items)
    elif command == "config":
        settings.save()
        settings.save_env()
        print("Configuracoes salvas")
    else:
        print(f"Comando desconhecido: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()

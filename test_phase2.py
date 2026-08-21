"""
Teste da Fase 2: Navegação + Cards
Testa busca, seleção, abertura de dialog e leitura de campos.
"""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from browser.session import SessionManager
from browser.platform import PlatformInteraction


def test_phase2():
    settings = Settings.load()
    settings.load_env()

    print("=" * 60)
    print("FASE 2 - Teste de Navegação e Cards")
    print("=" * 60)

    session = SessionManager(
        user_data_dir=settings.platform.user_data_dir,
        headless=settings.platform.headless,
        timeout=settings.platform.timeout,
    )

    try:
        # Login
        print("\n[1] Login...")
        session.start()
        success = session.login(
            settings.platform.login_url,
            settings.platform.username,
            settings.platform.password,
        )
        if not success:
            print("  FALHA no login")
            return
        print("  OK")

        # Navegar para nutri
        print("\n[2] Navegando para nutri...")
        platform = PlatformInteraction(session.page)
        platform.navigate_to_nutri(settings.platform.nutri_url)
        print(f"  Cards: {platform.get_cards_count()}")

        # Listar alimentos
        print("\n[3] Listando alimentos...")
        foods = platform.get_all_foods()
        print(f"  Total: {len(foods)}")
        for f in foods[:5]:
            print(f"    {f['name']} (alert: {f['hasAlert']}, assoc: {f['isAssociated']})")

        # Testar busca
        print("\n[4] Testando busca...")
        test_foods = ["ARROZ", "BANANA", "LEITE", "QUEIJO", "FRANGO"]
        for query in test_foods:
            count = platform.search_food(query)
            print(f"  '{query}': {count} resultados")
            platform.clear_search()
            time.sleep(0.5)

        # Testar abertura de dialog (usando ARROZ como teste)
        print("\n[5] Testando abertura de dialog...")
        test_food = "ARROZ"
        print(f"  Abrindo: {test_food}")

        # Primeiro buscar
        platform.search_food(test_food)
        time.sleep(1)

        # Listar cards encontrados
        found = platform.get_all_foods()
        print(f"  Encontrados: {[f['name'] for f in found]}")

        # Tentar abrir o primeiro resultado
        if found:
            first_food = found[0]['name']
            print(f"\n  Abrindo dialog para: {first_food}")

            # Hover no card
            card = session.page.query_selector(
                f'[data-slot="popover-trigger"]:has-text("{first_food}")'
            )
            if card:
                card.hover()
                time.sleep(2)

                # Capturar screenshot do hover
                output_dir = Path(__file__).parent / "test_output"
                output_dir.mkdir(exist_ok=True)
                session.page.screenshot(
                    path=str(output_dir / "phase2_hover.png"),
                    full_page=True
                )
                print("  Screenshot do hover salvo")

                # Procurar botão de editar no hover card
                hover_content = session.page.query_selector(
                    '[data-slot="hover-card-content"]'
                )
                if hover_content:
                    print(f"  Hover card content encontrado")
                    hover_text = hover_content.text_content() or ""
                    print(f"  Texto: {hover_text[:200]}")

                    # Procurar botões de ação
                    buttons = hover_content.query_selector_all('button')
                    print(f"  Botões no hover card: {len(buttons)}")
                    for btn in buttons:
                        btn_text = btn.text_content() or ""
                        print(f"    - {btn_text[:50]}")

                    # Procurar specifically o botão de editar (lápis)
                    edit_btn = hover_content.query_selector('button:has(svg.text-blue-500)')
                    if not edit_btn:
                        # Tentar outros seletores
                        all_btns = hover_content.query_selector_all('button')
                        for btn in all_btns:
                            svg = btn.query_selector('svg')
                            if svg:
                                svg_class = svg.get_attribute('class') or ''
                                if 'blue' in svg_class or 'edit' in svg_class.lower():
                                    edit_btn = btn
                                    break

                    if edit_btn:
                        print("  Botão de editar encontrado, clicando...")
                        edit_btn.click()
                        time.sleep(3)

                        # Verificar se abriu o sheet
                        sheet = session.page.query_selector('[data-slot="sheet-content"]')
                        if sheet:
                            print("  Sheet de edição aberto!")

                            # Listar campos
                            fields = platform.get_form_fields()
                            print(f"\n  Campos visíveis: {len(fields)}")
                            for f in fields:
                                print(f"    [{f['tag']}] {f['label'] or f['name'] or f['id']}: {f['value'][:30] if f['value'] else '(vazio)'}")

                            # Ler dados nutricionais
                            print("\n  Dados nutricionais:")
                            data = platform.get_nutritional_data()
                            for k, v in data.items():
                                print(f"    {k}: {v}")

                            # Screenshot do sheet
                            session.page.screenshot(
                                path=str(output_dir / "phase2_sheet.png"),
                                full_page=True
                            )
                            print("\n  Screenshot do sheet salvo")

                            # Fechar
                            platform.close_edit_dialog()
                        else:
                            print("  Sheet NÃO abriu")
                    else:
                        print("  Botão de editar NÃO encontrado")
                else:
                    print("  Hover card content NÃO encontrado")

        # Limpar
        platform.clear_search()

        print("\n" + "=" * 60)
        print("FASE 2 - CONCLUIDA")
        print("=" * 60)

    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()

    finally:
        session.stop()


if __name__ == "__main__":
    test_phase2()

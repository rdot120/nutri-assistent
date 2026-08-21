"""
Test actual save: modify a field, save, reload, verify persistence.
Uses the first food's "parteInteiraMedidaCaseira429" field (safe to toggle).
"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from browser.session import SessionManager
from browser.platform import PlatformInteraction

settings = Settings.load()
settings.load_env()

session = SessionManager(
    user_data_dir=settings.platform.user_data_dir,
    headless=True,
    timeout=30000,
)

try:
    session.start()
    session.login(settings.platform.login_url, settings.platform.username, settings.platform.password)

    platform = PlatformInteraction(session.page)

    # Navigate to nutri
    platform.navigate_to_nutri(settings.platform.nutri_url)
    print("[OK] Navegado para nutri")

    # Select a food to test with (use "ACAI EM PO" which is the first food)
    search_count = platform.search_food("ACAI EM PO")
    print(f"[OK] Busca 'ACAI EM PO': {search_count} resultados")

    # Open edit dialog
    assert platform.open_edit_dialog("ACAI EM PO"), "Falha ao abrir dialog"
    print("[OK] Dialog aberto para ACAI EM PO")

    # Read current value
    current_value = platform.get_field_value("parteInteiraMedidaCaseira429")
    print(f"[OK] Valor atual parteInteira: '{current_value}'")

    # Determine new value (toggle between 1 and 2)
    new_value = "2" if current_value == "1" else "1"
    print(f"[OK] Novo valor: '{new_value}'")

    # Fill the field
    success = platform.set_field_value("parteInteiraMedidaCaseira429", new_value)
    assert success, "Falha ao preencher campo"
    print(f"[OK] Campo preenchido")

    # Verify value in DOM
    filled_value = platform.get_field_value("parteInteiraMedidaCaseira429")
    print(f"[OK] Valor no DOM apos preenchimento: '{filled_value}'")

    # Click save
    saved = platform.click_save()
    print(f"[OK] Save result: {saved}")

    time.sleep(2)

    # Reload page to verify persistence
    session.page.goto(settings.platform.nutri_url, wait_until="networkidle", timeout=30000)
    time.sleep(3)
    print("[OK] Pagina recarregada")

    # Open edit dialog again for the same food
    assert platform.open_edit_dialog("ACAI EM PO"), "Falha ao reabrir dialog"
    print("[OK] Dialog reaberto")

    # Read the value again
    saved_value = platform.get_field_value("parteInteiraMedidaCaseira429")
    print(f"[OK] Valor apos reload: '{saved_value}'")

    # Verify persistence
    if saved_value == new_value:
        print(f"\n[PASS] SAVE FUNCIONA! Valor '{new_value}' persistiu apos reload")
    else:
        print(f"\n[FAIL] Valor nao persistiu. Esperado: '{new_value}', Obtido: '{saved_value}'")

    # Restore original value
    restore_value = current_value if current_value else "1"
    platform.set_field_value("parteInteiraMedidaCaseira429", restore_value)
    platform.click_save()
    print(f"[OK] Valor restaurado para: '{restore_value}'")

finally:
    session.stop()

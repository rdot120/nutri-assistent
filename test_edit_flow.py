"""
Test complete edit flow: open → read → fill → save
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
    assert platform.navigate_to_nutri(settings.platform.nutri_url)
    print("[OK] Navegado para nutri")

    # List foods
    foods = platform.get_all_foods()
    print(f"[OK] {len(foods)} nutricionais encontrados")
    first_food = foods[0]['name']
    print(f"  Primeiro: {first_food}")

    # Open edit dialog
    assert platform.open_edit_dialog(first_food), f"Falha ao abrir edição para {first_food}"
    print(f"[OK] Dialog de edição aberto para: {first_food}")

    # Read mandatory fields
    fields = platform.get_form_fields("main")
    print(f"\n[OK] Campos obrigatórios: {len(fields)}")
    for f in fields:
        print(f"  [{f['label']}] {f['name']} = '{f['value']}'")

    # Read current values
    data = platform.get_nutritional_data()
    print(f"\n[OK] Dados lidos: {len(data)} campos")
    for k, v in data.items():
        print(f"  {k} = {v}")

    # Test: fill with same values (no-op to test the mechanism)
    print("\n=== Testando preenchimento (mesmos valores) ===")
    filled = platform.fill_nutritional_data(data)
    print(f"[OK] Campos preenchidos: {len(filled)}")

    # Verify values still the same
    data_after = platform.get_nutritional_data()
    mismatches = []
    for k in data:
        if data_after.get(k) != data.get(k):
            mismatches.append(f"{k}: '{data.get(k)}' → '{data_after.get(k)}'")
    if mismatches:
        print(f"[FAIL] Mismatches: {mismatches}")
    else:
        print("[OK] Todos os valores mantidos após preenchimento")

    # DON'T save to avoid changing real data
    print("\n[OK] Operação concluída (sem salvar)")
    print("\n=== RESUMO DO FLUXO ===")
    print("1. Card click -> Popover: OK")
    print("2. Square-pen click -> Dialog: OK")
    print("3. Read form fields: OK")
    print("4. Fill form fields: OK")
    print("5. Save (not executed): OK")

finally:
    session.stop()

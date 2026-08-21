"""Debug login flow step by step."""
import sys, time, json
sys.path.insert(0, r"C:\Users\Qualihouse\OneDrive\Documentos\Default Project\nutri_auto")
from browser.session import SessionManager

session = SessionManager(
    user_data_dir=r"C:\Users\Qualihouse\OneDrive\Documentos\Default Project\nutri_auto\data\browser_profile_debug",
    headless=True,
    timeout=30000,
)

try:
    page = session.start()

    # Step 1: Navigate to login
    print("[1] Navegando para login...")
    page.goto("https://balancas.tecnosoftapps.com/login", wait_until="networkidle", timeout=30000)
    time.sleep(2)
    print(f"    URL: {page.url}")
    print(f"    Title: {page.title()}")

    # Step 2: Check what's on the page
    print("[2] Analisando pagina...")
    inputs = page.evaluate("""
        () => Array.from(document.querySelectorAll('input')).map(i => ({
            id: i.id, type: i.type, placeholder: i.placeholder, name: i.name
        }))
    """)
    print(f"    Inputs: {json.dumps(inputs, indent=2)}")

    buttons = page.evaluate("""
        () => Array.from(document.querySelectorAll('button')).map(b => ({
            text: b.textContent.trim(), type: b.type
        }))
    """)
    print(f"    Buttons: {json.dumps(buttons, indent=2)}")

    # Step 3: Fill credentials
    print("[3] Preenchendo credenciais...")
    email_input = page.query_selector('input#email')
    if email_input:
        email_input.fill("evelyn")
        print("    Email preenchido")
    else:
        print("    ERRO: input#email nao encontrado")

    pwd_input = page.query_selector('input#password')
    if pwd_input:
        pwd_input.fill("123mudar")
        print("    Senha preenchida")
    else:
        print("    ERRO: input#password nao encontrado")

    time.sleep(1)

    # Step 4: Submit
    print("[4] Submetendo...")
    submit = page.query_selector('button[type="submit"]')
    if submit:
        submit.click()
        print("    Clique no submit")
    else:
        print("    ERRO: button[submit] nao encontrado")

    # Step 5: Wait for navigation
    print("[5] Aguardando navegacao...")
    try:
        page.wait_for_url("**/!(login)**", timeout=15000)
        print(f"    URL apos login: {page.url}")
    except:
        print(f"    URL atual: {page.url}")
        # Check if still on login
        if "login" in page.url:
            # Maybe there's an error message
            body = page.text_content("body") or ""
            # Find relevant text
            relevant = [line.strip() for line in body.split("\n") if line.strip() and len(line.strip()) > 3]
            print(f"    Textos na pagina: {relevant[:10]}")

    time.sleep(3)
    print(f"\n[6] URL final: {page.url}")
    print(f"    Logged in: {'login' not in page.url}")

    if "login" not in page.url:
        print("\n[7] Navegando para nutri...")
        page.goto("https://balancas.tecnosoftapps.com/nutri", wait_until="networkidle", timeout=30000)
        time.sleep(3)
        cards = page.evaluate("() => document.querySelectorAll('[data-slot=\"popover-trigger\"]').length")
        print(f"    Cards encontrados: {cards}")

finally:
    session.stop()

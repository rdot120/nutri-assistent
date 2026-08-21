"""
Debug: entender a estrutura do hover card e como abrir edição.
"""
import sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from browser.session import SessionManager

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
    session.page.goto(settings.platform.nutri_url, wait_until="networkidle", timeout=30000)
    time.sleep(3)

    # Pegar o primeiro card que NAO esteja vazio
    print("=== Buscando card para analise ===")
    first_card = session.page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                const text = card.textContent.trim();
                if (text.length > 2) return text;
            }
            return null;
        }
    """)
    print(f"Primeiro card com texto: {first_card}")

    # Clicar nele
    card_el = session.page.query_selector(f'[data-slot="popover-trigger"]:has-text("{first_card}")')
    if card_el:
        print(f"\n=== Card encontrado, analisando ===")

        # 1. Analisar HTML do card
        card_html = card_el.evaluate("el => el.outerHTML")
        print(f"Card HTML ({len(card_html)} chars):")
        print(card_html[:1500])
        print("...")

        # 2. Analisar hover-card-trigger
        hover_trigger = card_el.query_selector('a[data-slot="hover-card-trigger"]')
        if hover_trigger:
            print(f"\n=== Hover trigger encontrado ===")
            print(f"  Tag: {hover_trigger.evaluate('el => el.tagName')}")
            print(f"  HTML: {hover_trigger.evaluate('el => el.outerHTML')[:500]}")

            # 3. Fazer hover e aguardar
            print("\n=== Fazendo hover ===")
            hover_trigger.hover()
            time.sleep(3)

            # 4. Procurar hover-card-content em toda a pagina
            hover_contents = session.page.evaluate("""
                () => {
                    const results = [];
                    // Procurar por todos os elementos com data-slot
                    document.querySelectorAll('*').forEach(el => {
                        const slot = el.getAttribute('data-slot');
                        if (slot && slot.includes('hover')) {
                            results.push({
                                slot: slot,
                                text: el.textContent.substring(0, 300),
                                visible: el.offsetParent !== null,
                                display: window.getComputedStyle(el).display,
                                html: el.outerHTML.substring(0, 1000)
                            });
                        }
                    });
                    // Procurar por portals
                    document.querySelectorAll('[data-radix-portal] > *').forEach(el => {
                        results.push({
                            slot: 'radix-portal-child',
                            text: el.textContent.substring(0, 300),
                            visible: el.offsetParent !== null,
                            html: el.outerHTML.substring(0, 1000)
                        });
                    });
                    return results;
                }
            """)
            print(f"\nHover-related elements: {len(hover_contents)}")
            for hc in hover_contents:
                print(f"\n  [{hc['slot']}] visible={hc['visible']} display={hc['display']}")
                print(f"  text: {hc['text'][:200]}")
                if 'button' in hc['html'].lower():
                    print(f"  HAS BUTTONS!")

        # 5. Tentar abordagem diferente: clicar no icone de alerta
        print("\n=== Tentando clicar no hover trigger ===")
        if hover_trigger:
            hover_trigger.click()
            time.sleep(3)

            # Verificar se algo abriu
            dialogs = session.page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('[role="dialog"], [data-slot*="content"]').forEach(el => {
                        const text = el.textContent.trim();
                        if (text.length > 5 && text.length < 2000) {
                            results.push({
                                tag: el.tagName,
                                role: el.getAttribute('role'),
                                slot: el.getAttribute('data-slot'),
                                state: el.getAttribute('data-state'),
                                text: text.substring(0, 500),
                                html: el.outerHTML.substring(0, 2000)
                            });
                        }
                    });
                    return results;
                }
            """)
            print(f"\nDialogs/Content apos clique: {len(dialogs)}")
            for d in dialogs:
                print(f"\n  <{d['tag']}> role={d['role']} slot={d['slot']} state={d['state']}")
                print(f"  text: {d['text'][:300]}")
                # Procurar botoes
                if 'button' in d['html'].lower() or 'Editar' in d['text'] or 'Excluir' in d['text']:
                    print(f"  *** INTERACTIVE CONTENT FOUND ***")

        # 6. Salvar todos os dialogs/contents
        all_contents = session.page.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('[role="dialog"], [data-slot$="-content"]').forEach(el => {
                    results.push({
                        tag: el.tagName,
                        slot: el.getAttribute('data-slot'),
                        state: el.getAttribute('data-state'),
                        text: el.textContent.substring(0, 500),
                        buttons: Array.from(el.querySelectorAll('button')).map(b => b.textContent.trim()).filter(t => t.length > 0),
                        inputs: Array.from(el.querySelectorAll('input')).map(i => ({name: i.name, id: i.id, value: i.value})),
                        html: el.innerHTML.substring(0, 3000)
                    });
                });
                return results;
            }
        """)
        print(f"\n=== Todos os contents: {len(all_contents)} ===")
        for c in all_contents:
            print(f"\n  [{c['slot']}] state={c['state']}")
            print(f"  text: {c['text'][:200]}")
            if c['buttons']:
                print(f"  buttons: {c['buttons']}")
            if c['inputs']:
                print(f"  inputs: {c['inputs']}")
            if 'Editar' in c['text'] or 'Excluir' in c['text'] or 'Salvar' in c['text']:
                print(f"  *** THIS IS THE EDIT CONTENT ***")
                print(f"  html: {c['html'][:1000]}")

finally:
    session.stop()

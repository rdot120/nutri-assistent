"""
Click 'Clique aqui' with longer wait and observe DOM changes.
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
    page = session.page

    # Open edit dialog
    first_card = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                const r = card.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && card.textContent.trim().length > 2) {
                    return { x: r.x + r.width/2, y: r.y + r.height/2, text: card.textContent.trim() };
                }
            }
            return null;
        }
    """)
    page.mouse.click(first_card['x'], first_card['y'])
    time.sleep(2)

    btn = page.evaluate("""
        () => {
            const popover = document.querySelector('[data-slot="popover-content"]');
            const triggers = popover.querySelectorAll('[data-slot="dialog-trigger"]');
            const r = triggers[0].getBoundingClientRect();
            return { x: r.x + r.width/2, y: r.y + r.height/2 };
        }
    """)
    page.mouse.click(btn['x'], btn['y'])
    time.sleep(2)

    # Click "Campos Extras" tab
    extras_tab = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            const tabs = dialog.querySelectorAll('[data-slot="tabs-trigger"]');
            for (const tab of tabs) {
                if (tab.textContent.includes('Extras')) {
                    const r = tab.getBoundingClientRect();
                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                }
            }
            return null;
        }
    """)
    page.mouse.click(extras_tab['x'], extras_tab['y'])
    time.sleep(1)

    # Get HTML of the extras tab content BEFORE clicking
    before_html = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            const tabsContents = dialog.querySelectorAll('[data-slot="tabs-content"]');
            for (const tc of tabsContents) {
                if (tc.getBoundingClientRect().height > 0) {
                    return tc.outerHTML.substring(0, 3000);
                }
            }
            return null;
        }
    """)
    print(f"Before click HTML: {before_html[:1000]}")

    # Click "Clique aqui" button
    clique_aqui = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            const btns = dialog.querySelectorAll('button');
            for (const b of btns) {
                if (b.textContent.trim() === 'Clique aqui') {
                    const r = b.getBoundingClientRect();
                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                }
            }
            return null;
        }
    """)
    if clique_aqui:
        page.mouse.click(clique_aqui['x'], clique_aqui['y'])

    # Wait and check for changes every 500ms
    for i in range(12):
        time.sleep(0.5)
        state = page.evaluate("""
            () => {
                const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                if (!dialog) return { error: 'dialog gone' };
                const tabsContents = dialog.querySelectorAll('[data-slot="tabs-content"]');
                let active = null;
                for (const tc of tabsContents) {
                    if (tc.getBoundingClientRect().height > 0) {
                        active = tc;
                        break;
                    }
                }
                if (!active) return { error: 'no active content' };
                return {
                    inputCount: active.querySelectorAll('input, select, textarea').length,
                    labelCount: active.querySelectorAll('label').length,
                    childCount: active.children.length,
                    textLen: active.textContent.length,
                    text: active.textContent.substring(0, 200),
                    html: active.outerHTML.substring(0, 1000)
                };
            }
        """)
        inputs = state.get('inputCount', 0)
        labels = state.get('labelCount', 0)
        text_len = state.get('textLen', 0)
        print(f"  [{i*500}ms] inputs={inputs} labels={labels} children={state.get('childCount', 0)} textLen={text_len}")
        if inputs > 0 or labels > 5:
            print(f"\n  EXTRAS LOADED!")
            # Capture all fields
            extras = page.evaluate("""
                () => {
                    const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                    const tabsContents = dialog.querySelectorAll('[data-slot="tabs-content"]');
                    let active = null;
                    for (const tc of tabsContents) {
                        if (tc.getBoundingClientRect().height > 0) { active = tc; break; }
                    }
                    if (!active) return null;
                    const fields = [];
                    const labels = active.querySelectorAll('label');
                    for (const label of labels) {
                        const text = label.textContent.trim();
                        let input = null;
                        let sib = label.nextElementSibling;
                        for (let i = 0; i < 5 && sib; i++) {
                            if (sib.tagName === 'INPUT' || sib.tagName === 'SELECT') { input = sib; break; }
                            const inner = sib.querySelector('input, select');
                            if (inner) { input = inner; break; }
                            sib = sib.nextElementSibling;
                        }
                        if (input) {
                            fields.push({
                                labelText: text,
                                inputName: input.name || '',
                                inputType: input.type || input.tagName.toLowerCase(),
                                value: input.value || ''
                            });
                        } else {
                            fields.push({ labelText: text, noInput: true });
                        }
                    }
                    return fields;
                }
            """)
            for f in extras:
                if f.get('noInput'):
                    print(f"    [{f['labelText']}] => NO INPUT")
                else:
                    print(f"    [{f['labelText']}] => name={f['inputName']} type={f['inputType']} value='{f['value']}'")
            break
    else:
        print("\nExtras did not load. Final HTML:")
        final_html = page.evaluate("""
            () => {
                const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                const tabsContents = dialog.querySelectorAll('[data-slot="tabs-content"]');
                for (const tc of tabsContents) {
                    if (tc.getBoundingClientRect().height > 0) {
                        return tc.outerHTML;
                    }
                }
                return null;
            }
        """)
        print(final_html[:2000] if final_html else "None")

    page.screenshot(path="nutri_auto/debug_extras_final.png", full_page=False)

finally:
    session.stop()

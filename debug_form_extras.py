"""
Capture the Campos Extras tab fields.
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
                    return { x: r.x + r.width/2, y: r.y + r.height/2, text: tab.textContent.trim() };
                }
            }
            return null;
        }
    """)
    print(f"Extras tab: {extras_tab}")
    if extras_tab:
        page.mouse.click(extras_tab['x'], extras_tab['y'])
        time.sleep(1)

        # Capture ALL fields in the extras tab
        extras = page.evaluate("""
            () => {
                const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                const tabsContent = dialog.querySelectorAll('[data-slot="tabs-content"]');
                let activeContent = null;
                for (const tc of tabsContent) {
                    if (tc.offsetHeight > 0 && tc.offsetWidth > 0) {
                        activeContent = tc;
                        break;
                    }
                }
                if (!activeContent) return { error: 'No active tabs-content' };

                const fields = [];
                const labels = activeContent.querySelectorAll('label');
                for (const label of labels) {
                    const text = label.textContent.trim();
                    let input = null;
                    if (label.htmlFor) {
                        input = activeContent.querySelector('#' + label.htmlFor);
                    }
                    if (!input) {
                        let sib = label.nextElementSibling;
                        for (let i = 0; i < 5 && sib; i++) {
                            if (sib.tagName === 'INPUT' || sib.tagName === 'SELECT' || sib.tagName === 'TEXTAREA') {
                                input = sib;
                                break;
                            }
                            const inner = sib.querySelector('input, select, textarea');
                            if (inner) { input = inner; break; }
                            sib = sib.nextElementSibling;
                        }
                    }
                    if (input) {
                        const field = {
                            labelText: text,
                            inputName: input.name || '',
                            inputType: input.type || input.tagName.toLowerCase(),
                            value: input.value || '',
                            placeholder: input.placeholder || ''
                        };
                        if (input.tagName === 'SELECT') {
                            field.options = Array.from(input.querySelectorAll('option')).map(o => ({
                                value: o.value, text: o.textContent.trim(), selected: o.selected
                            }));
                        }
                        fields.push(field);
                    } else {
                        fields.push({ labelText: text, noInput: true });
                    }
                }

                // Unassociated
                const allInputs = activeContent.querySelectorAll('input, select, textarea');
                const associatedNames = new Set(fields.filter(f => f.inputName).map(f => f.inputName));
                const unassociated = [];
                for (const inp of allInputs) {
                    if (inp.name && !associatedNames.has(inp.name)) {
                        unassociated.push({
                            name: inp.name, type: inp.type || inp.tagName.toLowerCase(),
                            value: inp.value || '', placeholder: inp.placeholder || ''
                        });
                    }
                }

                return { fieldCount: fields.length, fields, unassociated };
            }
        """)
        print(f"\n=== CAMPOS EXTRAS ===")
        print(f"Fields: {extras['fieldCount']}")
        for f in extras['fields']:
            if f.get('noInput'):
                print(f"  [{f['labelText']}] => NO INPUT")
            else:
                extra = ''
                if f.get('options'):
                    extra = f" options={[o['text'] + '(' + o['value'] + ')' for o in f['options'][:5]]}"
                print(f"  [{f['labelText']}] => name={f['inputName']} type={f['inputType']} value='{f['value']}'{extra}")
        if extras.get('unassociated'):
            print(f"\nUnassociated:")
            for inp in extras['unassociated']:
                print(f"  name={inp['name']} type={inp['type']} value='{inp['value']}'")

        # Save combined structure
        with open("nutri_auto/form_structure_extras.json", "w", encoding="utf-8") as f:
            json.dump(extras, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to form_structure_extras.json")

finally:
    session.stop()

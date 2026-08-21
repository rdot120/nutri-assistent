"""
Phase 2: Capture complete form structure from edit dialog.
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

    # Open edit dialog for first card
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
    print(f"Card: {first_card['text']}")
    page.mouse.click(first_card['x'], first_card['y'])
    time.sleep(2)

    # Click square-pen
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

    # Capture COMPLETE form structure
    form = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            if (!dialog) return { error: 'Dialog not found' };

            // Get all form fields by finding label-input pairs
            const fields = [];
            const labels = dialog.querySelectorAll('label');
            for (const label of labels) {
                const text = label.textContent.trim();
                // Find associated input via for attribute or proximity
                let input = null;
                if (label.htmlFor) {
                    input = dialog.querySelector('#' + label.htmlFor);
                }
                if (!input) {
                    // Try finding input in next sibling or parent
                    const container = label.closest('[class*="flex"]') || label.parentElement;
                    if (container) {
                        input = container.querySelector('input, select, textarea');
                    }
                }
                if (!input) {
                    // Try nextElementSibling
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
                        inputId: input.id || '',
                        value: input.value || '',
                        placeholder: input.placeholder || '',
                        required: input.required || input.getAttribute('aria-required') === 'true'
                    };

                    // If it's a select, get options
                    if (input.tagName === 'SELECT' || input.getAttribute('role') === 'combobox') {
                        const options = input.querySelectorAll('option');
                        field.options = Array.from(options).map(o => ({
                            value: o.value,
                            text: o.textContent.trim(),
                            selected: o.selected
                        }));
                    }

                    // If it's a checkbox, get state
                    if (input.type === 'checkbox') {
                        field.checked = input.checked;
                    }

                    fields.push(field);
                } else {
                    fields.push({ labelText: text, inputName: null, noInput: true });
                }
            }

            // Also find any inputs not associated with labels
            const allInputs = dialog.querySelectorAll('input, select, textarea');
            const associatedNames = new Set(fields.filter(f => f.inputName).map(f => f.inputName));
            const unassociated = [];
            for (const inp of allInputs) {
                if (inp.name && !associatedNames.has(inp.name)) {
                    unassociated.push({
                        name: inp.name,
                        type: inp.type,
                        value: inp.value || '',
                        placeholder: inp.placeholder || ''
                    });
                }
            }

            // Get all buttons
            const buttons = Array.from(dialog.querySelectorAll('button')).map(b => ({
                text: b.textContent.trim().substring(0, 40),
                type: b.type,
                ariaLabel: b.getAttribute('aria-label') || '',
                dataSlot: b.getAttribute('data-slot') || ''
            }));

            // Get the full text for context
            const fullText = dialog.textContent;

            return {
                title: dialog.querySelector('[data-slot="dialog-title"]')?.textContent || '',
                description: dialog.querySelector('[data-slot="dialog-description"]')?.textContent || '',
                fieldCount: fields.length,
                fields: fields,
                unassociatedInputs: unassociated,
                buttons: buttons,
                fullTextLength: fullText.length,
                fullText: fullText.substring(0, 2000)
            };
        }
    """)
    print(f"\n=== FORM STRUCTURE ===")
    print(f"Title: {form['title']}")
    print(f"Description: {form['description']}")
    print(f"Fields: {form['fieldCount']}")
    print(f"\nFields:")
    for f in form['fields']:
        if f.get('noInput'):
            print(f"  [{f['labelText']}] => NO INPUT FOUND")
        else:
            extra = ''
            if f.get('options'):
                extra = f" options={[o['text'] + '(' + o['value'] + ')' for o in f['options'][:5]]}"
            if f.get('checked') is not None:
                extra = f" checked={f['checked']}"
            print(f"  [{f['labelText']}] => name={f['inputName']} type={f['inputType']} value='{f['value']}'{extra}")

    if form['unassociatedInputs']:
        print(f"\nUnassociated inputs:")
        for inp in form['unassociatedInputs']:
            print(f"  name={inp['name']} type={inp['type']} value='{inp['value']}'")

    print(f"\nButtons:")
    for b in form['buttons']:
        print(f"  [{b['text']}] type={b['type']} slot={b['dataSlot']}")

    # Save form structure to file
    with open("nutri_auto/form_structure.json", "w", encoding="utf-8") as f:
        json.dump(form, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to form_structure.json")

finally:
    session.stop()

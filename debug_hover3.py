"""
Debug: Find a hover card that has action buttons (Editar/Excluir).
Then click Editar and inspect the Sheet form.
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

    # Check multiple hover cards to find one with buttons
    triggers = page.evaluate("""
        () => {
            const triggers = document.querySelectorAll('[data-slot="hover-card-trigger"]');
            const results = [];
            for (let i = 0; i < triggers.length; i++) {
                const t = triggers[i];
                const rect = t.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    results.push({
                        index: i,
                        x: rect.x + rect.width/2,
                        y: rect.y + rect.height/2
                    });
                }
            }
            return results;
        }
    """)
    print(f"Total visible triggers: {len(triggers)}")

    # Try hovering over triggers until we find one with buttons
    found = False
    for i, trigger in enumerate(triggers[:20]):
        page.mouse.move(trigger['x'], trigger['y'])
        time.sleep(0.8)

        hover_info = page.evaluate("""
            () => {
                const content = document.querySelector('[data-slot="hover-card-content"]');
                if (!content || content.getBoundingClientRect().width === 0) return { found: false };
                const buttons = Array.from(content.querySelectorAll('button'));
                return {
                    found: true,
                    text: content.textContent.substring(0, 200),
                    buttonCount: buttons.length,
                    buttonTexts: buttons.map(b => b.textContent.trim())
                };
            }
        """)

        if hover_info.get('found') and hover_info.get('buttonCount', 0) > 0:
            print(f"\nTrigger #{i}: FOUND HOVER CARD WITH BUTTONS!")
            print(f"  Text: {hover_info['text']}")
            print(f"  Buttons: {hover_info['buttonTexts']}")
            found = True

            # Click Editar
            for btn_text in hover_info['buttonTexts']:
                if 'Editar' in btn_text:
                    # Find and click the Editar button
                    btn_pos = page.evaluate("""
                        () => {
                            const content = document.querySelector('[data-slot="hover-card-content"]');
                            if (!content) return null;
                            const buttons = content.querySelectorAll('button');
                            for (const b of buttons) {
                                if (b.textContent.includes('Editar')) {
                                    const r = b.getBoundingClientRect();
                                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                                }
                            }
                            return null;
                        }
                    """)
                    if btn_pos:
                        print(f"  Clicking Editar at ({btn_pos['x']}, {btn_pos['y']})")
                        page.mouse.click(btn_pos['x'], btn_pos['y'])
                        time.sleep(2)

                        # Check for Sheet
                        sheet = page.evaluate("""
                            () => {
                                const sheet = document.querySelector('[data-slot="sheet-content"]');
                                if (!sheet) return { found: false };

                                const inputs = Array.from(sheet.querySelectorAll('input'));
                                const selects = Array.from(sheet.querySelectorAll('select'));
                                const labels = Array.from(sheet.querySelectorAll('label'));
                                const buttons = Array.from(sheet.querySelectorAll('button'));

                                return {
                                    found: true,
                                    inputCount: inputs.length,
                                    inputs: inputs.map(i => ({
                                        id: i.id,
                                        name: i.name,
                                        placeholder: i.placeholder,
                                        value: i.value,
                                        type: i.type,
                                        label: i.getAttribute('aria-label') || ''
                                    })),
                                    selectCount: selects.length,
                                    labels: labels.map(l => ({
                                        text: l.textContent.trim().substring(0, 50),
                                        for: l.htmlFor || ''
                                    })),
                                    buttonTexts: buttons.map(b => b.textContent.trim().substring(0, 30)),
                                    heading: sheet.querySelector('h2, h3')?.textContent || '',
                                    textPreview: sheet.textContent.substring(0, 1000)
                                };
                            }
                        """)
                        print(f"\nSheet opened: {json.dumps(sheet, indent=2)}")

                        # Take a screenshot
                        page.screenshot(path="nutri_auto/debug_sheet_screenshot.png", full_page=False)
                        print("\nScreenshot saved: debug_sheet_screenshot.png")
                    break
            break

        # Move away to close hover card
        page.mouse.move(0, 0)
        time.sleep(0.3)

    if not found:
        print("\nNo hover cards with buttons found in first 20 triggers.")
        print("Trying to scroll down to find more...")
        page.evaluate("window.scrollBy(0, 2000)")
        time.sleep(2)

        triggers2 = page.evaluate("""
            () => {
                const triggers = document.querySelectorAll('[data-slot="hover-card-trigger"]');
                const results = [];
                for (let i = 0; i < triggers.length; i++) {
                    const t = triggers[i];
                    const rect = t.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        results.push({ index: i, x: rect.x + rect.width/2, y: rect.y + rect.height/2 });
                    }
                }
                return results.slice(0, 20);
            }
        """)
        for trigger in triggers2[:10]:
            page.mouse.move(trigger['x'], trigger['y'])
            time.sleep(0.8)
            hover_info = page.evaluate("""
                () => {
                    const content = document.querySelector('[data-slot="hover-card-content"]');
                    if (!content || content.getBoundingClientRect().width === 0) return { found: false };
                    const buttons = Array.from(content.querySelectorAll('button'));
                    return {
                        found: true,
                        text: content.textContent.substring(0, 200),
                        buttonCount: buttons.length,
                        buttonTexts: buttons.map(b => b.textContent.trim())
                    };
                }
            """)
            if hover_info.get('found') and hover_info.get('buttonCount', 0) > 0:
                print(f"\nTrigger #{trigger['index']}: FOUND HOVER CARD WITH BUTTONS!")
                print(f"  Text: {hover_info['text']}")
                print(f"  Buttons: {hover_info['buttonTexts']}")
                found = True

                for btn_text in hover_info['buttonTexts']:
                    if 'Editar' in btn_text:
                        btn_pos = page.evaluate("""
                            () => {
                                const content = document.querySelector('[data-slot="hover-card-content"]');
                                if (!content) return null;
                                for (const b of content.querySelectorAll('button')) {
                                    if (b.textContent.includes('Editar')) {
                                        const r = b.getBoundingClientRect();
                                        return { x: r.x + r.width/2, y: r.y + r.height/2 };
                                    }
                                }
                                return null;
                            }
                        """)
                        if btn_pos:
                            page.mouse.click(btn_pos['x'], btn_pos['y'])
                            time.sleep(2)

                            sheet = page.evaluate("""
                                () => {
                                    const sheet = document.querySelector('[data-slot="sheet-content"]');
                                    if (!sheet) return { found: false };
                                    return {
                                        found: true,
                                        inputCount: Array.from(sheet.querySelectorAll('input')).length,
                                        inputs: Array.from(sheet.querySelectorAll('input')).map(i => ({
                                            id: i.id,
                                            name: i.name,
                                            placeholder: i.placeholder,
                                            type: i.type
                                        })),
                                        labels: Array.from(sheet.querySelectorAll('label')).map(l => l.textContent.trim().substring(0, 50)),
                                        textPreview: sheet.textContent.substring(0, 1000)
                                    };
                                }
                            """)
                            print(f"\nSheet: {json.dumps(sheet, indent=2)}")
                            page.screenshot(path="nutri_auto/debug_sheet_screenshot.png", full_page=False)
                        break
                break
            page.mouse.move(0, 0)
            time.sleep(0.3)

    if not found:
        print("\nStill no hover cards with buttons. Checking all cards text...")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

finally:
    session.stop()

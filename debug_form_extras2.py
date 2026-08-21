"""
Capture ALL tabs-content elements to find the extras fields.
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
    if extras_tab:
        page.mouse.click(extras_tab['x'], extras_tab['y'])
        time.sleep(1)

    # Get ALL tabs-content elements
    all_tabs = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            const tabsContents = dialog.querySelectorAll('[data-slot="tabs-content"]');
            const result = [];
            for (let i = 0; i < tabsContents.length; i++) {
                const tc = tabsContents[i];
                const rect = tc.getBoundingClientRect();
                const inputs = tc.querySelectorAll('input, select, textarea');
                result.push({
                    index: i,
                    dataState: tc.getAttribute('data-state'),
                    visible: rect.width > 0 && rect.height > 0,
                    rect: { w: rect.width, h: rect.height },
                    inputCount: inputs.length,
                    inputs: Array.from(inputs).map(inp => ({
                        name: inp.name,
                        type: inp.type || inp.tagName.toLowerCase(),
                        value: inp.value || ''
                    })),
                    textPreview: tc.textContent.substring(0, 300)
                });
            }
            return result;
        }
    """)
    print("=== ALL tabs-content elements ===")
    for tc in all_tabs:
        print(f"\nTab {tc['index']}: state={tc['dataState']} visible={tc['visible']} inputs={tc['inputCount']}")
        if tc['inputCount'] > 0:
            for inp in tc['inputs']:
                print(f"  {inp['name']} ({inp['type']}) = '{inp['value']}'")
        print(f"  text: {tc['textPreview'][:200]}")

    # Try clicking Campos Extras again and check what happens
    print("\n=== Clicking Campos Extras tab again ===")
    extras_tab2 = page.evaluate("""
        () => {
            const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
            const tabs = dialog.querySelectorAll('[data-slot="tabs-trigger"]');
            for (const tab of tabs) {
                if (tab.textContent.includes('Extras')) {
                    const r = tab.getBoundingClientRect();
                    return {
                        x: r.x + r.width/2, y: r.y + r.height/2,
                        dataState: tab.getAttribute('data-state'),
                        ariaSelected: tab.getAttribute('aria-selected')
                    };
                }
            }
            return null;
        }
    """)
    print(f"Extras tab state: {extras_tab2}")

    if extras_tab2:
        page.mouse.click(extras_tab2['x'], extras_tab2['y'])
        time.sleep(1)

        # Re-check after second click
        all_tabs2 = page.evaluate("""
            () => {
                const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                const tabsContents = dialog.querySelectorAll('[data-slot="tabs-content"]');
                const result = [];
                for (let i = 0; i < tabsContents.length; i++) {
                    const tc = tabsContents[i];
                    const inputs = tc.querySelectorAll('input, select, textarea');
                    result.push({
                        index: i,
                        dataState: tc.getAttribute('data-state'),
                        visible: tc.getBoundingClientRect().width > 0,
                        inputCount: inputs.length,
                        labels: Array.from(tc.querySelectorAll('label')).map(l => l.textContent.trim().substring(0, 40)),
                        textPreview: tc.textContent.substring(0, 500)
                    });
                }
                return result;
            }
        """)
        for tc in all_tabs2:
            print(f"\nTab {tc['index']}: state={tc['dataState']} visible={tc['visible']} inputs={tc['inputCount']}")
            if tc['labels']:
                print(f"  labels: {tc['labels']}")
            print(f"  text: {tc['textPreview'][:300]}")

    # Take screenshot
    page.screenshot(path="nutri_auto/debug_extras_screenshot.png", full_page=False)

finally:
    session.stop()

"""
Debug: Try second dialog-trigger and look for the actual edit flow.
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

    # Click first food card
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
    time.sleep(1.5)

    # Close any existing dialog first
    page.keyboard.press("Escape")
    time.sleep(0.5)

    # Re-open popover
    page.mouse.click(first_card['x'], first_card['y'])
    time.sleep(1.5)

    # Try the SECOND dialog-trigger
    edit_btn = page.evaluate("""
        () => {
            const popover = document.querySelector('[data-slot="popover-content"]');
            if (!popover) return null;
            const triggers = popover.querySelectorAll('[data-slot="dialog-trigger"]');
            if (triggers.length < 2) return null;
            const t = triggers[1];
            const r = t.getBoundingClientRect();
            return { x: r.x + r.width/2, y: r.y + r.height/2 };
        }
    """)
    if edit_btn:
        print(f"\nClicking SECOND dialog-trigger at ({edit_btn['x']}, {edit_btn['y']})")
        page.mouse.click(edit_btn['x'], edit_btn['y'])
        time.sleep(3)

        # Check what opened
        dialog_info = page.evaluate("""
            () => {
                // Check all dialogs and sheets
                const dialogs = document.querySelectorAll('[role="dialog"], [data-slot="sheet-content"]');
                const results = [];
                for (const d of dialogs) {
                    const r = d.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        results.push({
                            slot: d.getAttribute('data-slot'),
                            role: d.getAttribute('role'),
                            ariaLabel: d.getAttribute('aria-label'),
                            textPreview: d.textContent.substring(0, 300),
                            inputCount: d.querySelectorAll('input').length,
                            inputs: Array.from(d.querySelectorAll('input')).map(i => ({
                                id: i.id, name: i.name, placeholder: i.placeholder,
                                type: i.type, value: i.value.substring(0, 30)
                            })),
                            selectCount: d.querySelectorAll('select').length,
                            buttonCount: d.querySelectorAll('button').length,
                            buttons: Array.from(d.querySelectorAll('button')).map(b => ({
                                text: b.textContent.trim().substring(0, 40),
                                type: b.type
                            }))
                        });
                    }
                }
                return results;
            }
        """)
        print(f"Open dialogs/sheets: {json.dumps(dialog_info, indent=2)}")

        page.screenshot(path="nutri_auto/debug_edit2_screenshot.png", full_page=False)

        # Try pressing Escape and trying a completely different approach
        page.keyboard.press("Escape")
        time.sleep(0.5)

    # APPROACH B: Maybe edit is accessed via direct URL
    # The page might use query params like /nutri?edit=1
    print("\n=== Checking for URL-based navigation ===")

    # Let's look at the full page HTML for any hidden forms or data attributes
    page_data = page.evaluate("""
        () => {
            // Look for Next.js data
            const scripts = document.querySelectorAll('script');
            let nextData = null;
            for (const s of scripts) {
                if (s.id === '__NEXT_DATA__') {
                    nextData = JSON.parse(s.textContent);
                    break;
                }
            }

            // Look for __next_f data
            const nextF = window.__next_f || [];
            const serverActions = [];
            for (const item of nextF) {
                if (Array.isArray(item)) {
                    const str = String(item[1] || '');
                    if (str.includes('loadNutriEdit') || str.includes('formNutricional') ||
                        str.includes('deleteNutricional') || str.includes('getProds')) {
                        serverActions.push(str.substring(0, 200));
                    }
                }
            }

            return {
                nextData: nextData ? { page: nextData.page, query: nextData.query } : null,
                serverActionRefs: serverActions.slice(0, 10)
            };
        }
    """)
    print(f"Page data: {json.dumps(page_data, indent=2)}")

    # APPROACH C: Use React internals to call loadNutriEdit directly
    print("\n=== Using React fiber to find edit handler ===")
    edit_result = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                if (card.textContent.trim().length < 3) continue;

                // Find ALL dialog triggers within this card
                const dialogTriggers = card.querySelectorAll('[data-slot="dialog-trigger"]');
                for (const dt of dialogTriggers) {
                    const fiberKey = Object.keys(dt).find(k => k.startsWith('__reactFiber'));
                    if (!fiberKey) continue;

                    let fiber = dt[fiberKey];
                    let depth = 0;
                    while (fiber && depth < 20) {
                        if (fiber.memoizedProps) {
                            const props = fiber.memoizedProps;
                            if (props.onClick) {
                                const src = props.onClick.toString();
                                if (src.length > 10) {
                                    return {
                                        depth: depth,
                                        type: fiber.type?.name || fiber.type?.displayName || 'unknown',
                                        onClickSrc: src.substring(0, 500)
                                    };
                                }
                            }
                        }
                        fiber = fiber.return;
                        depth++;
                    }
                }
                break;
            }
            return null;
        }
    """)
    print(f"Edit handler: {json.dumps(edit_result, indent=2)}")

    # APPROACH D: Navigate to the page and use the server action form endpoint directly
    print("\n=== Trying server action for loadNutriEdit ===")
    # Look at the __next_f array for action IDs
    action_ids = page.evaluate("""
        () => {
            const nextF = window.__next_f || [];
            const ids = [];
            for (const item of nextF) {
                if (Array.isArray(item)) {
                    const str = String(item[1] || '');
                    // Server actions have IDs like $ACTION_ID_xxx
                    if (str.includes('$ACTION_ID') || str.includes('actionId') || str.includes('.createServerReference')) {
                        ids.push(str.substring(0, 300));
                    }
                }
            }
            return ids.slice(0, 20);
        }
    """)
    print(f"Action IDs found: {len(action_ids)}")
    for aid in action_ids[:5]:
        print(f"  {aid[:200]}")

finally:
    session.stop()

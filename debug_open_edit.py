"""
Debug: Test open_edit_dialog flow step by step.
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
    platform.navigate_to_nutri(settings.platform.nutri_url)
    print("[OK] Navegado")

    # Step 1: Close popups
    platform._close_all_popups()
    print("[OK] Popups fechados")

    # Step 2: Search
    count = platform.search_food("ARROZ BRANCO KG")
    print(f"[OK] Busca: {count} resultados")
    time.sleep(1)

    # Step 3: Find card position
    card_pos = session.page.evaluate("""
        (foodName) => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            const results = [];
            for (const card of cards) {
                const cardText = card.textContent.trim();
                const r = card.getBoundingClientRect();
                results.push({
                    text: cardText,
                    visible: r.width > 0 && r.height > 0,
                    x: r.x, y: r.y, w: r.width, h: r.height
                });
                if (r.width > 0 && r.height > 0 &&
                    (cardText.toUpperCase().includes(foodName.toUpperCase()) ||
                     foodName.toUpperCase().includes(cardText.toUpperCase()))) {
                    return { x: r.x + r.width/2, y: r.y + r.height/2, text: cardText, allVisible: results.length };
                }
            }
            return { error: 'no match', cards: results.slice(0, 5) };
        }
    """, "ARROZ BRANCO KG")
    print(f"[OK] Card position: {json.dumps(card_pos, indent=2)}")

    if 'error' in card_pos:
        print("[FAIL] Card not found by JS")
        sys.exit(1)

    # Step 4: Click card
    session.page.mouse.click(card_pos['x'], card_pos['y'])
    time.sleep(2)

    # Step 5: Check popover
    popover_info = session.page.evaluate("""
        () => {
            const popover = document.querySelector('[data-slot="popover-content"]');
            if (!popover) return { found: false };
            const triggers = popover.querySelectorAll('[data-slot="dialog-trigger"]');
            const allBtns = popover.querySelectorAll('button');
            const rect = popover.getBoundingClientRect();
            return {
                found: true,
                visible: rect.width > 0 && rect.height > 0,
                text: popover.textContent.substring(0, 200),
                dialogTriggerCount: triggers.length,
                allButtonCount: allBtns.length,
                html: popover.outerHTML.substring(0, 2000)
            };
        }
    """)
    print(f"\n[OK] Popover info:")
    print(f"  found: {popover_info['found']}")
    print(f"  visible: {popover_info.get('visible')}")
    print(f"  text: {popover_info.get('text', '')[:100]}")
    print(f"  dialog-triggers: {popover_info.get('dialogTriggerCount')}")
    print(f"  all buttons: {popover_info.get('allButtonCount')}")
    if popover_info.get('dialogTriggerCount', 0) == 0:
        print(f"\n  HTML: {popover_info.get('html', '')[:1500]}")

    # Step 6: If no dialog-trigger found, try clicking the edit button by SVG class
    if popover_info.get('dialogTriggerCount', 0) == 0:
        print("\n[INFO] No dialog-triggers. Trying direct SVG click...")
        svg_pos = session.page.evaluate("""
            () => {
                const popover = document.querySelector('[data-slot="popover-content"]');
                if (!popover) return null;
                const svgs = popover.querySelectorAll('svg');
                for (const svg of svgs) {
                    const cls = svg.getAttribute('class') || '';
                    if (cls.includes('square-pen') || cls.includes('pencil') || cls.includes('edit')) {
                        const r = svg.getBoundingClientRect();
                        return { x: r.x + r.width/2, y: r.y + r.height/2, class: cls };
                    }
                }
                // Any SVG
                if (svgs.length > 0) {
                    const firstSvg = svgs[0];
                    const r = firstSvg.getBoundingClientRect();
                    return { x: r.x + r.width/2, y: r.y + r.height/2, class: firstSvg.getAttribute('class') || '' };
                }
                return null;
            }
        """)
        print(f"  SVG pos: {svg_pos}")
        if svg_pos:
            session.page.mouse.click(svg_pos['x'], svg_pos['y'])
            time.sleep(2)
            dialog = session.page.evaluate("""
                () => {
                    const d = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                    if (!d) return { found: false };
                    return {
                        found: true,
                        title: d.querySelector('[data-slot="dialog-title"]')?.textContent || '',
                        inputCount: d.querySelectorAll('input').length
                    };
                }
            """)
            print(f"  Dialog after SVG click: {dialog}")

finally:
    session.stop()

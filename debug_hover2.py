"""
Debug: Trigger hover card on alert icon, click Editar, open Sheet.
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

    # Step 1: Find first food card text
    first_card_text = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                const text = card.textContent.trim();
                if (text.length > 2) return text;
            }
            return null;
        }
    """)
    print(f"First card: {first_card_text}")

    # Step 2: Find the alert-icon (hover-card-trigger) near the first card
    # The alert icon is a sibling or nearby element with data-slot="hover-card-trigger"
    trigger_info = page.evaluate("""
        () => {
            const triggers = document.querySelectorAll('[data-slot="hover-card-trigger"]');
            const results = [];
            for (let i = 0; i < Math.min(5, triggers.length); i++) {
                const t = triggers[i];
                const rect = t.getBoundingClientRect();
                results.push({
                    index: i,
                    tag: t.tagName,
                    classList: Array.from(t.classList),
                    text: t.textContent.substring(0, 50),
                    rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
                    visible: rect.width > 0 && rect.height > 0,
                    parentText: t.parentElement?.textContent?.substring(0, 80) || ''
                });
            }
            return { total: triggers.length, items: results };
        }
    """)
    print(f"\nHover card triggers: {json.dumps(trigger_info, indent=2)}")

    # Step 3: Find the alert icon SVGs specifically
    alert_icons = page.evaluate("""
        () => {
            // The alert icon is an SVG inside a button/span with data-state="closed"
            const icons = document.querySelectorAll('[data-slot="hover-card-trigger"] svg');
            const results = [];
            for (let i = 0; i < Math.min(5, icons.length); i++) {
                const svg = icons[i];
                const rect = svg.getBoundingClientRect();
                results.push({
                    index: i,
                    width: rect.width,
                    height: rect.height,
                    x: rect.x,
                    y: rect.y,
                    visible: rect.width > 0 && rect.height > 0,
                    parentTag: svg.parentElement?.tagName,
                    grandparentText: svg.parentElement?.parentElement?.textContent?.substring(0, 80) || ''
                });
            }
            return { total: icons.length, items: results };
        }
    """)
    print(f"\nAlert icon SVGs: {json.dumps(alert_icons, indent=2)}")

    # Step 4: Hover over the first alert icon and check if hover card appears
    if trigger_info['items']:
        first_trigger = trigger_info['items'][0]
        print(f"\nHovering over first trigger at ({first_trigger['rect']['x'] + first_trigger['rect']['w']/2}, {first_trigger['rect']['y'] + first_trigger['rect']['h']/2})")

        # Move mouse to the center of the trigger
        center_x = first_trigger['rect']['x'] + first_trigger['rect']['w'] / 2
        center_y = first_trigger['rect']['y'] + first_trigger['rect']['h'] / 2

        page.mouse.move(center_x, center_y)
        time.sleep(1.5)

        # Check if hover card content appeared
        hover_content = page.evaluate("""
            () => {
                const content = document.querySelector('[data-slot="hover-card-content"]');
                if (!content) return { found: false };
                const rect = content.getBoundingClientRect();
                return {
                    found: true,
                    text: content.textContent.substring(0, 500),
                    html: content.innerHTML.substring(0, 2000),
                    rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
                    buttons: Array.from(content.querySelectorAll('button')).map(b => ({
                        text: b.textContent.trim(),
                        rect: b.getBoundingClientRect(),
                        classList: Array.from(b.classList)
                    }))
                };
            }
        """)
        print(f"\nHover card content: {json.dumps(hover_content, indent=2)}")

        # Step 5: If hover card is showing buttons, click Editar
        if hover_content.get('found') and hover_content.get('buttons'):
            for btn in hover_content['buttons']:
                if 'Editar' in btn.get('text', '') or 'editar' in btn.get('text', '').lower():
                    print(f"\nClicking Editar button at ({btn['rect']['x'] + btn['rect']['w']/2}, {btn['rect']['y'] + btn['rect']['h']/2})")
                    page.mouse.click(
                        btn['rect']['x'] + btn['rect']['w'] / 2,
                        btn['rect']['y'] + btn['rect']['h'] / 2
                    )
                    time.sleep(2)

                    # Check if Sheet opened
                    sheet = page.evaluate("""
                        () => {
                            const sheet = document.querySelector('[data-slot="sheet-content"]');
                            if (!sheet) return { found: false };
                            const rect = sheet.getBoundingClientRect();
                            return {
                                found: true,
                                rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
                                inputs: Array.from(sheet.querySelectorAll('input')).map(i => ({
                                    id: i.id,
                                    name: i.name,
                                    placeholder: i.placeholder,
                                    value: i.value,
                                    type: i.type,
                                    label: i.getAttribute('aria-label') || ''
                                })),
                                buttons: Array.from(sheet.querySelectorAll('button')).map(b => ({
                                    text: b.textContent.trim().substring(0, 50),
                                    type: b.type
                                })),
                                textPreview: sheet.textContent.substring(0, 500)
                            };
                        }
                    """)
                    print(f"\nSheet content: {json.dumps(sheet, indent=2)}")
                    break

finally:
    session.stop()

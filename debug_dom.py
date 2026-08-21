"""
Debug: Deep DOM investigation - find where Editar buttons actually live.
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

    # Approach 1: Search ALL buttons on the entire page
    print("=== ALL buttons on page ===")
    all_buttons = page.evaluate("""
        () => {
            const buttons = document.querySelectorAll('button');
            const results = [];
            for (const b of buttons) {
                const text = b.textContent.trim();
                if (text.includes('Editar') || text.includes('Excluir') || text.includes('Assoc')) {
                    const r = b.getBoundingClientRect();
                    results.push({
                        text: text.substring(0, 50),
                        tag: b.tagName,
                        visible: r.width > 0 && r.height > 0,
                        rect: { x: r.x, y: r.y, w: r.width, h: r.height },
                        parentSlot: b.parentElement?.getAttribute('data-slot') || '',
                        dataState: b.getAttribute('data-state') || '',
                        disabled: b.disabled
                    });
                }
            }
            return results;
        }
    """)
    print(f"Found {len(all_buttons)} Editar/Excluir/Assoc buttons:")
    for b in all_buttons:
        print(f"  {b}")

    # Approach 2: Search for ALL links (A tags) with edit-related attributes
    print("\n=== Links with edit-related content ===")
    all_links = page.evaluate("""
        () => {
            const links = document.querySelectorAll('a');
            const results = [];
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                const text = a.textContent.trim();
                if (href.includes('edit') || href.includes('nutri') || text.includes('Editar')) {
                    const r = a.getBoundingClientRect();
                    results.push({
                        href: href.substring(0, 100),
                        text: text.substring(0, 50),
                        visible: r.width > 0 && r.height > 0,
                        rect: { x: r.x, y: r.y, w: r.width, h: r.height }
                    });
                }
            }
            return results;
        }
    """)
    print(f"Found {len(all_links)} links:")
    for l in all_links[:10]:
        print(f"  {l}")

    # Approach 3: Hover over the first trigger and capture full outer HTML
    print("\n=== Detailed hover card content analysis ===")
    trigger = page.evaluate("""
        () => {
            const t = document.querySelector('[data-slot="hover-card-trigger"]');
            if (!t) return null;
            const r = t.getBoundingClientRect();
            return { x: r.x + r.width/2, y: r.y + r.height/2 };
        }
    """)
    if trigger:
        page.mouse.move(trigger['x'], trigger['y'])
        time.sleep(1.5)

        hover_detail = page.evaluate("""
            () => {
                const content = document.querySelector('[data-slot="hover-card-content"]');
                if (!content) return { found: false };

                // Get the FULL outer HTML of the hover card
                const outerHTML = content.outerHTML;
                return {
                    found: true,
                    outerHTML: outerHTML.substring(0, 5000),
                    childCount: content.children.length,
                    children: Array.from(content.children).map(c => ({
                        tag: c.tagName,
                        classList: Array.from(c.classList),
                        text: c.textContent.substring(0, 100),
                        childCount: c.children.length,
                        html: c.innerHTML.substring(0, 500)
                    }))
                };
            }
        """)
        print(f"Hover card detail: {json.dumps(hover_detail, indent=2)}")

    # Approach 4: Check if the edit happens via a different mechanism
    # Maybe clicking on the card popover trigger opens a popover with an edit button
    print("\n=== Popover content after clicking card ===")
    page.mouse.move(0, 0)
    time.sleep(0.5)

    # Click on the first food card
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
    if first_card:
        print(f"Clicking card: {first_card['text']}")
        page.mouse.click(first_card['x'], first_card['y'])
        time.sleep(1.5)

        popover = page.evaluate("""
            () => {
                const content = document.querySelector('[data-slot="popover-content"]');
                if (!content) return { found: false };
                return {
                    found: true,
                    text: content.textContent.substring(0, 500),
                    html: content.innerHTML.substring(0, 3000),
                    buttons: Array.from(content.querySelectorAll('button')).map(b => ({
                        text: b.textContent.trim().substring(0, 50),
                        rect: b.getBoundingClientRect()
                    })),
                    links: Array.from(content.querySelectorAll('a')).map(a => ({
                        text: a.textContent.trim().substring(0, 50),
                        href: a.getAttribute('href')
                    }))
                };
            }
        """)
        print(f"Popover content: {json.dumps(popover, indent=2)}")

    # Approach 5: Look at ALL elements with 'data-slot' attribute
    print("\n=== All data-slot elements ===")
    slots = page.evaluate("""
        () => {
            const elements = document.querySelectorAll('[data-slot]');
            const slotTypes = {};
            for (const el of elements) {
                const slot = el.getAttribute('data-slot');
                if (!slotTypes[slot]) slotTypes[slot] = 0;
                slotTypes[slot]++;
            }
            return slotTypes;
        }
    """)
    print(f"Slot types: {json.dumps(slots, indent=2)}")

finally:
    session.stop()

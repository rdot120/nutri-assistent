"""
Debug: encontrar o botão de edição usando React internals.
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

    print("=== Procurando botão de edição via React fiber ===")

    # Encontrar o primeiro card
    first_card_text = session.page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                const text = card.textContent.trim();
                if (text.length > 2) return text;
            }
            return null;
        }
    """)
    print(f"Primeiro card: {first_card_text}")

    # Usar React internals para encontrar o EditButton
    result = session.page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                const text = card.textContent.trim();
                if (text !== first_card_text) continue;

                // Encontrar React fiber
                const fiberKey = Object.keys(card).find(k => k.startsWith('__reactFiber'));
                if (!fiberKey) continue;

                let fiber = card[fiberKey];
                const components = [];

                // Subir na árvore de fiber
                let depth = 0;
                while (fiber && depth < 30) {
                    if (fiber.memoizedProps) {
                        const props = fiber.memoizedProps;
                        // Procurar por onClick que parece ser de edição
                        if (props.onClick && typeof props.onClick === 'function') {
                            const onClickStr = props.onClick.toString().substring(0, 200);
                            components.push({
                                depth: depth,
                                type: fiber.type?.name || fiber.type?.displayName || String(fiber.type).substring(0, 50),
                                hasOnClick: true,
                                onClickPreview: onClickStr
                            });
                        }
                    }
                    fiber = fiber.return;
                    depth++;
                }

                return { cardText: text, components: components };
            }
            return null;
        }
    """)
    print(f"\nReact components encontrados:")
    if result:
        for c in result['components']:
            print(f"  depth={c['depth']} type={c['type']} onClick={c['onClickPreview'][:100]}")

    # Agora procurar o componente que carrega o nutricional
    print("\n=== Procurando loadNutriEdit ===")
    load_result = session.page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
            for (const card of cards) {
                const text = card.textContent.trim();
                if (text !== first_card_text) continue;

                const fiberKey = Object.keys(card).find(k => k.startsWith('__reactFiber'));
                if (!fiberKey) continue;

                let fiber = card[fiberKey];
                let depth = 0;

                while (fiber && depth < 30) {
                    if (fiber.memoizedProps) {
                        const props = fiber.memoizedProps;
                        if (props.onClick) {
                            const src = props.onClick.toString();
                            if (src.includes('nutri') || src.includes('Nutri') ||
                                src.includes('edit') || src.includes('Edit') ||
                                src.includes('load') || src.includes('Load')) {
                                return {
                                    depth: depth,
                                    type: fiber.type?.name || fiber.type?.displayName || 'unknown',
                                    onClickFull: src.substring(0, 500)
                                };
                            }
                        }
                    }
                    fiber = fiber.return;
                    depth++;
                }
                break;
            }
            return null;
        }
    """)
    if load_result:
        print(f"  depth={load_result['depth']} type={load_result['type']}")
        print(f"  onClick: {load_result['onClickFull']}")

    # Tentar abordagem diferente: procurar por server actions no window
    print("\n=== Procurando server actions ===")
    actions_result = session.page.evaluate("""
        () => {
            // Procurar por funções de server action no window.__next_f
            const results = [];
            if (window.__next_f) {
                for (const item of window.__next_f) {
                    if (Array.isArray(item) && item.length > 1) {
                        const str = String(item[1]);
                        if (str.includes('loadNutriEdit') || str.includes('formNutricional')) {
                            results.push(str.substring(0, 300));
                        }
                    }
                }
            }
            return results;
        }
    """)
    print(f"  Found: {len(actions_result)} items")
    for r in actions_result[:3]:
        print(f"    {r[:200]}")

    # Tentar chamar loadNutriEdit diretamente
    print("\n=== Tentando chamar loadNutriEdit via server action ===")
    nutri_result = session.page.evaluate("""
        async () => {
            try {
                // Encontrar o idNutricional do primeiro card
                const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
                let targetCard = null;
                for (const card of cards) {
                    const text = card.textContent.trim();
                    if (text === '""" + (first_card_text or "") + """') {
                        targetCard = card;
                        break;
                    }
                }

                if (!targetCard) return { error: 'Card not found' };

                // Tentar encontrar o idNutricional nos props do React
                const fiberKey = Object.keys(targetCard).find(k => k.startsWith('__reactFiber'));
                if (!fiberKey) return { error: 'No React fiber' };

                let fiber = targetCard[fiberKey];
                let depth = 0;
                let nutriId = null;

                while (fiber && depth < 30) {
                    if (fiber.memoizedProps) {
                        const props = fiber.memoizedProps;
                        if (props.nutri && props.nutri.id) {
                            nutriId = props.nutri.id;
                            break;
                        }
                        if (props.idNutricional) {
                            nutriId = props.idNutricional;
                            break;
                        }
                    }
                    if (fiber.memoizedState) {
                        // Check state
                    }
                    fiber = fiber.return;
                    depth++;
                }

                if (!nutriId) return { error: 'Could not find nutri ID', depth: depth };

                return { nutriId: nutriId, cardText: '""" + (first_card_text or "") + """' };
            } catch(e) {
                return { error: e.message };
            }
        }
    """)
    print(f"  Result: {json.dumps(nutri_result, indent=2)}")

    # Se encontrou o ID, tentar chamar loadNutriEdit
    if nutri_result and nutri_result.get('nutriId'):
        nutri_id = nutri_result['nutriId']
        print(f"\n=== Chamando loadNutriEdit({nutri_id}) ===")

        edit_result = session.page.evaluate(f"""
            async () => {{
                try {{
                    // Usar a server action indiretamente
                    // Procurar por todas as funções disponíveis
                    const scripts = document.querySelectorAll('script');
                    let actionFound = false;

                    // Tentar usar fetch com a URL correta
                    const resp = await fetch('/nutri', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Next-Action': 'true',
                        }},
                        body: JSON.stringify({{ id: {nutri_id} }}),
                    }});

                    return {{
                        status: resp.status,
                        ok: resp.ok,
                        url: resp.url,
                        contentType: resp.headers.get('content-type'),
                    }};
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)
        print(f"  Result: {json.dumps(edit_result, indent=2)}")

finally:
    session.stop()

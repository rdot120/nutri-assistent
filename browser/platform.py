"""
Interação com a plataforma Tecnosoft Balanças.
Leitura de cards, campos, e preenchimento de dados nutricionais.

Fluxo de edição:
  1. Clicar no card (popover-trigger) → abre Popover
  2. Clicar no ícone square-pen (dialog-trigger dentro do popover) → abre Dialog "Editar Nutricional"
  3. Preencher campos obrigatórios (tab "Campos Obrigatórios")
  4. Opcionalmente: tab "Campos Extras" → "Clique aqui" → Dialog de extras
  5. Clicar Salvar → fecha Dialog
"""
import time
import logging
import json
import re
from typing import Optional
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class PlatformInteraction:
    """Interage com a plataforma de nutricionais."""

    SELECTORS = {
        "card": '[data-slot="popover-trigger"]',
        "card_content": '[data-slot="card-content"]',
        "search_input": 'input[placeholder*="Procure"]',
        "popover_content": '[data-slot="popover-content"]',
        "dialog_trigger_edit": '[data-slot="popover-content"] [data-slot="dialog-trigger"]:first-child',
        "dialog_content": '[data-slot="dialog-content"]',
        "save_button": 'button[type="submit"][data-slot="button"]',
        "close_button": '[data-slot="dialog-close"]',
        "tabs_trigger": '[data-slot="tabs-trigger"]',
        "tabs_content": '[data-slot="tabs-content"]',
        "extra_fields_trigger": '[data-slot="tabs-content"] [data-slot="dialog-trigger"]',
        "filter_buttons": {
            "todos": 'button:has-text("Todos")',
            "associados": 'button:has-text("Associado")',
            "nao_associados": 'button:has-text("Não associado")',
            "checados": 'button:has-text("Checado")',
        },
    }

    # Campos obrigatórios (RDC 429) - mapeamento nome do campo → rótulo amigável
    MANDATORY_FIELDS = {
        "descricaoProduto": "Descrição",
        "quantidadePorcao": "Qtd Porção",
        "unidadePorcao429": "Unid Porção",
        "parteInteiraMedidaCaseira429": "Parte Inteira Caseira",
        "parteDecimalMedidaCaseira429": "Parte Decimal Caseira",
        "medidaCaseiraUtilizada": "Medida Caseira",
        "valorEnergetico429": "Valor Energético (kcal)",
        "carboidratos429": "Carboidratos (g)",
        "acucaresTotais429": "Açúcares Totais (g)",
        "acucaresAdicionados": "Açúcares Adicionados (g)",
        "lactose": "Lactose (g)",
        "galactose": "Galactose (g)",
        "proteinas429": "Proteínas (g)",
        "gordurasTotais429": "Gorduras Totais (g)",
        "gordurasSaturadas429": "Gorduras Saturadas (g)",
        "gordurasTrans429": "Gorduras Trans (g)",
        "fibraAlimentar429": "Fibra Alimentar (g)",
        "sodio429": "Sódio (mg)",
    }

    # Campos extras (Campos Extras dialog)
    EXTRA_FIELDS = {
        "acidoLinoleico": "Ácido Linoléico",
        "acidoLinolenico": "Ácido Linolênico",
        "acidoOleico": "Ácido Oleico",
        "acidoAraquidonico": "Ácido Araquidônico",
        "calcio": "Cálcio",
        "cloreto": "Cloreto",
        "cobre": "Cobre",
        "colesterol": "Colesterol",
        "colina": "Colina",
        "cromo": "Cromo",
        "acidoDocosaexaenoico": "Ácido Docosaexaenoico",
        "acidoEicosapentaenoico": "Ácido Eicosapentaenoico",
        "ferro": "Ferro",
        "fluor": "Flúor",
        "fósforo": "Fósforo",
        "gordurasMonoInsaturadas": "Gorduras Monoinsaturadas",
        "gordurasPoliInsaturadas": "Gorduras Poliinsaturadas",
        "iodo": "Iodo",
        "magnesio": "Magnésio",
        "manganes": "Manganês",
        "molibdenio": "Molibdênio",
        "nucleotideos": "Nucleotídeos",
        "omega3": "Omega 3",
        "omega6": "Omega 6",
        "omega9": "Omega 9",
        "potassio": "Potássio",
        "selenio": "Selênio",
        "taurina": "Taurina",
        "vitaminaA": "Vitamina A",
        "vitaminaB1": "Vitamina B1",
        "vitaminaB12": "Vitamina B12",
        "vitaminaB2": "Vitamina B2",
        "vitaminaB3": "Vitamina B3",
        "vitaminaB5": "Vitamina B5",
        "vitaminaB6": "Vitamina B6",
        "vitaminaB7": "Vitamina B7",
        "vitaminaB9": "Vitamina B9",
        "vitaminaC": "Vitamina C",
        "vitaminaD": "Vitamina D",
        "vitaminaE": "Vitamina E",
        "vitaminaK": "Vitamina K",
        "zinco": "Zinco",
    }

    # Todos os campos juntos
    ALL_FIELDS = {**MANDATORY_FIELDS, **EXTRA_FIELDS}

    def __init__(self, page: Page):
        self.page = page

    def navigate_to_nutri(self, nutri_url: str) -> bool:
        """Navega para a página de nutricionais."""
        logger.info(f"Navegando para: {nutri_url}")
        self.page.goto(nutri_url, wait_until="networkidle", timeout=30000)
        time.sleep(3)
        cards = self.get_cards_count()
        if cards > 0:
            logger.info(f"Página carregada: {cards} nutricionais")
            return True
        logger.error("Página não carregou corretamente")
        return False

    def get_cards_count(self) -> int:
        """Retorna número total de cards de alimento visíveis."""
        return self.page.evaluate("""
            () => {
                const triggers = document.querySelectorAll('[data-slot="popover-trigger"]');
                let count = 0;
                for (const t of triggers) {
                    if (t.tagName === 'DIV' && t.textContent.trim().length > 2) count++;
                }
                return count;
            }
        """)

    def get_all_foods_with_status(self) -> list[dict]:
        """
        Lista todos os nutricionais da pagina com status de preenchimento e revisao.
        Detecta pelo conteudo do card (texto, badges, icons) sem abrir dialog.
        """
        foods = self.page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
                return Array.from(cards).map((card, index) => {
                    if (card.tagName !== 'DIV') return null;
                    const text = card.textContent.trim();
                    if (text.length < 3) return null;

                    const lowerText = text.toLowerCase();

                    // Detectar se conferido/checado/revisado
                    const reviewed = lowerText.includes('conferido') ||
                                     lowerText.includes('conferida') ||
                                     lowerText.includes('checado') ||
                                     lowerText.includes('checada') ||
                                     lowerText.includes('revisado') ||
                                     lowerText.includes('revisada');

                    // Detectar se preenchido: procurar badges/indicadores visuais
                    // na plataforma, cards preenchidos geralmente tem cor diferenciada
                    // ou badges de status. Vamos verificar pela ausencia de indicadores
                    // de "vazio" e presenca de dados nutricionais visiveis.
                    const badges = card.querySelectorAll('[data-slot="badge"], span[class*="badge"]');
                    let hasFilledBadge = false;
                    let filledText = '';
                    for (const badge of badges) {
                        const bt = badge.textContent.trim().toLowerCase();
                        if (bt.includes('preenchido') || bt.includes('completo') ||
                            bt.includes('ok') || bt.includes('valido')) {
                            hasFilledBadge = true;
                            filledText = bt;
                        }
                    }

                    // Verificar temas de cor do card (cards preenchidos podem ter bg diferente)
                    const computedStyle = window.getComputedStyle(card);
                    const bgColor = computedStyle.backgroundColor;

                    return {
                        index: index,
                        name: text,
                        reviewed: reviewed,
                        hasFilledBadge: hasFilledBadge,
                        filledText: filledText,
                        bgColor: bgColor,
                    };
                }).filter(Boolean);
            }
        """)
        logger.info(f"Total de nutricionais: {len(foods)}")
        return foods

    def get_card_names(self) -> list[str]:
        """Nomes de todos os cards presentes no DOM (sem precisar rolar)."""
        return self.page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
                return Array.from(cards)
                    .filter(c => c.tagName === 'DIV' && c.textContent.trim().length > 2)
                    .map(c => c.textContent.trim());
            }
        """)

    def _scroll_grid_top(self):
        """Rola a janela para o topo (a barra de filtros nao e fixa)."""
        self.page.evaluate("() => window.scrollTo(0, 0)")
        time.sleep(0.4)

    def _click_filter(self, pattern: str) -> int:
        """
        Clica em um filtro da barra lateral e retorna o contador do botao.

        Os filtros sao tabs Radix e exigem clique de mouse real
        (eventos de ponteiro), entao localizamos o botao por texto,
        marcamos com um atributo temporario e clicamos via Playwright.
        A barra rola junto com o conteudo, entao volta ao topo antes.
        """
        self._scroll_grid_top()
        token = f"ppf-{int(time.time() * 1000)}"
        found = self.page.evaluate(
            """
            (args) => {
                const rx = new RegExp(args.pattern);
                const btns = Array.from(document.querySelectorAll('button'));
                const target = btns.find(
                    b => rx.test((b.textContent || '').trim())
                );
                if (!target) return null;
                const m = (target.textContent || '').match(/(\\d+)/);
                target.setAttribute('data-pp-filter', args.token);
                return { count: m ? parseInt(m[1], 10) : null };
            }
            """,
            {"pattern": pattern, "token": token},
        )
        if not found:
            logger.warning(f"Filtro nao encontrado: {pattern}")
            return 0

        self.page.locator(f'[data-pp-filter="{token}"]').click()
        time.sleep(1.2)
        self.page.evaluate(
            "(t) => { const el = document.querySelector("
            "`[data-pp-filter='${t}']`);"
            " if (el) el.removeAttribute('data-pp-filter'); }",
            token,
        )
        return found.get("count") or 0

    def capture_filter_sets(self) -> dict:
        """
        Captura os conjuntos de cards por filtro da barra lateral.

        A barra lateral rola junto com o grid, entao cada clique exige
        voltar ao topo da grade. No fim restaura o filtro "Todos".

        Retorna:
        {
          "counts": {"total": n, "associados": n, "checados": n},
          "names": {"total": [...], "associados": [...], "checados": [...]},
        }
        """
        filters = [
            ("total", r"^Todos\s*\d+$"),
            ("associados", r"^Associado\(s\)\s*\d+$"),
            ("checados", r"^Checado por nutricionista\s*\d+$"),
        ]

        counts = {}
        names = {}
        for key, pattern in filters:
            counts[key] = self._click_filter(pattern)
            names[key] = self.get_card_names()
            logger.info(
                f"Filtro {key}: contador={counts[key]}, "
                f"cards no DOM={len(names[key])}"
            )

        # Restaurar filtro "Todos" e posicao do scroll
        self._click_filter(r"^Todos\s*\d+$")

        return {"counts": counts, "names": names}

    def search_food(self, query: str) -> int:
        """Busca nutricional por nome. Retorna número de resultados."""
        search = self.page.query_selector(self.SELECTORS["search_input"])
        if search:
            search.fill(query)
            time.sleep(1)
            count = self.get_cards_count()
            logger.debug(f"Busca '{query}': {count} resultados")
            return count
        return 0

    def clear_search(self):
        """Limpa busca."""
        try:
            search = self.page.query_selector(self.SELECTORS["search_input"])
            if search:
                search.fill("")
                time.sleep(1)
        except Exception:
            # Pagina pode ter navegado
            time.sleep(1)

    def _close_all_popups(self):
        """Fecha popups abertos (popover, dialog, etc.)."""
        try:
            self.page.keyboard.press("Escape")
            time.sleep(0.3)
            self.page.keyboard.press("Escape")
            time.sleep(0.3)
        except Exception:
            # Pagina pode ter navegado apos save
            time.sleep(1)
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

    def open_edit_dialog(self, food_name: str) -> bool:
        """
        Abre o dialog de edição para um nutricional.
        Fluxo: card click → popover → square-pen click → dialog
        """
        logger.info(f"Abrindo edição para: {food_name}")

        # Fechar qualquer popup aberto
        self._close_all_popups()

        # Buscar o alimento
        self.search_food(food_name)
        time.sleep(1)

        # Encontrar e clicar no card
        card_pos = self.page.evaluate("""
            (foodName) => {
                const cards = document.querySelectorAll('[data-slot="popover-trigger"]');
                let bestMatch = null;
                let bestScore = 0;
                for (const card of cards) {
                    if (card.tagName !== 'DIV') continue;
                    const cardText = card.textContent.trim();
                    if (cardText.length < 3) continue;
                    const r = card.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    const searchUpper = foodName.trim().toUpperCase();
                    const cardUpper = cardText.toUpperCase();
                    let score = 0;
                    if (cardUpper === searchUpper) score = 100;
                    else if (cardUpper.includes(searchUpper)) score = 80;
                    else if (searchUpper.includes(cardUpper)) score = 70;
                    if (score > bestScore) {
                        bestScore = score;
                        bestMatch = { x: r.x + r.width/2, y: r.y + r.height/2, text: cardText, score: score };
                    }
                }
                return bestMatch;
            }
        """, food_name)

        if not card_pos:
            logger.error(f"Card não encontrado: {food_name}")
            self.clear_search()
            return False

        # Clicar no card → abre popover
        self.page.mouse.click(card_pos['x'], card_pos['y'])
        time.sleep(1.5)

        # Verificar se popover abriu
        popover = self.page.query_selector(self.SELECTORS["popover_content"])
        if not popover:
            logger.error("Popover não abriu")
            self.clear_search()
            return False

        # Encontrar e clicar no ícone square-pen (primeiro dialog-trigger)
        edit_btn = self.page.evaluate("""
            () => {
                const popover = document.querySelector('[data-slot="popover-content"]');
                if (!popover) return null;
                const triggers = popover.querySelectorAll('[data-slot="dialog-trigger"]');
                if (triggers.length === 0) return null;
                const t = triggers[0];
                const r = t.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    return { x: r.x + r.width/2, y: r.y + r.height/2 };
                }
                return null;
            }
        """)

        if not edit_btn:
            logger.error("Botão de edição não encontrado no popover")
            self.page.keyboard.press("Escape")
            self.clear_search()
            return False

        # Clicar no square-pen → abre dialog
        self.page.mouse.click(edit_btn['x'], edit_btn['y'])

        # Aguardar dialog aparecer
        for _ in range(20):
            time.sleep(0.5)
            dialog = self.page.evaluate("""
                () => {
                    const d = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                    if (!d) return null;
                    const inputs = d.querySelectorAll('input[type="text"], select');
                    return {
                        title: d.querySelector('[data-slot="dialog-title"]')?.textContent || '',
                        inputCount: inputs.length
                    };
                }
            """)
            if dialog and dialog.get('inputCount', 0) > 0:
                logger.info(f"Dialog de edição aberto: {dialog['title']} ({dialog['inputCount']} campos)")
                return True

        logger.warning(f"Dialog não abriu completamente para: {food_name}")
        self._close_all_popups()
        self.clear_search()
        return False

    def get_form_fields(self, context: str = "main") -> list[dict]:
        """
        Lista campos do formulário de edição.
        context: 'main' para campos obrigatórios, 'extras' para campos extras.
        """
        if context == "extras":
            return self._get_extra_fields()

        fields = self.page.evaluate("""
            () => {
                const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                if (!dialog) return [];
                const labels = dialog.querySelectorAll('label');
                const results = [];
                for (const label of labels) {
                    const text = label.textContent.trim();
                    let input = null;
                    let sib = label.nextElementSibling;
                    for (let i = 0; i < 5 && sib; i++) {
                        if (sib.tagName === 'INPUT' || sib.tagName === 'SELECT' || sib.tagName === 'TEXTAREA') {
                            input = sib; break;
                        }
                        const inner = sib.querySelector('input, select, textarea');
                        if (inner) { input = inner; break; }
                        sib = sib.nextElementSibling;
                    }
                    if (input) {
                        const field = {
                            label: text,
                            name: input.name || '',
                            tag: input.tagName.toLowerCase(),
                            type: input.type || input.tagName.toLowerCase(),
                            value: input.value || '',
                            placeholder: input.placeholder || '',
                            readOnly: input.readOnly || false,
                            disabled: input.disabled || false
                        };
                        if (input.tagName === 'SELECT') {
                            field.options = Array.from(input.querySelectorAll('option')).map(o => ({
                                value: o.value,
                                text: o.textContent.trim(),
                                selected: o.selected
                            }));
                        }
                        if (input.type === 'checkbox') {
                            field.checked = input.checked;
                        }
                        results.push(field);
                    }
                }
                return results;
            }
        """)
        logger.info(f"Campos [{context}]: {len(fields)}")
        return fields

    def _get_extra_fields(self) -> list[dict]:
        """Retorna campos do dialog de extras (se aberto)."""
        fields = self.page.evaluate("""
            () => {
                const dialogs = document.querySelectorAll('[data-slot="dialog-content"][data-state="open"]');
                for (const dialog of dialogs) {
                    const title = dialog.querySelector('[data-slot="dialog-title"]');
                    if (!title || !title.textContent.includes('Selecione')) continue;

                    const labels = dialog.querySelectorAll('label');
                    const results = [];
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
                            results.push({
                                label: text,
                                name: input.name || '',
                                type: input.type || input.tagName.toLowerCase(),
                                value: input.value || ''
                            });
                        }
                    }
                    if (results.length > 0) return results;
                }
                return [];
            }
        """)
        logger.info(f"Campos extras: {len(fields)}")
        return fields

    def set_field_value(self, field_name: str, value: str, context: str = "main") -> bool:
        """
        Define o valor de um campo no formulário.
        Usa nativeInputValueSetter para funcionar com React.
        """
        try:
            escaped_value = value.replace("\\", "\\\\").replace("'", "\\'")
            result = self.page.evaluate(f"""
                (fieldInfo) => {{
                    const dialogs = document.querySelectorAll('[data-slot="dialog-content"][data-state="open"]');
                    for (const dialog of dialogs) {{
                        let input = dialog.querySelector('[name="{field_name}"]');
                        if (!input) continue;
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        )?.set;
                        if (nativeInputValueSetter) {{
                            nativeInputValueSetter.call(input, '{escaped_value}');
                        }} else {{
                            input.value = '{escaped_value}';
                        }}
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}
            """)
            if result:
                logger.debug(f"Campo {field_name} = {value}")
            return result
        except Exception as e:
            logger.error(f"Erro ao definir {field_name}: {e}")
            return False

    def set_select_value(self, field_name: str, value: str) -> bool:
        """Define valor de um select nativo."""
        try:
            result = self.page.evaluate(f"""
                () => {{
                    const dialogs = document.querySelectorAll('[data-slot="dialog-content"][data-state="open"]');
                    for (const dialog of dialogs) {{
                        const select = dialog.querySelector('[name="{field_name}"]');
                        if (!select) continue;
                        select.value = '{value}';
                        select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}
            """)
            return result
        except Exception as e:
            logger.error(f"Erro ao definir select {field_name}: {e}")
            return False

    def get_field_value(self, field_name: str) -> Optional[str]:
        """Retorna o valor de um campo no formulário."""
        value = self.page.evaluate(f"""
            () => {{
                const dialogs = document.querySelectorAll('[data-slot="dialog-content"][data-state="open"]');
                for (const dialog of dialogs) {{
                    const input = dialog.querySelector('[name="{field_name}"]');
                    if (input) return input.value;
                }}
                return null;
            }}
        """)
        return value

    def get_nutritional_data(self) -> dict:
        """Lê todos os dados nutricionais do dialog de edição aberto."""
        data = {}
        for field_key in self.ALL_FIELDS:
            value = self.get_field_value(field_key)
            if value is not None and value != "":
                data[field_key] = value
        logger.debug(f"Dados lidos: {len(data)} campos")
        return data

    def read_back_after_save(self, food_name: str,
                             expected_fields: dict) -> dict:
        """
        Apos salvar, relê os campos para confirmar persistencia.
        Abre o dialog novamente, le os valores, fecha o dialog.
        Retorna dict de campos lidos ou vazio se falhar.
        """
        try:
            time.sleep(1.5)
            if not self.open_edit_dialog(food_name):
                logger.warning(
                    f"Nao foi possivel reabrir dialog para verificacao: "
                    f"{food_name}"
                )
                return {}

            time.sleep(0.5)
            readback = {}
            for field_key in expected_fields:
                value = self.get_field_value(field_key)
                if value is not None:
                    readback[field_key] = value

            self._close_all_popups()
            logger.info(
                f"Read-back para {food_name}: {len(readback)}/"
                f"{len(expected_fields)} campos relidos"
            )
            return readback

        except Exception as e:
            logger.warning(f"Erro no read-back de {food_name}: {e}")
            try:
                self._close_all_popups()
            except Exception:
                pass
            return {}

    def fill_nutritional_data(self, data: dict) -> dict:
        """
        Preenche campos nutricionais no formulário.
        Usa select triggers para selects do Radix UI e nativeInputValueSetter para inputs.
        Retorna campos preenchidos com sucesso.
        """
        filled = {}
        for field_key, value in data.items():
            if value is None or value == "":
                continue

            # Verificar se é select
            field_info = self.page.evaluate(f"""
                () => {{
                    const dialogs = document.querySelectorAll('[data-slot="dialog-content"][data-state="open"]');
                    for (const dialog of dialogs) {{
                        const el = dialog.querySelector('[name="{field_key}"]');
                        if (el) return {{ found: true, tag: el.tagName, type: el.type }};
                    }}
                    return {{ found: false }};
                }}
            """)

            if not field_info.get('found'):
                continue

            if field_info.get('tag') == 'SELECT':
                success = self.set_select_value(field_key, str(value))
            else:
                success = self.set_field_value(field_key, str(value))

            if success:
                filled[field_key] = value

        logger.info(f"Campos preenchidos: {len(filled)}/{len(data)}")
        return filled

    def click_save(self) -> bool:
        """
        Clica no botão Salvar dentro do dialog de edição.
        O botão Salvar é um submit button associado ao form via atributo 'form',
        posicionado no canto superior direito do dialog (tooltip-trigger).
        Também suporta Enter como fallback.
        """
        # Primeiro: tentar clicar no botão submit associado ao form
        result = self.page.evaluate("""
            () => {
                const form = document.querySelector('#form-nutri-add');
                if (!form) return null;

                // Procurar botão submit fora do form mas associado via form attribute
                const allSubmit = document.querySelectorAll('button[type="submit"]');
                for (const btn of allSubmit) {
                    if (btn.form && btn.form.id === 'form-nutri-add') {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            return { x: r.x + r.width/2, y: r.y + r.height/2 };
                        }
                    }
                }

                // Fallback: procurar dentro do dialog
                const dialog = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                if (dialog) {
                    const btns = dialog.querySelectorAll('button[type="submit"]');
                    for (const btn of btns) {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            return { x: r.x + r.width/2, y: r.y + r.height/2 };
                        }
                    }
                }
                return null;
            }
        """)

        if result:
            self.page.mouse.click(result['x'], result['y'])
        else:
            # Fallback: usar Enter para submeter o form
            logger.info("Botao nao encontrado, tentando Enter")
            self.page.keyboard.press("Enter")

        # Aguardar possivel navegacao pos-save
        try:
            self.page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        time.sleep(2)

        # Verificar se dialog fechou ou toast de sucesso
        try:
            dialog_still_open = self.page.evaluate("""
                () => {
                    const d = document.querySelector('[data-slot="dialog-content"][data-state="open"]');
                    const title = d?.querySelector('[data-slot="dialog-title"]')?.textContent || '';
                    return title.includes('Editar');
                }
            """)
        except Exception:
            # Pagina pode ter navegado, considerar salvamento
            dialog_still_open = False

        if not dialog_still_open:
            logger.info("Salvamento confirmado (dialog fechado)")
            return True

        # Verificar toast
        toast = self.page.evaluate("""
            () => {
                const toasts = document.querySelectorAll('[role="status"], [data-sonner-toaster] li');
                for (const t of toasts) {
                    const text = t.textContent || '';
                    if (text.toLowerCase().includes('sucesso') ||
                        text.toLowerCase().includes('success') ||
                        text.toLowerCase().includes('atualizado')) {
                        return text;
                    }
                }
                return null;
            }
        """)
        if toast:
            logger.info(f"Toast: {toast}")
            return True

        logger.warning("Nao foi possivel confirmar salvamento")
        return False

    def close_edit_dialog(self):
        """Fecha o dialog de edição."""
        self.page.keyboard.press("Escape")
        time.sleep(0.5)

    def get_nutritional_code(self) -> Optional[str]:
        """Retorna o código nutricional do popover aberto."""
        return self.page.evaluate("""
            () => {
                const popover = document.querySelector('[data-slot="popover-content"]');
                if (!popover) return null;
                const text = popover.textContent;
                const match = text.match(/C[óo]d\\. Nutricional:\\s*(\\d+)/i);
                return match ? match[1] : null;
            }
        """)

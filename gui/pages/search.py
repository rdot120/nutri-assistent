"""
Pagina de pesquisa de alimentos.
Busca em TBCA, USDA e mostra informacoes nutricionais.
"""
import time
import threading
import customtkinter as ctk
from tkinter import messagebox

from ..theme import COLORS, FONTS
from ..widgets import ActionButton, TreeviewFrame, LogPanel


# Campos nutricionais principais (para exibicao)
NUTRIENT_FIELDS = [
    ("energia_kcal", "Energia (kcal)"),
    ("carboidrato_total", "Carboidratos (g)"),
    ("proteina", "Proteinas (g)"),
    ("lipidios_totais", "Gorduras Totais (g)"),
    ("gorduras_saturadas", "Gorduras Saturadas (g)"),
    ("gorduras_trans", "Gorduras Trans (g)"),
    ("fibra_alimentar", "Fibra Alimentar (g)"),
    ("acucares_totais", "Acucares Totais (g)"),
    ("sodio", "Sodio (mg)"),
    ("colesterol", "Colesterol (mg)"),
    ("calcio", "Calcio (mg)"),
    ("ferro", "Ferro (mg)"),
    ("fosforo", "Fosforo (mg)"),
    ("magnesio", "Magnesio (mg)"),
    ("potassio", "Potassio (mg)"),
    ("zinco", "Zinco (mg)"),
    ("vitamina_a_rae", "Vitamina A (mcg)"),
    ("vitamina_c", "Vitamina C (mg)"),
    ("vitamina_d_total", "Vitamina D (mcg)"),
    ("vitamina_e", "Vitamina E (mg)"),
    ("tiamina", "Vitamina B1 (mg)"),
    ("riboflavina", "Vitamina B2 (mg)"),
    ("niacina", "Vitamina B3 (mg)"),
    ("vitamina_b6", "Vitamina B6 (mg)"),
    ("folato", "Folato (mcg)"),
    ("vitamina_b12", "Vitamina B12 (mcg)"),
]


class SearchPage(ctk.CTkFrame):
    """Pagina de pesquisa de alimentos."""

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        self._results = []

        self._build_header()
        self._build_search()
        self._build_results_table()
        self._build_detail_panel()

    def _build_header(self):
        ctk.CTkLabel(
            self, text="Pesquisa de Alimentos",
            font=FONTS["title"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            self, text="Busque informacoes nutricionais em TBCA, USDA e outras fontes.",
            font=FONTS["body"], text_color=COLORS["text_soft"],
            anchor="w"
        ).pack(fill="x", padx=24)

    def _build_search(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=24, pady=(12, 8))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            row, text="Buscar:", font=FONTS["body_bold"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        self._search_entry = ctk.CTkEntry(
            row, placeholder_text="Ex: arroz, frango, leite...",
            font=FONTS["body"], width=350, corner_radius=6
        )
        self._search_entry.pack(side="left", padx=(0, 8))
        self._search_entry.bind("<Return>", lambda e: self._do_search())

        # Filtros de fonte
        self._var_tbca = ctk.BooleanVar(value=True)
        self._var_usda = ctk.BooleanVar(value=True)
        self._var_ai = ctk.BooleanVar(value=False)

        ctk.CTkCheckBox(
            row, text="TBCA", variable=self._var_tbca,
            font=FONTS["small"], fg_color=COLORS["primary"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

        ctk.CTkCheckBox(
            row, text="USDA", variable=self._var_usda,
            font=FONTS["small"], fg_color=COLORS["primary"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

        ctk.CTkCheckBox(
            row, text="IA", variable=self._var_ai,
            font=FONTS["small"], fg_color=COLORS["accent"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

        ActionButton(
            row, "Buscar", command=self._do_search,
            color=COLORS["primary"], width=80
        ).pack(side="left", padx=(12, 0))

        self._status_label = ctk.CTkLabel(
            row, text="", font=FONTS["small"],
            text_color=COLORS["text_soft"]
        )
        self._status_label.pack(side="right")

    def _build_results_table(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        # Tabela de resultados
        self._table = TreeviewFrame(
            container,
            columns=("source", "name", "category", "code"),
            headings=("Fonte", "Nome", "Categoria", "Codigo"),
            widths=[60, 300, 150, 100]
        )
        self._table.pack(fill="both", expand=True)

        # Bind de selecao
        self._table._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Botao para usar selecionado
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(4, 0))

        ActionButton(
            btn_frame, "Usar para Preenchimento",
            command=self._use_selected,
            color=COLORS["accent"]
        ).pack(side="left")

        ActionButton(
            btn_frame, "Copiar Valores",
            command=self._copy_values,
            color=COLORS["primary_light"], text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

    def _build_detail_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10, height=250)
        panel.pack(fill="x", padx=24, pady=(0, 12))
        panel.pack_propagate(False)

        ctk.CTkLabel(
            panel, text="Valores Nutricionais (por 100g)",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        # Grid de valores
        self._detail_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self._detail_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._detail_labels = {}
        for i, (key, label) in enumerate(NUTRIENT_FIELDS):
            row = i // 3
            col = (i % 3) * 2

            ctk.CTkLabel(
                self._detail_frame, text=f"{label}:",
                font=FONTS["small"], text_color=COLORS["text_soft"],
                anchor="w"
            ).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=1)

            val_label = ctk.CTkLabel(
                self._detail_frame, text="-",
                font=FONTS["small_bold"], text_color=COLORS["text"],
                anchor="w", width=80
            )
            val_label.grid(row=row, column=col + 1, sticky="w", pady=1)
            self._detail_labels[key] = val_label

    def _do_search(self):
        """Executa busca."""
        query = self._search_entry.get().strip()
        if not query:
            return

        self._status_label.configure(text="Buscando...")
        self._table.clear()
        self._results = []
        self._clear_details()

        def _search():
            try:
                all_results = []

                if self._var_tbca.get():
                    self.after(0, lambda: self._status_label.configure(
                        text="Buscando TBCA..."))
                    tbca_results = self._search_tbca(query)
                    all_results.extend(tbca_results)

                if self._var_usda.get():
                    self.after(0, lambda: self._status_label.configure(
                        text="Buscando USDA..."))
                    usda_results = self._search_usda(query)
                    all_results.extend(usda_results)

                if self._var_ai.get():
                    self.after(0, lambda: self._status_label.configure(
                        text="Buscando via IA..."))
                    ai_results = self._search_ai(query)
                    all_results.extend(ai_results)

                self._results = all_results

                for r in all_results:
                    self.after(0, lambda res=r: self._table.insert((
                        res.get("source", ""),
                        res.get("name", ""),
                        res.get("category", ""),
                        res.get("code", ""),
                    )))

                count = len(all_results)
                self.after(0, lambda: self._status_label.configure(
                    text=f"{count} resultado(s) encontrado(s)"
                ))

            except Exception as e:
                self.after(0, lambda: self._status_label.configure(
                    text=f"Erro: {e}"
                ))

        threading.Thread(target=_search, daemon=True).start()

    def _search_tbca(self, query: str) -> list:
        """Busca no TBCA."""
        from nutrition.tbca import TBCAScraper
        from config.settings import DATA_DIR

        scraper = TBCAScraper(cache_db_path=DATA_DIR / "tbca_cache.db")
        listing = scraper.load_listing_index()

        results = []
        query_lower = query.lower()
        for item in listing:
            name = item.get("name", "")
            if query_lower in name.lower():
                results.append({
                    "source": "TBCA",
                    "name": name,
                    "category": item.get("group", ""),
                    "code": item.get("code", ""),
                    "url": item.get("url", ""),
                    "data": item,
                })
                if len(results) >= 20:
                    break
        return results

    def _search_usda(self, query: str) -> list:
        """Busca no USDA."""
        from nutrition.usda import USDAScraper
        from config.settings import DATA_DIR, Settings

        settings = Settings.load()
        settings.load_env()
        scraper = USDAScraper(
            api_key=settings.usda.api_key,
            cache_db_path=DATA_DIR / "tbca_cache.db"
        )
        foods = scraper.search(query, page_size=10)

        results = []
        for f in foods:
            results.append({
                "source": "USDA",
                "name": f.get("description", ""),
                "category": f.get("food_category", ""),
                "code": f"USDA-{f.get('fdc_id', '')}",
                "fdc_id": f.get("fdc_id", ""),
                "data": f,
            })
        return results

    def _search_ai(self, query: str) -> list:
        """Busca via IA (Gemini/OpenAI/Claude/Ollama)."""
        from nutrition.ai_provider import create_default_finder
        from config.settings import Settings

        settings = Settings.load()
        settings.load_env()
        if not settings.ai.enabled or not settings.ai.api_key:
            return []

        finder = create_default_finder(settings)
        if not finder:
            return []

        result = finder.find_with_result(query)

        if not result.success or not result.fields:
            return []

        nutrients = {}
        for field_key, value in result.fields.items():
            if value is not None and value != "":
                nutrients[field_key] = {
                    "value_per_100g": value
                }

        return [{
            "source": f"IA ({result.provider})",
            "name": query,
            "category": "Consulta IA",
            "code": f"AI-{result.provider}-{int(time.time())}",
            "data": {"nutrients": nutrients, "confidence": result.confidence},
        }]

    def _on_select(self, event):
        """Ao selecionar item na tabela."""
        selection = self._table._tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self._table._tree.item(item, "values")
        source = values[0]
        code = values[3]

        # Buscar dados detalhados
        for r in self._results:
            if r.get("code") == code and r.get("source") == source:
                self._show_details(r)
                break

    def _show_details(self, result: dict):
        """Mostra detalhes nutricionais."""
        source = result.get("source", "")

        if source == "TBCA":
            self._show_tbca_details(result)
        elif source == "USDA":
            self._show_usda_details(result)
        elif "IA" in source:
            self._show_ai_details(result)

    def _show_ai_details(self, result: dict):
        """Mostra detalhes de resultado da IA."""
        data = result.get("data", {})
        nutrients = data.get("nutrients", {})
        for key, label in NUTRIENT_FIELDS:
            nutrient = nutrients.get(key)
            if nutrient:
                val = nutrient.get("value_per_100g", "-")
                self.after(0, lambda k=key, v=str(val):
                           self._update_detail(k, v))
        conf = data.get("confidence", 0)
        self.after(0, lambda: self._status_label.configure(
            text=f"Confianca IA: {conf:.0f}%"
        ))

    def _show_tbca_details(self, result: dict):
        """Mostra detalhes do TBCA."""
        from nutrition.tbca import TBCAScraper
        from config.settings import DATA_DIR

        scraper = TBCAScraper(cache_db_path=DATA_DIR / "tbca_cache.db")
        url = result.get("url", "")

        if not url:
            return

        def _load():
            try:
                food = scraper.fetch_food(url)
                if food and food.nutrients:
                    for key, label in NUTRIENT_FIELDS:
                        nutrient = food.nutrients.get(key)
                        if nutrient:
                            val = nutrient.get("value_per_100g", "-")
                            self.after(0, lambda k=key, v=str(val):
                                       self._update_detail(k, v))
            except Exception as e:
                self.after(0, lambda: self._status_label.configure(
                    text=f"Erro ao carregar detalhes: {e}"
                ))

        threading.Thread(target=_load, daemon=True).start()

    def _show_usda_details(self, result: dict):
        """Mostra detalhes do USDA."""
        from nutrition.usda import USDAScraper
        from config.settings import DATA_DIR, Settings

        settings = Settings.load()
        settings.load_env()
        scraper = USDAScraper(
            api_key=settings.usda.api_key,
            cache_db_path=DATA_DIR / "tbca_cache.db"
        )
        fdc_id = result.get("fdc_id", "")

        if not fdc_id:
            return

        def _load():
            try:
                food = scraper.get_food(fdc_id)
                if food and food.nutrients:
                    for key, label in NUTRIENT_FIELDS:
                        nutrient = food.nutrients.get(key)
                        if nutrient:
                            val = nutrient.get("amount", "-")
                            self.after(0, lambda k=key, v=str(val):
                                       self._update_detail(k, v))
            except Exception as e:
                self.after(0, lambda: self._status_label.configure(
                    text=f"Erro ao carregar detalhes: {e}"
                ))

        threading.Thread(target=_load, daemon=True).start()

    def _update_detail(self, key: str, value: str):
        """Atualiza valor na tela de detalhes."""
        if key in self._detail_labels:
            self._detail_labels[key].configure(text=str(value))

    def _clear_details(self):
        """Limpa detalhes."""
        for label in self._detail_labels.values():
            label.configure(text="-")

    def _use_selected(self):
        """Usa o alimento selecionado para preenchimento manual."""
        selection = self._table._tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um alimento primeiro!")
            return

        item = selection[0]
        values = self._table._tree.item(item, "values")
        source = values[0]
        name = values[1]
        code = values[3]

        # Coletar valores atuais
        data = {}
        for key in self._detail_labels:
            val = self._detail_labels[key].cget("text")
            if val and val != "-":
                data[key] = val

        if not data:
            messagebox.showwarning("Aviso",
                                   "Nenhum valor nutricional carregado!")
            return

        # Abrir dialog de preenchimento manual
        self.app.show_manual_entry(name, source, data)

    def _copy_values(self):
        """Copia valores nutricionais para o clipboard."""
        values = []
        for key, label in NUTRIENT_FIELDS:
            val = self._detail_labels[key].cget("text")
            if val and val != "-":
                values.append(f"{label}: {val}")

        if values:
            self.clipboard_clear()
            self.clipboard_append("\n".join(values))
            self._status_label.configure(text="Valores copiados!")
        else:
            self._status_label.configure(text="Nenhum valor para copiar")

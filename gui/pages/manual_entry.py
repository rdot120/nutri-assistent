"""
Pagina de entrada manual de dados nutricionais.
Permite ao usuario inserir valores para alimentos sem correspondencia.
"""
import time
import threading
import customtkinter as ctk
from tkinter import messagebox

from ..theme import COLORS, FONTS
from ..widgets import ActionButton, TreeviewFrame


# Campos obrigatorios (RDC 429)
MANDATORY_FIELDS = [
    ("valorEnergetico429", "Valor Energetico (kcal)"),
    ("carboidratos429", "Carboidratos (g)"),
    ("acucaresTotais429", "Acucares Totais (g)"),
    ("acucaresAdicionados", "Acucares Adicionados (g)"),
    ("proteinas429", "Proteinas (g)"),
    ("gordurasTotais429", "Gorduras Totais (g)"),
    ("gordurasSaturadas429", "Gorduras Saturadas (g)"),
    ("gordurasTrans429", "Gorduras Trans (g)"),
    ("fibraAlimentar429", "Fibra Alimentar (g)"),
    ("sodio429", "Sodio (mg)"),
    ("lactose", "Lactose (g)"),
    ("galactose", "Galactose (g)"),
]

# Campos extras (opcionais)
EXTRA_FIELDS = [
    ("colesterol", "Colesterol (mg)"),
    ("calcio", "Calcio (mg)"),
    ("ferro", "Ferro (mg)"),
    ("fosforo", "Fosforo (mg)"),
    ("magnesio", "Magnesio (mg)"),
    ("potassio", "Potassio (mg)"),
    ("zinco", "Zinco (mg)"),
    ("vitaminaA", "Vitamina A (mcg)"),
    ("vitaminaB1", "Vitamina B1 (mg)"),
    ("vitaminaB2", "Vitamina B2 (mg)"),
    ("vitaminaB3", "Vitamina B3 (mg)"),
    ("vitaminaB6", "Vitamina B6 (mg)"),
    ("vitaminaB9", "Vitamina B9/Folato (mcg)"),
    ("vitaminaB12", "Vitamina B12 (mcg)"),
    ("vitaminaC", "Vitamina C (mg)"),
    ("vitaminaD", "Vitamina D (mcg)"),
    ("vitaminaE", "Vitamina E (mg)"),
    ("vitaminaK", "Vitamina K (mcg)"),
]


class ManualEntryPage(ctk.CTkFrame):
    """Pagina de entrada manual de dados nutricionais."""

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        self._entries = {}
        self._current_food = None

        self._build_header()
        self._build_food_selector()
        self._build_form()
        self._build_actions()
        self._build_pending_list()

    def _build_header(self):
        ctk.CTkLabel(
            self, text="Preenchimento Manual",
            font=FONTS["title"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            self, text="Preencha dados nutricionais para alimentos sem correspondencia automatica.",
            font=FONTS["body"], text_color=COLORS["text_soft"],
            anchor="w"
        ).pack(fill="x", padx=24)

    def _build_food_selector(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=24, pady=(12, 8))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            row, text="Alimento:", font=FONTS["body_bold"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        self._food_var = ctk.StringVar(value="")
        self._food_search = ctk.CTkEntry(
            row, placeholder_text="Buscar alimento...",
            font=FONTS["body"], width=350, corner_radius=6
        )
        self._food_search.pack(side="left", padx=(0, 8))
        self._food_search.bind("<KeyRelease>", self._filter_foods)

        self._food_list_frame = ctk.CTkScrollableFrame(
            frame, fg_color="transparent", height=120
        )

        self._food_buttons_frame = ctk.CTkFrame(
            self._food_list_frame, fg_color="transparent"
        )
        self._food_buttons_frame.pack(fill="x")

        self._source_label = ctk.CTkLabel(
            row, text="", font=FONTS["small"],
            text_color=COLORS["text_soft"]
        )
        self._source_label.pack(side="left", padx=(8, 0))

        self._all_foods = []
        self._food_buttons = []

    def _build_form(self):
        form = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                            corner_radius=10)
        form.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        # Two columns
        left = ctk.CTkFrame(form, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=12)

        right = ctk.CTkFrame(form, fg_color="transparent")
        right.pack(side="right", fill="both", expand=True, padx=(8, 16), pady=12)

        # Mandatory fields
        ctk.CTkLabel(
            left, text="Campos Obrigatorios (RDC 429)",
            font=FONTS["section"], text_color=COLORS["accent"],
            anchor="w"
        ).pack(fill="x", pady=(0, 8))

        for field_name, label in MANDATORY_FIELDS:
            row = ctk.CTkFrame(left, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row, text=f"{label}:", font=FONTS["small"],
                text_color=COLORS["text"], width=160, anchor="w"
            ).pack(side="left")

            entry = ctk.CTkEntry(
                row, font=FONTS["small"], width=100,
                placeholder_text="0", corner_radius=4
            )
            entry.pack(side="left", padx=(4, 0))
            self._entries[field_name] = entry

        # Extra fields
        ctk.CTkLabel(
            right, text="Campos Extras (Opcionais)",
            font=FONTS["section"], text_color=COLORS["primary"],
            anchor="w"
        ).pack(fill="x", pady=(0, 8))

        for field_name, label in EXTRA_FIELDS:
            row = ctk.CTkFrame(right, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row, text=f"{label}:", font=FONTS["small"],
                text_color=COLORS["text"], width=160, anchor="w"
            ).pack(side="left")

            entry = ctk.CTkEntry(
                row, font=FONTS["small"], width=100,
                placeholder_text="0", corner_radius=4
            )
            entry.pack(side="left", padx=(4, 0))
            self._entries[field_name] = entry

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(0, 8))

        ActionButton(
            frame, "Salvar Entrada", command=self._save_entry,
            color=COLORS["primary"]
        ).pack(side="left")

        ActionButton(
            frame, "Limpar Campos", command=self._clear_fields,
            color=COLORS["border"], text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

        ActionButton(
            frame, "Preencher no Site", command=self._fill_on_site,
            color=COLORS["accent"]
        ).pack(side="right")

        self._status_label = ctk.CTkLabel(
            frame, text="", font=FONTS["small"],
            text_color=COLORS["text_soft"]
        )
        self._status_label.pack(side="right", padx=(0, 12))

    def _build_pending_list(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10, height=150)
        frame.pack(fill="x", padx=24, pady=(0, 12))
        frame.pack_propagate(False)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            header, text="Entradas Pendentes (preenchimento manual)",
            font=FONTS["small_bold"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        ActionButton(
            header, "Limpar Todas", command=self._clear_all_pending,
            color=COLORS["error"], width=80, height=28
        ).pack(side="right")

        self._pending_table = TreeviewFrame(
            frame,
            columns=("food", "source", "fields", "status"),
            headings=("Alimento", "Fonte", "Campos", "Status"),
            widths=[250, 80, 80, 100]
        )
        self._pending_table.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def load_unmatched_foods(self, processed_foods: list):
        """Carrega alimentos sem correspondencia."""
        self._all_foods = [p.platform_name for p in processed_foods
                          if p.status == "no_match"]
        self._unmatched = {p.platform_name: p for p in processed_foods
                          if p.status == "no_match"}
        self._filter_foods()

    def _filter_foods(self, event=None):
        """Filtra alimentos pela busca."""
        query = self._food_search.get().lower().strip()

        for btn in self._food_buttons:
            btn.destroy()
        self._food_buttons.clear()

        if query:
            foods = [f for f in self._all_foods if query in f.lower()][:50]
        else:
            foods = self._all_foods[:50]

        for food in foods:
            btn = ctk.CTkButton(
                self._food_buttons_frame, text=food[:60],
                anchor="w", height=26, corner_radius=4,
                fg_color="transparent", hover_color=COLORS["primary_light"],
                text_color=COLORS["text"], font=FONTS["small"],
                command=lambda f=food: self._on_food_select(f)
            )
            btn.pack(fill="x", pady=1)
            self._food_buttons.append(btn)

        if not self._all_foods:
            self._food_list_frame.pack_forget()
        else:
            self._food_list_frame.pack(fill="x", padx=24, pady=(0, 8))

    def _on_food_select(self, food_name: str):
        """Ao selecionar um alimento."""
        if not food_name:
            self._current_food = None
            self._source_label.configure(text="")
            return

        self._current_food = food_name
        self._food_search.delete(0, "end")
        self._food_search.insert(0, food_name)
        self._source_label.configure(text="Entrada Manual")
        self._load_existing_entry(food_name)

    def _load_existing_entry(self, food_name: str):
        """Carrega entrada existente do banco."""
        try:
            from config.settings import DATA_DIR
            from storage.db import Database

            db = Database(DATA_DIR / "nutri_auto.db")
            existing = db.get_manual_entry(food_name)
            if existing:
                for field_name, value in existing.items():
                    if field_name in self._entries:
                        self._entries[field_name].delete(0, "end")
                        self._entries[field_name].insert(0, str(value))
        except Exception:
            pass

    def _save_entry(self):
        """Salva entrada manual no banco."""
        if not self._current_food:
            messagebox.showwarning("Aviso", "Selecione um alimento!")
            return

        data = {}
        for field_name, entry in self._entries.items():
            val = entry.get().strip()
            if val:
                data[field_name] = val

        if not data:
            messagebox.showwarning("Aviso",
                                   "Preencha pelo menos um campo!")
            return

        try:
            from config.settings import DATA_DIR
            from storage.db import Database

            db = Database(DATA_DIR / "nutri_auto.db")
            db.save_manual_entry(self._current_food, data)

            self._status_label.configure(
                text=f"Salvo: {len(data)} campos"
            )
            self._update_pending_list()

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar: {e}")

    def _clear_fields(self):
        """Limpa todos os campos."""
        for entry in self._entries.values():
            entry.delete(0, "end")

    def _fill_on_site(self):
        """Preenche os dados no site da plataforma."""
        if not self._current_food:
            messagebox.showwarning("Aviso", "Selecione um alimento!")
            return

        data = {}
        for field_name, entry in self._entries.items():
            val = entry.get().strip()
            if val:
                data[field_name] = val

        if not data:
            messagebox.showwarning("Aviso",
                                   "Preencha pelo menos um campo!")
            return

        # Preencher em thread separada
        def _fill():
            try:
                self.after(0, lambda: self._status_label.configure(
                    text="Preenchendo no site..."
                ))

                if not self.app._connected:
                    self.app.orchestrator.start_browser(headless=True)
                    self.app._connected = True

                platform = self.app.orchestrator.platform
                if platform.open_edit_dialog(self._current_food):
                    platform.fill_nutritional_data(data)
                    platform.click_save()
                    platform._close_all_popups()
                    platform.clear_search()

                    self.after(0, lambda: self._status_label.configure(
                        text="Preenchido com sucesso!"
                    ))
                    self.after(0, lambda: self.app._log(
                        f"Manual: {self._current_food} preenchido ({len(data)} campos)"
                    ))
                else:
                    self.after(0, lambda: self._status_label.configure(
                        text="Erro ao abrir alimento no site"
                    ))

            except Exception as e:
                self.after(0, lambda: self._status_label.configure(
                    text=f"Erro: {e}"
                ))

        threading.Thread(target=_fill, daemon=True).start()

    def _update_pending_list(self):
        """Atualiza lista de entradas pendentes."""
        self._pending_table.clear()
        try:
            from config.settings import DATA_DIR
            from storage.db import Database

            db = Database(DATA_DIR / "nutri_auto.db")
            entries = db.get_all_manual_entries()

            for food_name, data in entries.items():
                self._pending_table.insert((
                    food_name[:40],
                    "Manual",
                    str(len(data)),
                    "Pronto"
                ))
        except Exception:
            pass

    def _clear_all_pending(self):
        """Limpa todas as entradas pendentes."""
        if messagebox.askyesno("Confirmar",
                               "Limpar todas as entradas manuais?"):
            try:
                from config.settings import DATA_DIR
                from storage.db import Database

                db = Database(DATA_DIR / "nutri_auto.db")
                db.clear_manual_entries()
                self._pending_table.clear()
                self._status_label.configure(text="Entradas limpas!")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro: {e}")

    def refresh_pending(self):
        """Atualiza lista de pendentes."""
        self._update_pending_list()

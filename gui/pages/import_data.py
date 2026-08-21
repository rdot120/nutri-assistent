"""
Pagina de importacao de dados.
Importa valores de planilhas (CSV) ou texto copiado.
"""
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog

from ..theme import COLORS, FONTS
from ..widgets import ActionButton, TreeviewFrame


FIELD_LABELS = {
    "valorEnergetico429": "Valor Energetico (kcal)",
    "carboidratos429": "Carboidratos (g)",
    "proteinas429": "Proteinas (g)",
    "gordurasTotais429": "Gorduras Totais (g)",
    "gordurasSaturadas429": "Gorduras Saturadas (g)",
    "gordurasTrans429": "Gorduras Trans (g)",
    "fibraAlimentar429": "Fibra Alimentar (g)",
    "sodio429": "Sodio (mg)",
    "acucaresTotais429": "Acucares Totais (g)",
    "colesterol": "Colesterol (mg)",
    "calcio": "Calcio (mg)",
    "ferro": "Ferro (mg)",
}


class ImportPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        self._imported_data = {}
        self._build_header()
        self._build_csv_import()
        self._build_paste_import()
        self._build_preview()
        self._build_actions()

    def _build_header(self):
        ctk.CTkLabel(self, text="Importacao de Dados",
            font=FONTS["title"], text_color=COLORS["text"], anchor="w"
        ).pack(fill="x", padx=24, pady=(18, 2))
        ctk.CTkLabel(self, text="Importe valores nutricionais de planilhas CSV ou texto copiado.",
            font=FONTS["body"], text_color=COLORS["text_soft"], anchor="w"
        ).pack(fill="x", padx=24)

    def _build_csv_import(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        panel.pack(fill="x", padx=24, pady=(12, 8))
        ctk.CTkLabel(panel, text="Importar CSV", font=FONTS["section"],
            text_color=COLORS["text"], anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))
        self._csv_path = ctk.CTkEntry(row, placeholder_text="Caminho do arquivo CSV...",
            font=FONTS["body"], width=400)
        self._csv_path.pack(side="left", padx=(0, 8))
        ActionButton(row, "Selecionar", command=self._select_csv,
            color=COLORS["primary_light"], text_color=COLORS["text"]).pack(side="left")
        ActionButton(row, "Importar", command=self._import_csv,
            color=COLORS["primary"]).pack(side="left", padx=(8, 0))

    def _build_paste_import(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        panel.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(panel, text="Colar Texto", font=FONTS["section"],
            text_color=COLORS["text"], anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkLabel(panel, text="Formato: 'Campo: valor' por linha",
            font=FONTS["small"], text_color=COLORS["text_soft"], anchor="w"
        ).pack(fill="x", padx=16)
        self._paste_text = ctk.CTkTextbox(panel, font=FONTS["log"], height=120,
            fg_color=COLORS["bg"], corner_radius=6)
        self._paste_text.pack(fill="x", padx=16, pady=(4, 8))
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row, text="Nome:", font=FONTS["body_bold"],
            text_color=COLORS["text"]).pack(side="left", padx=(0, 8))
        self._food_name_entry = ctk.CTkEntry(row, placeholder_text="Ex: Arroz Tipo 1",
            font=FONTS["body"], width=250)
        self._food_name_entry.pack(side="left", padx=(0, 8))
        ActionButton(row, "Importar Texto", command=self._import_paste,
            color=COLORS["primary"]).pack(side="left", padx=(8, 0))

    def _build_preview(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        panel.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        ctk.CTkLabel(panel, text="Preview dos Dados Importados", font=FONTS["section"],
            text_color=COLORS["text"], anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))
        self._preview_table = TreeviewFrame(panel, columns=("field", "value"),
            headings=("Campo", "Valor"), widths=[250, 150])
        self._preview_table.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(0, 12))
        ActionButton(frame, "Salvar como Entrada Manual", command=self._save_manual,
            color=COLORS["accent"]).pack(side="left")
        ActionButton(frame, "Preencher no Site", command=self._fill_on_site,
            color=COLORS["primary"]).pack(side="left", padx=(8, 0))
        ActionButton(frame, "Limpar", command=self._clear_all,
            color=COLORS["border"], text_color=COLORS["text"]).pack(side="right")
        self._status_label = ctk.CTkLabel(frame, text="", font=FONTS["small"],
            text_color=COLORS["text_soft"])
        self._status_label.pack(side="right", padx=(0, 12))

    def _select_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv"), ("Todos", "*.*")])
        if path:
            self._csv_path.delete(0, "end")
            self._csv_path.insert(0, path)

    def _import_csv(self):
        path = self._csv_path.get().strip()
        if not path:
            messagebox.showwarning("Aviso", "Selecione um arquivo!")
            return
        from nutrition.importer import SpreadsheetImporter
        importer = SpreadsheetImporter()
        result = importer.import_csv(path)
        if result.error_messages:
            self._status_label.configure(text=result.error_messages[0])
            return
        self._imported_data = result.fields
        self._update_preview()
        self._status_label.configure(text=f"Importado: {result.imported} campos")

    def _import_paste(self):
        text = self._paste_text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("Aviso", "Cole o texto primeiro!")
            return
        from nutrition.importer import SpreadsheetImporter
        importer = SpreadsheetImporter()
        food_name = self._food_name_entry.get().strip()
        result = importer.import_paste(text, food_name)
        if result.error_messages:
            self._status_label.configure(text=result.error_messages[0])
            return
        self._imported_data = result.fields
        if food_name:
            self._imported_data["_food_name"] = food_name
        self._update_preview()
        self._status_label.configure(text=f"Importado: {result.imported} campos")

    def _update_preview(self):
        self._preview_table.clear()
        for field, value in self._imported_data.items():
            if field.startswith("_"):
                continue
            label = FIELD_LABELS.get(field, field)
            self._preview_table.insert((label, str(value)))

    def _save_manual(self):
        if not self._imported_data:
            messagebox.showwarning("Aviso", "Importe dados primeiro!")
            return
        food_name = self._imported_data.get("_food_name") or self._food_name_entry.get().strip()
        if not food_name:
            messagebox.showwarning("Aviso", "Informe o nome do alimento!")
            return
        data = {k: v for k, v in self._imported_data.items() if not k.startswith("_")}
        try:
            from config.settings import DATA_DIR
            from storage.db import Database
            db = Database(DATA_DIR / "nutri_auto.db")
            db.save_manual_entry(food_name, data)
            self._status_label.configure(text=f"Salvo: {food_name}")
            self.app._pages["manual_entry"].refresh_pending()
            self.app._log(f"Manual: {food_name} importado ({len(data)} campos)")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao salvar: {e}")

    def _fill_on_site(self):
        if not self._imported_data:
            messagebox.showwarning("Aviso", "Importe dados primeiro!")
            return
        food_name = self._imported_data.get("_food_name") or self._food_name_entry.get().strip()
        if not food_name:
            messagebox.showwarning("Aviso", "Informe o nome do alimento!")
            return
        data = {k: v for k, v in self._imported_data.items() if not k.startswith("_")}
        def _fill():
            try:
                self.after(0, lambda: self._status_label.configure(text="Preenchendo..."))
                if not self.app._connected:
                    self.app.orchestrator.start_browser(headless=True)
                    self.app._connected = True
                platform = self.app.orchestrator.platform
                if platform.open_edit_dialog(food_name):
                    platform.fill_nutritional_data(data)
                    platform.click_save()
                    platform._close_all_popups()
                    platform.clear_search()
                    self.after(0, lambda: self._status_label.configure(text="Preenchido!"))
                    self.after(0, lambda: self.app._log(f"Import: {food_name} preenchido"))
                else:
                    self.after(0, lambda: self._status_label.configure(text="Erro ao abrir"))
            except Exception as e:
                self.after(0, lambda: self._status_label.configure(text=f"Erro: {e}"))
        threading.Thread(target=_fill, daemon=True).start()

    def _clear_all(self):
        self._imported_data = {}
        self._preview_table.clear()
        self._csv_path.delete(0, "end")
        self._paste_text.delete("1.0", "end")
        self._food_name_entry.delete(0, "end")
        self._status_label.configure(text="")

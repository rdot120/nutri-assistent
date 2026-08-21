"""
Pagina de deduplicacao de alimentos.
Detecta nomes parecidos e permite unificar.
"""
import threading
import customtkinter as ctk
from tkinter import messagebox

from ..theme import COLORS, FONTS
from ..widgets import ActionButton, TreeviewFrame, LogPanel


class DedupPage(ctk.CTkFrame):
    """Pagina de deduplicacao de alimentos."""

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        self._groups = []

        self._build_header()
        self._build_controls()
        self._build_groups_list()
        self._build_details()

    def _build_header(self):
        ctk.CTkLabel(
            self, text="Deduplicacao de Alimentos",
            font=FONTS["title"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            self, text="Detecte e unifique alimentos com nomes parecidos.",
            font=FONTS["body"], text_color=COLORS["text_soft"],
            anchor="w"
        ).pack(fill="x", padx=24)

    def _build_controls(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        frame.pack(fill="x", padx=24, pady=(12, 8))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            row, text="Threshold:", font=FONTS["body_bold"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        self._threshold_var = ctk.DoubleVar(value=80.0)
        self._threshold_slider = ctk.CTkSlider(
            row, from_=50, to=100, variable=self._threshold_var,
            number_of_steps=10, width=150
        )
        self._threshold_slider.pack(side="left", padx=(0, 8))

        self._threshold_label = ctk.CTkLabel(
            row, text="80%", font=FONTS["small"],
            text_color=COLORS["text"]
        )
        self._threshold_label.pack(side="left")

        ActionButton(
            row, "Buscar Duplicatas", command=self._scan,
            color=COLORS["primary"]
        ).pack(side="left", padx=(16, 0))

        self._status_label = ctk.CTkLabel(
            row, text="", font=FONTS["small"],
            text_color=COLORS["text_soft"]
        )
        self._status_label.pack(side="right")

    def _build_groups_list(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        self._table = TreeviewFrame(
            container,
            columns=("group_idx", "count", "similarity", "suggested_keep"),
            headings=("#", "Itens", "Similaridade", "Sugestao Manter"),
            widths=[40, 60, 100, 350]
        )
        self._table.pack(fill="both", expand=True)

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(4, 0))

        ActionButton(
            btn_frame, "Mesclar Selecionado", command=self._merge_selected,
            color=COLORS["accent"]
        ).pack(side="left")

        ActionButton(
            btn_frame, "Ignorar Selecionado", command=self._ignore_selected,
            color=COLORS["border"], text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

    def _build_details(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10, height=150)
        panel.pack(fill="x", padx=24, pady=(0, 12))
        panel.pack_propagate(False)

        ctk.CTkLabel(
            panel, text="Itens do Grupo",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        self._items_table = TreeviewFrame(
            panel,
            columns=("name", "source", "code"),
            headings=("Nome", "Fonte", "Codigo"),
            widths=[300, 100, 100]
        )
        self._items_table.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _scan(self):
        """Escaneia por duplicatas."""
        self._status_label.configure(text="Escaneando...")
        self._table.clear()
        self._groups = []

        def _scan_thread():
            try:
                from nutrition.dedup import Deduplicator
                from config.settings import DATA_DIR

                threshold = self._threshold_var.get()
                dedup = Deduplicator(similarity_threshold=threshold)

                platform_foods = []
                if hasattr(self.app, '_platform_foods'):
                    platform_foods = self.app._platform_foods or []

                groups = dedup.find_duplicates(platform_foods)
                self._groups = groups

                for i, group in enumerate(groups):
                    names = [item.name[:35] for item in group.items[:3]]
                    display = " | ".join(names)
                    if group.count > 3:
                        display += f" (+{group.count - 3})"

                    self.after(0, lambda idx=i, g=group, d=display:
                               self._table.insert((
                                   str(idx + 1),
                                   str(g.count),
                                   f"{g.similarity:.0f}%",
                                   g.suggested_keep[:50]
                               )))

                self.after(0, lambda: self._status_label.configure(
                    text=f"{len(groups)} grupos encontrados"
                ))

            except Exception as e:
                self.after(0, lambda: self._status_label.configure(
                    text=f"Erro: {e}"
                ))

        threading.Thread(target=_scan_thread, daemon=True).start()

    def _merge_selected(self):
        """Mescla itens selecionados."""
        selection = self._table._tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um grupo!")
            return

        item = selection[0]
        values = self._table._tree.item(item, "values")
        group_idx = int(values[0]) - 1

        if group_idx < 0 or group_idx >= len(self._groups):
            return

        group = self._groups[group_idx]
        keep = group.suggested_keep
        remove = group.suggested_remove

        msg = f"Manter: {keep}\nRemover: {', '.join(remove[:5])}"
        if messagebox.askyesno("Confirmar Mesclagem", msg):
            self._status_label.configure(text=f"Mesclando para '{keep}'...")
            self._table._tree.delete(item)
            self._status_label.configure(text="Mesclado!")

    def _ignore_selected(self):
        """Ignora grupo selecionado."""
        selection = self._table._tree.selection()
        if selection:
            self._table._tree.delete(selection[0])

"""
Pagina principal: tabela de alimentos, botoes de controle, log.
"""
import time
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ..theme import COLORS, FONTS
from ..widgets import (StatCard, ActionButton, LogPanel, SearchEntry,
                       FilterButton, TreeviewFrame, ProgressBar)


class DashboardPage(ctk.CTkFrame):
    """Painel de controle principal."""

    COLUMNS = ("index", "platform_name", "match_name", "match_source",
               "confidence", "status", "fields_count")
    HEADINGS = ("#", "Alimento da Plataforma", "Correspondencia",
                "Fonte", "Confianca", "Status", "Campos")
    WIDTHS = [40, 220, 220, 60, 70, 100, 60]

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app

        self._filter_var = tk.StringVar(value="all")
        self._all_rows = []

        self._build_header()
        self._build_stats()
        self._build_progress()
        self._build_actions()
        self._build_filters()
        self._build_table()
        self._build_log()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            header, text="Painel de Controle",
            font=FONTS["title"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        self._status_label = ctk.CTkLabel(
            header, text="Desconectado",
            font=FONTS["small"], text_color=COLORS["text_soft"],
            anchor="e"
        )
        self._status_label.pack(side="right")

        self._sources_label = ctk.CTkLabel(
            header, text="",
            font=FONTS["small"], text_color=COLORS["text_soft"],
            anchor="e"
        )
        self._sources_label.pack(side="right", padx=(0, 16))

    def _build_stats(self):
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=24, pady=(12, 4))
        for i in range(4):
            cards.grid_columnconfigure(i, weight=1, uniform="cards")

        self.card_total = StatCard(cards, "Total", "0", COLORS["primary"])
        self.card_total.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.card_matched = StatCard(cards, "Com Match", "0", COLORS["success_dark"])
        self.card_matched.grid(row=0, column=1, sticky="ew", padx=4)

        self.card_filled = StatCard(cards, "Preenchidos", "0", COLORS["accent"])
        self.card_filled.grid(row=0, column=2, sticky="ew", padx=4)

        self.card_saved = StatCard(cards, "Salvos", "0",
                                   COLORS["primary_light"])
        self.card_saved.grid(row=0, column=3, sticky="ew", padx=(8, 0))

    def _build_progress(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(8, 4))

        self._progress_label = ctk.CTkLabel(
            frame, text="Progresso",
            font=FONTS["small_bold"], text_color=COLORS["text"],
            anchor="w"
        )
        self._progress_label.pack(side="left")

        self.progress = ProgressBar(frame)
        self.progress.pack(side="left", fill="x", expand=True, padx=(12, 0))

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(8, 4))

        self.btn_connect = ActionButton(
            frame, "Conectar", command=self._on_connect,
            color=COLORS["primary"]
        )
        self.btn_connect.pack(side="left", padx=(0, 8))

        self.btn_load = ActionButton(
            frame, "Carregar Dados", command=self._on_load,
            color=COLORS["primary"]
        )
        self.btn_load.pack(side="left", padx=(0, 8))

        self.btn_start = ActionButton(
            frame, "Iniciar", command=self._on_start,
            color=COLORS["primary"]
        )
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_stop = ActionButton(
            frame, "Parar", command=self._on_stop,
            color=COLORS["error"]
        )
        self.btn_stop.pack(side="left", padx=(0, 8))

        self.btn_undo = ActionButton(
            frame, "Desfazer", command=self._on_undo,
            color=COLORS["accent_light"], text_color=COLORS["text"]
        )
        self.btn_undo.pack(side="left", padx=(0, 8))

        self.btn_settings = ActionButton(
            frame, "Configuracoes", command=self._on_settings,
            color=COLORS["accent_light"], text_color=COLORS["text"]
        )
        self.btn_settings.pack(side="right")

        self.btn_check_updates = ActionButton(
            frame, "Verificar Atualizacoes", command=self._on_check_updates,
            color=COLORS["primary_light"], text_color=COLORS["text"]
        )
        self.btn_check_updates.pack(side="right", padx=(0, 8))

    def _build_filters(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(8, 4))

        self._search = SearchEntry(
            frame, placeholder="Buscar alimento...",
            command=self._on_search
        )
        self._search.pack(side="right", padx=(12, 0), ipady=2)

        for text, value, label_text in [
            ("Todos", "all", "Filtros:"),
            ("Com Match", "matched", "Com Match"),
            ("Sem Match", "no_match", "Sem Match"),
            ("Revisar", "review", "Revisar"),
            ("Preenchidos", "filled", "Preenchidos"),
            ("Conferidos", "reviewed", "Conferidos"),
            ("Ignorados", "skipped", "Ignorados"),
            ("Removidos", "removed", "Removidos"),
        ]:
            if text == "Todos":
                ctk.CTkLabel(
                    frame, text=label_text,
                    font=FONTS["small_bold"], text_color=COLORS["text"]
                ).pack(side="left")
            FilterButton(
                frame, text=text, variable=self._filter_var,
                value=value, command=self._apply_filter
            ).pack(side="left", padx=(8 if text != "Todos" else 4, 0))

    def _build_table(self):
        self.table = TreeviewFrame(
            self, columns=self.COLUMNS, headings=self.HEADINGS,
            widths=self.WIDTHS
        )
        self.table.pack(fill="both", expand=True, padx=24, pady=(4, 8))

    def _build_log(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkLabel(
            frame, text="Log de Operacoes",
            font=FONTS["small_bold"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        ActionButton(
            frame, "Limpar", command=lambda: self.log.clear(),
            color=COLORS["border"], text_color=COLORS["text"],
            width=60, height=28
        ).pack(side="right")

        self.log = LogPanel(frame, height=120)
        self.log.pack(fill="x", pady=(4, 0))

    # === Acoes dos botoes ===

    def _on_connect(self):
        """Conecta na plataforma."""
        self.app.connect_platform()

    def _on_load(self):
        """Carrega dados da plataforma e TBCA/USDA."""
        self.app.load_data()

    def _on_start(self):
        """Inicia o pipeline de preenchimento."""
        self.app.start_pipeline()

    def _on_stop(self):
        """Para o pipeline."""
        self.app.stop_pipeline()

    def _on_undo(self):
        """Desfaz ultima operacao."""
        self.app.undo_last()

    def _on_settings(self):
        """Abre configuracoes."""
        self.app.show_settings()

    def _on_check_updates(self):
        """Verifica atualizacoes nas fontes."""
        self.app.check_updates_now()

    def _on_search(self, query: str):
        """Busca na tabela."""
        self._apply_filter(query=query)

    def _apply_filter(self, query: str = ""):
        """Aplica filtro selecionado."""
        filter_val = self._filter_var.get()
        self.table.clear()

        if not query:
            query = self._search.get_text().strip().lower()

        for row in self._all_rows:
            status = row[5] if len(row) > 5 else ""
            name = row[1] if len(row) > 1 else ""

            show = True
            if filter_val == "matched":
                show = status == "Com Match"
            elif filter_val == "no_match":
                show = status == "Sem Match"
            elif filter_val == "review":
                show = status == "Revisar"
            elif filter_val == "filled":
                show = status == "Preenchido"
            elif filter_val == "reviewed":
                show = status == "Conferido"
            elif filter_val == "skipped":
                show = status == "Ignorado"
            elif filter_val == "removed":
                show = status == "Removido"

            if show and query:
                show = query in name.lower()

            if show:
                self.table.insert(row)

    # === Metodos publicos para atualizar a UI ===

    def update_status(self, connected: bool, text: str = ""):
        """Atualiza status de conexao."""
        if connected:
            self._status_label.configure(
                text=text or "Conectado",
                text_color=COLORS["success_dark"]
            )
        else:
            self._status_label.configure(
                text=text or "Desconectado",
                text_color=COLORS["text_soft"]
            )

    def update_sources(self, tbca: int = 0, usda: int = 0, ia: int = 0):
        """Atualiza contadores de fontes de correspondencia."""
        parts = []
        if tbca > 0:
            parts.append(f"TBCA: {tbca}")
        if usda > 0:
            parts.append(f"USDA: {usda}")
        if ia > 0:
            parts.append(f"IA: {ia}")
        self._sources_label.configure(text=" | ".join(parts) if parts else "")

    def update_stats(self, total: int, matched: int,
                     filled: int, saved: int):
        """Atualiza cards de estatistica."""
        self.card_total.set_value(str(total))
        self.card_matched.set_value(str(matched))
        self.card_filled.set_value(str(filled))
        self.card_saved.set_value(str(saved))

    def update_progress(self, current: int, total: int):
        """Atualiza barra de progresso."""
        self.progress.update_progress(current, total)

    def add_food_row(self, index: int, platform_name: str,
                     match_name: str = "", source: str = "",
                     confidence: float = 0, status: str = "Pendente",
                     fields_count: int = 0) -> str:
        """Adiciona alimento na tabela. Retorna item_id."""
        conf_str = f"{confidence:.0f}%" if confidence > 0 else "-"
        row = (
            str(index), platform_name, match_name, source,
            conf_str, status, str(fields_count) if fields_count > 0 else "-"
        )
        self._all_rows.append(row)
        return self.table.insert(row)

    def update_food_status(self, item_id: str, status: str,
                           match_name: str = None, source: str = None,
                           confidence: float = None, fields_count: int = None):
        """Atualiza status de um alimento na tabela."""
        current = list(self.table._tree.item(item_id, "values"))
        if match_name is not None:
            current[2] = match_name
        if source is not None:
            current[3] = source
        if confidence is not None:
            current[4] = f"{confidence:.0f}%" if confidence > 0 else "-"
        current[5] = status
        if fields_count is not None:
            current[6] = str(fields_count) if fields_count > 0 else "-"
        self.table.update_item(item_id, tuple(current))

    def log_message(self, message: str):
        """Adiciona mensagem ao log."""
        timestamp = time.strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {message}")

    def clear_table(self):
        """Limpa a tabela."""
        self._all_rows.clear()
        self.table.clear()

    def clear_log(self):
        """Limpa o log."""
        self.log.clear()

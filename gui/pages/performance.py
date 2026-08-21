"""
Pagina de performance e metricas.
Mostra historico de sessoes, estatisticas e permite exportar relatorios.
"""
import time
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog

from ..theme import COLORS, FONTS
from ..widgets import StatCard, ActionButton, TreeviewFrame, LogPanel


class PerformancePage(ctk.CTkFrame):
    """Pagina de performance e metricas."""

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        self._build_header()
        self._build_global_stats()
        self._build_sessions_table()
        self._build_details_panel()
        self._build_actions()

    def _build_header(self):
        ctk.CTkLabel(
            self, text="Performance e Metricas",
            font=FONTS["title"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            self, text="Acompanhe o desempenho das operacoes de preenchimento.",
            font=FONTS["body"], text_color=COLORS["text_soft"],
            anchor="w"
        ).pack(fill="x", padx=24)

    def _build_global_stats(self):
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=24, pady=(12, 4))
        for i in range(5):
            cards.grid_columnconfigure(i, weight=1, uniform="cards")

        self.card_sessions = StatCard(cards, "Sessoes", "0", COLORS["primary"])
        self.card_sessions.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.card_processed = StatCard(cards, "Processados", "0", COLORS["accent"])
        self.card_processed.grid(row=0, column=1, sticky="ew", padx=3)

        self.card_success = StatCard(cards, "Taxa Sucesso", "0%", COLORS["success_dark"])
        self.card_success.grid(row=0, column=2, sticky="ew", padx=3)

        self.card_avg_time = StatCard(cards, "Tempo/Item", "0s", COLORS["primary_light"])
        self.card_avg_time.grid(row=0, column=3, sticky="ew", padx=3)

        self.card_errors = StatCard(cards, "Erros", "0", COLORS["error"])
        self.card_errors.grid(row=0, column=4, sticky="ew", padx=(6, 0))

    def _build_sessions_table(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        frame.pack(fill="both", expand=True, padx=24, pady=(8, 8))

        ctk.CTkLabel(
            frame, text="Historico de Sessoes",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        self._table = TreeviewFrame(
            frame,
            columns=("session_id", "date", "total", "saved", "errors", "duration"),
            headings=("ID", "Data", "Total", "Salvos", "Erros", "Duracao"),
            widths=[80, 150, 70, 70, 70, 100]
        )
        self._table.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_details_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10, height=180)
        panel.pack(fill="x", padx=24, pady=(0, 8))
        panel.pack_propagate(False)

        ctk.CTkLabel(
            panel, text="Detalhes da Sessao",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        self._details_log = LogPanel(panel, height=100)
        self._details_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(0, 12))

        ActionButton(
            frame, "Atualizar", command=self._refresh,
            color=COLORS["primary"]
        ).pack(side="left")

        ActionButton(
            frame, "Exportar Sessao (CSV)", command=self._export_session,
            color=COLORS["primary_light"], text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

        ActionButton(
            frame, "Exportar Tudo (CSV)", command=self._export_all,
            color=COLORS["primary_light"], text_color=COLORS["text"]
        ).pack(side="left", padx=(8, 0))

        self._status_label = ctk.CTkLabel(
            frame, text="", font=FONTS["small"],
            text_color=COLORS["text_soft"]
        )
        self._status_label.pack(side="right")

    def _refresh(self):
        """Atualiza dados."""
        try:
            from storage.performance import PerformanceTracker
            from config.settings import DATA_DIR

            tracker = PerformanceTracker(DATA_DIR / "nutri_auto.db")
            stats = tracker.get_global_stats()

            self.card_sessions.set_value(str(stats["total_sessions"]))
            self.card_processed.set_value(str(stats["total_foods_processed"]))
            self.card_errors.set_value(str(stats["total_errors"]))

            total = stats["total_foods_processed"]
            saved = stats["total_saved"]
            if total > 0:
                rate = (saved / total) * 100
                self.card_success.set_value(f"{rate:.0f}%")
            else:
                self.card_success.set_value("-")

            avg_time = stats["avg_time_per_item"]
            if avg_time > 0:
                self.card_avg_time.set_value(f"{avg_time:.1f}s")
            else:
                self.card_avg_time.set_value("-")

            sessions = tracker.get_sessions()
            self._table.clear()
            for s in sessions[:30]:
                date_str = time.strftime(
                    "%d/%m/%Y %H:%M",
                    time.localtime(s.get("started_at", 0))
                )
                duration = s.get("total_duration", 0)
                dur_str = f"{duration:.0f}s" if duration else "-"
                self._table.insert((
                    s.get("session_id", "")[:8],
                    date_str,
                    str(s.get("total_foods", 0)),
                    str(s.get("saved", 0)),
                    str(s.get("errors", 0)),
                    dur_str,
                ))

            self._status_label.configure(text="Atualizado!")

        except Exception as e:
            self._status_label.configure(text=f"Erro: {e}")

    def _export_session(self):
        """Exporta sessao selecionada."""
        selection = self._table._tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione uma sessao!")
            return

        item = selection[0]
        values = self._table._tree.item(item, "values")
        session_id = values[0]

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Exportar Sessao"
        )
        if path:
            from storage.performance import PerformanceTracker
            from config.settings import DATA_DIR

            tracker = PerformanceTracker(DATA_DIR / "nutri_auto.db")
            if tracker.export_session_csv(session_id, Path(path)):
                messagebox.showinfo("Sucesso", f"Exportado para {path}")
            else:
                messagebox.showerror("Erro", "Falha ao exportar")

    def _export_all(self):
        """Exporta todas as sessoes."""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Exportar Todas as Sessoes"
        )
        if path:
            from storage.performance import PerformanceTracker
            from config.settings import DATA_DIR

            tracker = PerformanceTracker(DATA_DIR / "nutri_auto.db")
            if tracker.export_global_csv(Path(path)):
                messagebox.showinfo("Sucesso", f"Exportado para {path}")
            else:
                messagebox.showerror("Erro", "Falha ao exportar")

    def refresh(self):
        """Atualiza dados (chamado externamente)."""
        self._refresh()

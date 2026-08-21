"""
Pagina de historico de operacoes.
"""
import time
import csv
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from ..theme import COLORS, FONTS
from ..widgets import ActionButton, TreeviewFrame


class LogsPage(ctk.CTkFrame):
    """Pagina de historico de operacoes."""

    COLUMNS = ("id", "datetime", "food", "operation", "status", "details")
    HEADINGS = ("#", "Data/Hora", "Alimento", "Operacao", "Status", "Detalhes")
    WIDTHS = [40, 140, 200, 100, 80, 300]

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app

        self._build_header()
        self._build_actions()
        self._build_table()

    def _build_header(self):
        ctk.CTkLabel(
            self, text="Historico de Operacoes",
            font=FONTS["title"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            self, text="Todas as operacoes realizadas pelo sistema.",
            font=FONTS["body"], text_color=COLORS["text_soft"],
            anchor="w"
        ).pack(fill="x", padx=24)

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(12, 4))

        ActionButton(
            frame, "Atualizar", command=self.refresh,
            color=COLORS["primary"]
        ).pack(side="left", padx=(0, 8))

        ActionButton(
            frame, "Exportar CSV", command=self._export_csv,
            color=COLORS["accent_light"], text_color=COLORS["text"]
        ).pack(side="left")

        self._count_label = ctk.CTkLabel(
            frame, text="0 operacoes",
            font=FONTS["small"], text_color=COLORS["text_soft"]
        )
        self._count_label.pack(side="right")

    def _build_table(self):
        self.table = TreeviewFrame(
            self, columns=self.COLUMNS, headings=self.HEADINGS,
            widths=self.WIDTHS
        )
        self.table.pack(fill="both", expand=True, padx=24, pady=(4, 12))

    def refresh(self):
        """Recarrega historico do banco."""
        self.table.clear()
        try:
            db = self.app.db
            ops = db.get_operation_history(limit=200)
            for op in ops:
                dt = time.strftime(
                    "%d/%m/%Y %H:%M",
                    time.localtime(op.get("created_at", 0))
                )
                self.table.insert((
                    str(op.get("id", "")),
                    dt,
                    op.get("food_name", ""),
                    op.get("operation", ""),
                    op.get("status", ""),
                    op.get("details", "")[:100] if op.get("details") else "",
                ))
            self._count_label.configure(text=f"{len(ops)} operacoes")
        except Exception as e:
            self._count_label.configure(text=f"Erro: {e}")

    def _export_csv(self):
        """Exporta historico para CSV."""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            initialfile="historico_operacoes.csv"
        )
        if not path:
            return

        try:
            db = self.app.db
            ops = db.get_operation_history(limit=10000)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Data/Hora", "Alimento",
                                 "Operacao", "Status", "Detalhes"])
                for op in ops:
                    dt = time.strftime(
                        "%d/%m/%Y %H:%M",
                        time.localtime(op.get("created_at", 0))
                    )
                    writer.writerow([
                        op.get("id", ""),
                        dt,
                        op.get("food_name", ""),
                        op.get("operation", ""),
                        op.get("status", ""),
                        op.get("details", ""),
                    ])
            self._count_label.configure(
                text=f"Exportado: {Path(path).name}"
            )
        except Exception as e:
            self._count_label.configure(text=f"Erro ao exportar: {e}")

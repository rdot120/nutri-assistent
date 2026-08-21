"""
Pagina do assistente interativo.
Permite revisao campo-a-campo antes de preencher.
"""
import threading
import customtkinter as ctk
from tkinter import messagebox

from ..theme import COLORS, FONTS
from ..widgets import ActionButton, LogPanel


# Labels dos campos
FIELD_LABELS = {
    "valorEnergetico429": "Valor Energetico (kcal)",
    "carboidratos429": "Carboidratos (g)",
    "acucaresTotais429": "Acucares Totais (g)",
    "acucaresAdicionados": "Acucares Adicionados (g)",
    "proteinas429": "Proteinas (g)",
    "gordurasTotais429": "Gorduras Totais (g)",
    "gordurasSaturadas429": "Gorduras Saturadas (g)",
    "gordurasTrans429": "Gorduras Trans (g)",
    "fibraAlimentar429": "Fibra Alimentar (g)",
    "sodio429": "Sodio (mg)",
    "colesterol": "Colesterol (mg)",
    "calcio": "Calcio (mg)",
    "ferro": "Ferro (mg)",
}


class AssistantPage(ctk.CTkFrame):
    """Pagina do assistente interativo."""

    def __init__(self, master, app):
        super().__init__(master, corner_radius=0, fg_color="transparent")
        self.app = app
        self._assistant = None
        self._build_header()
        self._build_controls()
        self._build_food_panel()
        self._build_fields_panel()
        self._build_actions()
        self._build_summary()

    def _build_header(self):
        ctk.CTkLabel(
            self, text="Assistente Interativo",
            font=FONTS["title"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=24, pady=(18, 2))

        ctk.CTkLabel(
            self, text="Revise campo-a-campo antes de preencher na plataforma.",
            font=FONTS["body"], text_color=COLORS["text_soft"],
            anchor="w"
        ).pack(fill="x", padx=24)

    def _build_controls(self):
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        frame.pack(fill="x", padx=24, pady=(12, 8))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        self.btn_start = ActionButton(
            row, "Iniciar Revisao", command=self._start_review,
            color=COLORS["primary"]
        )
        self.btn_start.pack(side="left")

        self.btn_auto = ActionButton(
            row, "Auto-Aprovar (Conf>=90%)", command=self._auto_approve,
            color=COLORS["primary_light"], text_color=COLORS["text"]
        )
        self.btn_auto.pack(side="left", padx=(8, 0))

        self.btn_apply = ActionButton(
            row, "Aplicar Aprovados", command=self._apply_approved,
            color=COLORS["accent"]
        )
        self.btn_apply.pack(side="right")

    def _build_food_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10, height=120)
        panel.pack(fill="x", padx=24, pady=(0, 8))
        panel.pack_propagate(False)

        ctk.CTkLabel(
            panel, text="Alimento Atual",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        info_row = ctk.CTkFrame(panel, fg_color="transparent")
        info_row.pack(fill="x", padx=16)

        ctk.CTkLabel(
            info_row, text="Nome:", font=FONTS["body_bold"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        self._food_name = ctk.CTkLabel(
            info_row, text="-", font=FONTS["body"],
            text_color=COLORS["text"]
        )
        self._food_name.pack(side="left", padx=(0, 24))

        ctk.CTkLabel(
            info_row, text="Match:", font=FONTS["body_bold"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        self._match_name = ctk.CTkLabel(
            info_row, text="-", font=FONTS["body"],
            text_color=COLORS["text"]
        )
        self._match_name.pack(side="left", padx=(0, 24))

        ctk.CTkLabel(
            info_row, text="Confianca:", font=FONTS["body_bold"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(0, 8))

        self._confidence = ctk.CTkLabel(
            info_row, text="-", font=FONTS["body"],
            text_color=COLORS["text"]
        )
        self._confidence.pack(side="left")

    def _build_fields_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        panel.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        ctk.CTkLabel(
            panel, text="Campos Nutricionais",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        self._fields_frame = ctk.CTkScrollableFrame(
            panel, fg_color="transparent"
        )
        self._fields_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._field_widgets = []

    def _build_actions(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=(0, 8))

        self.btn_prev = ActionButton(
            frame, "Anterior", command=self._prev_food,
            color=COLORS["border"], text_color=COLORS["text"]
        )
        self.btn_prev.pack(side="left")

        self.btn_approve = ActionButton(
            frame, "Aprovar Tudo", command=self._approve_all,
            color=COLORS["success_dark"]
        )
        self.btn_approve.pack(side="left", padx=(8, 0))

        self.btn_reject = ActionButton(
            frame, "Rejeitar", command=self._reject_all,
            color=COLORS["error"]
        )
        self.btn_reject.pack(side="left", padx=(8, 0))

        self.btn_next = ActionButton(
            frame, "Proximo", command=self._next_food,
            color=COLORS["primary"]
        )
        self.btn_next.pack(side="left", padx=(8, 0))

    def _build_summary(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10, height=100)
        panel.pack(fill="x", padx=24, pady=(0, 12))
        panel.pack_propagate(False)

        ctk.CTkLabel(
            panel, text="Resumo da Revisao",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(8, 4))

        self._summary_label = ctk.CTkLabel(
            panel, text="Nenhuma revisao em andamento",
            font=FONTS["body"], text_color=COLORS["text_soft"],
            anchor="w"
        )
        self._summary_label.pack(fill="x", padx=16)

    def _start_review(self):
        """Inicia revisao."""
        if not hasattr(self.app, '_processed') or not self.app._processed:
            messagebox.showwarning("Aviso", "Carregue os dados primeiro!")
            return

        from automation.interactive import InteractiveAssistant
        from automation.orchestrator import Orchestrator

        self._assistant = InteractiveAssistant(self.app.orchestrator)
        self._assistant.prepare_reviews(self.app._processed)
        self._show_current()

    def _show_current(self):
        """Mostra alimento atual."""
        if not self._assistant:
            return

        review = self._assistant.get_current_review()
        if not review:
            messagebox.showinfo("Fim", "Revisao concluida!")
            return

        pf = review.processed
        self._food_name.configure(text=pf.platform_name[:50])
        if pf.match:
            self._match_name.configure(text=pf.match.tbca_name[:40])
            self._confidence.configure(text=f"{pf.match.confidence:.0f}%")

        # Limpar campos anteriores
        for widget in self._field_widgets:
            widget.destroy()
        self._field_widgets = []

        # Criar campos
        for i, field in enumerate(review.fields):
            row = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            var = ctk.BooleanVar(value=field.approved)
            cb = ctk.CTkCheckBox(
                row, text="", variable=var,
                fg_color=COLORS["primary"],
                command=lambda idx=i, v=var: self._toggle_field(idx, v)
            )
            cb.pack(side="left", padx=(0, 8))

            label = FIELD_LABELS.get(field.field_name, field.field_name)
            ctk.CTkLabel(
                row, text=f"{label}:", font=FONTS["small"],
                text_color=COLORS["text"], width=160, anchor="w"
            ).pack(side="left")

            ctk.CTkLabel(
                row, text="->", font=FONTS["small"],
                text_color=COLORS["text_soft"]
            ).pack(side="left", padx=(8, 8))

            entry = ctk.CTkEntry(
                row, font=FONTS["small"], width=100,
                corner_radius=4
            )
            entry.insert(0, field.new_value)
            entry.pack(side="left")
            entry.bind("<FocusOut>", lambda e, idx=i, ent=entry:
                       self._edit_field(idx, ent.get()))

            self._field_widgets.append(row)

        summary = self._assistant.get_summary()
        self._summary_label.configure(
            text=f"Total: {summary['total']} | "
                 f"Aprovados: {summary['approved']} | "
                 f"Pendentes: {summary['pending']}"
        )

    def _toggle_field(self, idx, var):
        """Toggle aprovacao de campo."""
        if var.get():
            self._assistant.approve_field(idx)
        else:
            self._assistant.reject_field(idx)

    def _edit_field(self, idx, value):
        """Edita valor de campo."""
        self._assistant.edit_field(idx, value)

    def _approve_all(self):
        """Aprova todos os campos."""
        if self._assistant:
            self._assistant.approve_current()
            self._show_current()

    def _reject_all(self):
        """Rejeita todos."""
        if self._assistant:
            self._assistant.reject_current()
            self._show_current()

    def _next_food(self):
        """Proximo alimento."""
        if self._assistant:
            self._assistant.skip_current()
            self._show_current()

    def _prev_food(self):
        """Alimento anterior."""
        if self._assistant:
            self._assistant.go_back()
            self._show_current()

    def _auto_approve(self):
        """Aprova automaticamente alta confianca."""
        if self._assistant:
            self._assistant.auto_approve_high_confidence(90.0)
            self._show_current()

    def _apply_approved(self):
        """Aplica aprovacoes na plataforma."""
        if not self._assistant:
            return

        actions = self._assistant.apply_approved()
        if not actions:
            messagebox.showinfo("Info", "Nenhuma acao aprovada!")
            return

        if messagebox.askyesno(
            "Confirmar",
            f"Aplicar {len(actions)} alimentos aprovados no site?"
        ):
            self.app._log(f"Aplicando {len(actions)} aprovados...")
            self.app.start_pipeline_from_approved(actions)

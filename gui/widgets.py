"""
Widgets reutilizaveis para a interface GUI.
"""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from .theme import COLORS, FONTS


class StatCard(ctk.CTkFrame):
    """Card de estatistica com titulo, valor e cor de destaque."""

    def __init__(self, master, title: str, value: str = "0",
                 color: str = COLORS["primary"], **kwargs):
        super().__init__(master, fg_color=COLORS["card_bg"],
                         corner_radius=10, **kwargs)

        self.grid_columnconfigure(0, weight=1)

        self._color_bar = ctk.CTkFrame(
            self, height=4, fg_color=color, corner_radius=2
        )
        self._color_bar.grid(row=0, column=0, sticky="ew", padx=12,
                             pady=(12, 0))

        self._title = ctk.CTkLabel(
            self, text=title, font=FONTS["small"],
            text_color=COLORS["text_soft"], anchor="w"
        )
        self._title.grid(row=1, column=0, sticky="w", padx=12, pady=(8, 0))

        self._value = ctk.CTkLabel(
            self, text=value, font=FONTS["card_value"],
            text_color=COLORS["text"], anchor="w"
        )
        self._value.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))

    def set_value(self, value: str):
        self._value.configure(text=value)

    def set_color(self, color: str):
        self._color_bar.configure(fg_color=color)


class ActionButton(ctk.CTkButton):
    """Botao de acao padronizado."""

    def __init__(self, master, text: str, command=None,
                 color: str = COLORS["primary"],
                 text_color: str = "#FFFFFF",
                 hover_color: str = None, **kwargs):
        if hover_color is None:
            hover_color = COLORS["sidebar_hover"]
        defaults = {
            "corner_radius": 8,
            "height": 36,
            "font": FONTS["body_bold"],
        }
        defaults.update(kwargs)
        super().__init__(
            master, text=text, command=command,
            fg_color=color, text_color=text_color,
            hover_color=hover_color,
            **defaults
        )


class LogPanel(ctk.CTkFrame):
    """Painel de log scrollavel com texto monoespacado."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["card_bg"],
                         corner_radius=10, **kwargs)

        self._text = ctk.CTkTextbox(
            self, font=FONTS["log"],
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            corner_radius=6,
            state="disabled",
            wrap="word",
        )
        self._text.pack(fill="both", expand=True, padx=8, pady=8)

    def append(self, message: str, tag: str = "info"):
        """Adiciona mensagem ao log."""
        self._text.configure(state="normal")
        self._text.insert("end", message + "\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        """Limpa o log."""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


class SearchEntry(ctk.CTkEntry):
    """Campo de busca com placeholder."""

    def __init__(self, master, placeholder: str = "Buscar...",
                 command=None, **kwargs):
        super().__init__(
            master, placeholder_text=placeholder,
            corner_radius=8, height=36,
            font=FONTS["body"],
            border_color=COLORS["border"],
            **kwargs
        )
        self._command = command
        self.bind("<Return>", lambda e: self._do_search())

    def _do_search(self):
        if self._command:
            self._command(self.get())

    def get_text(self):
        return self.get()


class FilterButton(ctk.CTkRadioButton):
    """Botao de filtro estilo radio button."""

    def __init__(self, master, text: str, command=None,
                 variable=None, value="", **kwargs):
        super().__init__(
            master, text=text, command=command,
            variable=variable, value=value,
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_light"],
            text_color=COLORS["text"],
            font=FONTS["small"],
            **kwargs
        )


class TreeviewFrame(ctk.CTkFrame):
    """Frame contendo um Treeview estilizado com scrollbars."""

    def __init__(self, master, columns: list, headings: list,
                 widths: list = None, **kwargs):
        super().__init__(master, fg_color=COLORS["card_bg"],
                         corner_radius=10, **kwargs)

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Nutri.Treeview",
                        background=COLORS["row_even"],
                        foreground=COLORS["text"],
                        rowheight=32,
                        fieldbackground=COLORS["row_even"],
                        font=FONTS["body"])
        style.configure("Nutri.Treeview.Heading",
                        background=COLORS["primary"],
                        foreground="#FFFFFF",
                        font=FONTS["body_bold"],
                        relief="flat")
        style.map("Nutri.Treeview",
                  background=[("selected", COLORS["row_selected"])],
                  foreground=[("selected", COLORS["text"])])
        style.configure("Nutri.Treeview", borderwidth=0)
        style.map("Nutri.Treeview",
                  borderwidth=[("selected", 0)])

        self._tree = ttk.Treeview(
            self, columns=columns, show="headings",
            selectmode="extended", style="Nutri.Treeview"
        )

        if widths is None:
            widths = [100] * len(columns)

        for col, heading, width in zip(columns, headings, widths):
            self._tree.heading(col, text=heading, anchor="w")
            self._tree.column(col, width=width, minwidth=50, anchor="w")

        vsb = ttk.Scrollbar(self, orient="vertical",
                            command=self._tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal",
                            command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set,
                             xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vsb.grid(row=0, column=1, sticky="ns", pady=8, padx=(0, 8))
        hsb.grid(row=1, column=0, sticky="ew", padx=(8, 0), pady=(0, 8))

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Alternar cores das linhas
        self._tree.tag_configure("odd", background=COLORS["row_odd"])
        self._tree.tag_configure("even", background=COLORS["row_even"])

    def insert(self, values: tuple, tags: tuple = ()) -> str:
        """Insere item na tabela."""
        count = len(self._tree.get_children())
        if not tags:
            tags = ("even" if count % 2 == 0 else "odd",)
        return self._tree.insert("", "end", values=values, tags=tags)

    def clear(self):
        """Limpa todos os itens."""
        for item in self._tree.get_children():
            self._tree.delete(item)

    def get_selected(self) -> list:
        """Retorna itens selecionados."""
        return self._tree.selection()

    def update_item(self, item_id: str, values: tuple):
        """Atualiza valores de um item."""
        self._tree.item(item_id, values=values)

    def get_all_items(self) -> list:
        """Retorna todos os itens da tabela."""
        items = []
        for item_id in self._tree.get_children():
            items.append({
                "id": item_id,
                "values": self._tree.item(item_id, "values"),
            })
        return items


class ProgressBar(ctk.CTkFrame):
    """Barra de progresso customizada."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._label = ctk.CTkLabel(
            self, text="0 / 0", font=FONTS["small"],
            text_color=COLORS["text_soft"]
        )
        self._label.pack(side="right", padx=(8, 0))

        self._bar = ctk.CTkProgressBar(
            self, height=8, corner_radius=4,
            progress_color=COLORS["primary"],
            fg_color=COLORS["border"]
        )
        self._bar.pack(side="left", fill="x", expand=True)
        self._bar.set(0)

    def update_progress(self, current: int, total: int):
        """Atualiza progresso."""
        if total > 0:
            self._bar.set(current / total)
        else:
            self._bar.set(0)
        self._label.configure(text=f"{current} / {total}")

    def reset(self):
        """Reseta a barra."""
        self._bar.set(0)
        self._label.configure(text="0 / 0")

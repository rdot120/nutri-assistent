"""
Tema, cores e fontes da interface GUI.
Palette: tons terrosos e naturais para app de nutricao.
"""
import customtkinter as ctk

COLORS = {
    "bg": "#FFFFFF",
    "sidebar": "#767c57",
    "sidebar_hover": "#8a9068",
    "primary": "#767c57",
    "primary_light": "#bfc891",
    "accent": "#9c6148",
    "accent_light": "#caa586",
    "text": "#2D2D2D",
    "text_soft": "#6B6B6B",
    "text_light": "#9A9A9A",
    "success": "#bfc891",
    "success_dark": "#767c57",
    "warning": "#caa586",
    "error": "#9c6148",
    "border": "#E5E5E5",
    "card_bg": "#F8F8F8",
    "row_even": "#FFFFFF",
    "row_odd": "#F5F5F0",
    "row_selected": "#E8EDD8",
}

FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "title_light": ("Segoe UI", 20),
    "section": ("Segoe UI", 15, "bold"),
    "body": ("Segoe UI", 13),
    "body_bold": ("Segoe UI", 13, "bold"),
    "small": ("Segoe UI", 11),
    "small_bold": ("Segoe UI", 11, "bold"),
    "card_value": ("Segoe UI", 26, "bold"),
    "sidebar_title": ("Segoe UI", 17, "bold"),
    "sidebar_item": ("Segoe UI", 13),
    "log": ("Consolas", 11),
}


def configure_theme():
    """Configura tema do CustomTkinter."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

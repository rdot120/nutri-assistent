"""
Janela principal do aplicativo de automacao nutricional.
Coordena GUI, threading e orchestrator.
"""
import sys
import time
import uuid
import queue
import logging
import threading
import customtkinter as ctk
from pathlib import Path

# Adicionar diretorio pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _resource_path(relative: str) -> Path:
    """Resolve caminho de recurso para dev e PyInstaller."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent.parent / relative

from config.settings import Settings, DATA_DIR
from storage.db import Database
from storage.session import SessionManager
from automation.orchestrator import Orchestrator, ProcessedFood
from nutrition.updater import UpdateChecker
from storage.performance import PerformanceTracker, SessionMetrics, ItemMetrics

from .theme import COLORS, FONTS, configure_theme
from .pages.dashboard import DashboardPage
from .pages.settings import SettingsPage
from .pages.logs import LogsPage
from .pages.search import SearchPage
from .pages.manual_entry import ManualEntryPage
from .pages.performance import PerformancePage
from .pages.dedup import DedupPage
from .pages.assistant import AssistantPage
from .pages.import_data import ImportPage

logger = logging.getLogger(__name__)

APP_VERSION = "1.2"


class App(ctk.CTk):
    """Janela principal: sidebar de navegacao + paginas."""

    NAV_ITEMS = [
        ("Dashboard", "dashboard"),
        ("Pesquisa", "search"),
        ("Importar", "import_data"),
        ("Preenchimento Manual", "manual_entry"),
        ("Assistente", "assistant"),
        ("Deduplicacao", "dedup"),
        ("Performance", "performance"),
        ("Configuracoes", "settings"),
        ("Historico", "logs"),
    ]

    def __init__(self):
        super().__init__()
        configure_theme()

        self.title(f"Nutri Assistent v{APP_VERSION} - Tecnosoft Balancas")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_icon()

        # Configuracoes e banco
        self.settings = Settings.load()
        self.settings.load_env()
        self.db = Database(DATA_DIR / "nutri_auto.db")
        self.session_mgr = SessionManager(DATA_DIR)

        # Orchestrator
        self.orchestrator = Orchestrator(self.settings)

        # Estado
        self._session_id = str(uuid.uuid4())[:8]
        self._connected = False
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()

        # Worker thread dedicado para operacoes Playwright
        self._browser_queue = queue.Queue()
        self._browser_thread = None

        # Verificador de atualizacoes
        self._updater = UpdateChecker(
            self.settings, callback=self._on_update_event
        )
        self._update_results = {"tbca": None, "usda": None}

        # Referencias as paginas
        self._pages = {}
        self._current_page = None

        self._configure_layout()
        self._build_sidebar()
        self._build_pages()
        self.show_page("dashboard")

        self._load_saved_session()

        # Iniciar verificacao periodica se habilitada
        if self.settings.automation.auto_check_updates:
            self.after(2000, self._start_updater)

    def _configure_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

    def _set_icon(self):
        """Define icone da janela."""
        icon_path = _resource_path("extra/icon.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0,
            fg_color=COLORS["sidebar"]
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        # Titulo
        ctk.CTkLabel(
            sidebar, text="Nutri\nAssistent",
            font=FONTS["sidebar_title"],
            text_color="#FFFFFF",
            justify="left", anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 2))

        ctk.CTkLabel(
            sidebar, text="Tecnosoft Balancas",
            font=FONTS["small"], text_color="#D4DBC4",
            anchor="w", wraplength=180, justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))

        # Scroll frame para navegacao
        nav_scroll = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent",
            scrollbar_button_color=COLORS["sidebar_hover"],
            scrollbar_button_hover_color="#6a7048",
        )
        nav_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=0)
        sidebar.grid_rowconfigure(2, weight=1)

        # Botoes de navegacao
        self._nav_buttons = {}
        for index, (label, key) in enumerate(self.NAV_ITEMS):
            button = ctk.CTkButton(
                nav_scroll, text=label, corner_radius=8, height=34,
                fg_color="transparent", text_color="#FFFFFF",
                hover_color=COLORS["sidebar_hover"],
                anchor="w", font=FONTS["sidebar_item"],
                command=lambda k=key: self.show_page(k),
            )
            button.pack(fill="x", padx=4, pady=1)
            self._nav_buttons[key] = button

        # Status na sidebar
        self._sidebar_status = ctk.CTkLabel(
            sidebar, text=f"v{APP_VERSION}",
            font=FONTS["small"], text_color="#9AA888",
            anchor="w"
        )
        self._sidebar_status.grid(row=20, column=0, sticky="ew",
                                  padx=18, pady=(0, 8))

        # Logo no canto inferior
        logo_path = _resource_path("extra/logo.png")
        if logo_path.exists():
            try:
                from PIL import Image as PILImage
                logo_pil = PILImage.open(str(logo_path))
                w, h = logo_pil.size
                max_w, max_h = 160, 100
                scale = min(max_w / w, max_h / h)
                logo_w, logo_h = int(w * scale), int(h * scale)

                logo_frame = ctk.CTkFrame(
                    sidebar, fg_color="white", corner_radius=10
                )
                logo_frame.grid(row=21, column=0, sticky="s",
                                padx=18, pady=(4, 14))
                logo_img = ctk.CTkImage(
                    light_image=logo_pil,
                    dark_image=logo_pil,
                    size=(logo_w, logo_h),
                )
                ctk.CTkLabel(
                    logo_frame, image=logo_img, text="",
                    fg_color="white", corner_radius=10,
                ).pack(padx=8, pady=8)
            except Exception:
                pass

    def _build_pages(self):
        container = ctk.CTkFrame(self, fg_color=COLORS["bg"],
                                 corner_radius=0)
        container.grid(row=0, column=1, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self._pages["dashboard"] = DashboardPage(container, self)
        self._pages["search"] = SearchPage(container, self)
        self._pages["import_data"] = ImportPage(container, self)
        self._pages["manual_entry"] = ManualEntryPage(container, self)
        self._pages["assistant"] = AssistantPage(container, self)
        self._pages["dedup"] = DedupPage(container, self)
        self._pages["performance"] = PerformancePage(container, self)
        self._pages["settings"] = SettingsPage(container, self)
        self._pages["logs"] = LogsPage(container, self)

        # Carregar configuracoes na pagina de settings
        self._pages["settings"].load_from_settings(self.settings)

    def show_page(self, key: str):
        """Mostra uma pagina."""
        if self._current_page:
            self._pages[self._current_page].grid_forget()

        # Atualizar botoes da sidebar
        for nav_key, btn in self._nav_buttons.items():
            if nav_key == key:
                btn.configure(fg_color=COLORS["sidebar_hover"])
            else:
                btn.configure(fg_color="transparent")

        self._pages[key].grid(row=0, column=0, sticky="nsew",
                              padx=0, pady=0)
        self._current_page = key

    # === Acoes da GUI ===

    def _start_browser_worker(self):
        """Inicia worker thread dedicado para operacoes Playwright."""
        if self._browser_thread and self._browser_thread.is_alive():
            return
        self._browser_thread = threading.Thread(
            target=self._browser_worker_loop, daemon=True
        )
        self._browser_thread.start()

    def _browser_worker_loop(self):
        """Loop do worker: processa tarefas da fila na mesma thread."""
        while True:
            try:
                task = self._browser_queue.get(timeout=1)
                if task is None:
                    break
                func, args, kwargs, result_event, result_box = task
                try:
                    result_box["value"] = func(*args, **kwargs)
                except Exception as e:
                    result_box["error"] = e
                finally:
                    result_event.set()
            except queue.Empty:
                continue

    def _run_on_browser_thread(self, func, *args, **kwargs):
        """Executa funcao na thread do browser e retorna resultado."""
        if threading.current_thread() is self._browser_thread:
            return func(*args, **kwargs)
        result_event = threading.Event()
        result_box = {"value": None, "error": None}
        self._browser_queue.put((func, args, kwargs, result_event, result_box))
        result_event.wait(timeout=120)
        if result_box["error"]:
            raise result_box["error"]
        return result_box["value"]

    def connect_platform(self):
        """Conecta na plataforma."""
        if self._connected or getattr(self, "_connecting", False):
            return

        self._connecting = True
        self._log("Conectando na plataforma...")
        self._set_status("Conectando...")

        def _connect():
            try:
                self._start_browser_worker()
                self._run_on_browser_thread(
                    self.orchestrator.start_browser, headless=True
                )
                self._connected = True
                self.after(0, lambda: self._on_connected())
            except Exception as e:
                self._connected = False
                self.after(0, lambda: self._on_error(f"Erro ao conectar: {e}"))
            finally:
                self._connecting = False

        threading.Thread(target=_connect, daemon=True).start()

    def _on_connected(self):
        """Callback apos conexao."""
        self._log("Conectado com sucesso!")
        self._set_status("Conectado")
        dashboard = self._pages["dashboard"]
        dashboard.update_status(True, "Conectado")

    def load_data(self):
        """Carrega dados da plataforma e busca correspondencias."""
        if not self._connected:
            self._log("Erro: conecte-se primeiro!")
            return
        if self._running:
            return

        self._log("Carregando dados...")
        self._set_status("Carregando...")

        def _load():
            try:
                # Fase 1: Coletar alimentos da plataforma
                self.after(0, lambda: self._log("Fase 1: Coletando alimentos da plataforma..."))
                platform_foods = self._run_on_browser_thread(
                    self.orchestrator.step1_collect_platform_foods
                )
                self.after(0, lambda: self._log(
                    f"Coletados {len(platform_foods)} alimentos"
                ))

                # Fase 1b: filtros da barra lateral (verde/azul ja concluidos)
                self.after(0, lambda: self._log(
                    "Fase 1b: Lendo filtros da barra lateral..."
                ))
                info = self._run_on_browser_thread(
                    self.orchestrator.step1b_mark_prefilled, platform_foods
                )
                c = info["counts"]
                self.after(0, lambda: self._log(
                    f"Pendentes: {info['pendentes']} = {c.get('total', 0)} - "
                    f"({c.get('associados', 0)} salvos + "
                    f"{c.get('checados', 0)} conferidos); "
                    f"{info['marked']} marcados como preenchidos"
                ))

                # Preparar exibicao em tempo real
                self._live_platform_foods = platform_foods
                self._live_manual_entries = self.db.get_all_manual_entries()
                self._live_rows = []
                self._live_total = len(platform_foods)
                self.after(0, self._start_live_stream)

                # Sincronizar com sessao anterior
                saved = self.session_mgr.load()
                if saved and saved.get("processed_raw"):
                    self.after(0, lambda: self._log("Sincronizando com sessao anterior..."))
                    processed, removed_count, new_count = self._sync_with_saved(
                        platform_foods, saved
                    )
                    self.after(0, lambda: self._log(
                        f"Sincronizado: {new_count} novos, "
                        f"{removed_count} removidos, "
                        f"{len(processed) - new_count - removed_count} mantidos"
                    ))
                else:
                    # Fase 2: Indice TBCA (sem Playwright, pode rodar aqui)
                    self.after(0, lambda: self._log("Fase 2: Carregando indice TBCA..."))
                    search_terms = list(set(
                        f["name"].split(",")[0].strip()
                        for f in platform_foods if len(f["name"]) > 3
                    ))
                    tbca_foods = self.orchestrator.step2_build_tbca_index(search_terms)
                    self.after(0, lambda: self._log(
                        f"Indice TBCA: {len(tbca_foods)} alimentos"
                    ))

                    # Fase 3: Matching (sem Playwright, pode rodar aqui)
                    self.after(0, lambda: self._log("Fase 3: Buscando correspondencias..."))
                    processed = self.orchestrator.step3_match_foods(
                        platform_foods,
                        gui_callback=lambda msg: self.after(0, lambda m=msg: self._log(m)),
                        on_item=self._live_on_item,
                    )

                    matched = sum(1 for p in processed if p.status == "matched")
                    self.after(0, lambda: self._log(
                        f"Matches: {matched}/{len(processed)}"
                    ))

                # Fase 3b: Verificar status dos cards (Playwright)
                self.after(0, lambda: self._log("Fase 3b: Verificando cards na plataforma..."))
                processed = self._run_on_browser_thread(
                    self.orchestrator.step3b_check_card_status, processed
                )

                processed = self.orchestrator.apply_prefilled_to_processed(processed)

                skipped = sum(1 for p in processed if p.status == "skipped")
                if skipped > 0:
                    self.after(0, lambda: self._log(
                        f"Cards ignorados: {skipped} (ja preenchidos/conferidos)"
                    ))

                # Salvar sessao
                self.session_mgr.save(platform_foods, processed)

                # Atualizar GUI
                self.after(0, lambda: self._update_dashboard_data(
                    platform_foods, processed
                ))

            except Exception as e:
                self.after(0, lambda: self._on_error(f"Erro ao carregar: {e}"))

        threading.Thread(target=_load, daemon=True).start()

    def _compute_row_fields(self, pf, manual_entries):
        """Calcula os campos de exibicao de um item para a tabela."""
        match_name = ""
        source = ""
        confidence = 0
        status = "Pendente"
        fields_count = 0

        if pf.status == "removed":
            match_name = pf.suggestion[:35] if pf.suggestion else ""
            source = "Removido"
            status = "Removido"
        elif pf.status == "review_needed":
            match_name = pf.match.tbca_name[:35] if pf.match else ""
            source = "Revisar"
            status = "Revisar"
            confidence = pf.match.confidence if pf.match else 0
        elif pf.status == "skipped":
            if pf.skip_reason == "already_filled":
                match_name = pf.suggestion[:35] if pf.suggestion else ""
                source = "Plataforma"
                status = "Preenchido"
            elif pf.skip_reason == "reviewed":
                match_name = pf.suggestion[:35] if pf.suggestion else ""
                source = "Plataforma"
                status = "Conferido"
            elif pf.skip_reason == "prefilled_salvo":
                match_name = "(salvo na plataforma)"
                source = "Plataforma"
                status = "Salvo"
            elif pf.skip_reason == "prefilled_conferido":
                match_name = "(conferido na plataforma)"
                source = "Plataforma"
                status = "Conferido"
            else:
                match_name = pf.suggestion[:35] if pf.suggestion else ""
                source = "Ignorado"
                status = "Ignorado"
        elif pf.match:
            match_name = pf.match.tbca_name[:35]
            confidence = pf.match.confidence
            method = pf.match.match_method or ""
            if method.startswith("ai_"):
                source = f"IA ({method.replace('ai_', '')})"
            elif method == "usda":
                source = "USDA"
            else:
                source = "TBCA"
            status = "Com Match"
            fields_count = len(pf.fields_to_fill) if pf.fields_to_fill else 0
        elif pf.platform_name in manual_entries:
            match_name = "Manual"
            source = "Manual"
            status = "Entrada Manual"
            fields_count = len(manual_entries[pf.platform_name])
        else:
            status = "Sem Match"

        return (match_name, source, confidence, status, fields_count)

    def _count_matched(self, processed):
        """Com Match: correspondencias de qualquer fonte (TBCA, USDA, IA)."""
        return sum(1 for p in processed if p.match)

    # Motivos de skip que indicam alimento ja pronto na plataforma
    _DONE_SKIP_REASONS = (
        "already_filled", "reviewed", "prefilled_salvo", "prefilled_conferido",
    )

    def _count_filled(self, processed):
        """Preenchidos: todo alimento que ja esta pronto na plataforma
        (preenchido, conferido ou salvo) + os preenchidos nesta sessao."""
        return sum(
            1 for p in processed
            if p.status in ("filled", "saved")
            or (p.status == "skipped"
                and p.skip_reason in self._DONE_SKIP_REASONS)
        )

    def _count_saved(self, processed):
        """Salvos: equivalente ao botao verde (Associados) do site."""
        return sum(
            1 for p in processed
            if p.status == "saved"
            or (p.status == "skipped" and p.skip_reason == "prefilled_salvo")
        )

    def _start_live_stream(self):
        """Prepara a tabela para receber itens em tempo real."""
        dashboard = self._pages["dashboard"]

        def reset():
            dashboard.clear_table()
            self._live_rows = []
            self._live_total = len(self._live_platform_foods)
            dashboard.update_progress(0, max(1, self._live_total))

        self.after(0, reset)

    def _live_on_item(self, pf):
        """Callback do orquestrador: adiciona item na tabela em tempo real."""

        def apply():
            if not hasattr(self, "_live_rows"):
                return
            dashboard = self._pages["dashboard"]
            self._live_rows.append(pf)
            idx = len(self._live_rows)
            fields = self._compute_row_fields(pf, self._live_manual_entries)
            dashboard.add_food_row(
                idx, pf.platform_name[:30], *fields
            )
            matched = self._count_matched(self._live_rows)
            skipped = sum(1 for p in self._live_rows
                          if p.status == "skipped")
            dashboard.update_stats(
                self._live_total or len(self._live_rows),
                matched,
                self._count_filled(self._live_rows),
                self._count_saved(self._live_rows),
            )
            dashboard.update_progress(idx, max(1, self._live_total))
            if skipped:
                self._set_status(
                    f"Carregando... {idx}/{self._live_total} "
                    f"({matched} com match, {skipped} pre-preenchidos)"
                )
            else:
                self._set_status(
                    f"Carregando... {idx}/{self._live_total} "
                    f"({matched} com match)"
                )

        self.after(0, apply)

    def _update_dashboard_data(self, platform_foods, processed):
        """Atualiza dashboard com dados carregados."""
        dashboard = self._pages["dashboard"]
        dashboard.clear_table()

        self._processed = processed
        self._platform_foods = platform_foods

        # Estatisticas
        total = len(processed)
        matched = self._count_matched(processed)
        skipped = sum(1 for p in processed if p.status == "skipped")
        removed = sum(1 for p in processed if p.status == "removed")
        dashboard.update_stats(total, matched,
                               self._count_filled(processed),
                               self._count_saved(processed))
        dashboard.update_progress(0, matched)

        tbca_matches = sum(
            1 for p in processed if p.match
            and (p.match.match_method or "") not in ("usda", "")
            and not (p.match.match_method or "").startswith("ai_")
        )
        usda_matches = sum(1 for p in processed
                           if p.match
                           and p.match.match_method == "usda")
        ia_matches = sum(1 for p in processed
                         if p.match and (p.match.match_method or "")
                         .startswith("ai_"))
        dashboard.update_sources(tbca=tbca_matches, usda=usda_matches,
                                 ia=ia_matches)

        manual_entries = self.db.get_all_manual_entries()

        # Preencher tabela
        for i, pf in enumerate(processed):
            match_name, source, confidence, status, fields_count = (
                self._compute_row_fields(pf, manual_entries)
            )

            dashboard.add_food_row(
                i + 1, pf.platform_name[:30], match_name,
                source, confidence, status, fields_count
            )

        status_parts = [f"Carregado: {matched}/{total} matches"]
        if skipped > 0:
            status_parts.append(f"{skipped} ignorados")
        if removed > 0:
            status_parts.append(f"{removed} removidos")
        self._set_status(", ".join(status_parts))
        self._log("Dados carregados!")

        manual_page = self._pages["manual_entry"]
        manual_page.load_unmatched_foods(processed)
        manual_page.refresh_pending()

    def start_pipeline(self):
        """Inicia o pipeline de preenchimento."""
        if not self._connected:
            self._log("Erro: conecte-se primeiro!")
            return
        if self._running:
            return
        if not hasattr(self, '_processed') or not self._processed:
            self._log("Erro: carregue os dados primeiro!")
            return

        processed = [p for p in self._processed
                     if p.status == "matched"
                     and p.skip_reason not in ("already_filled", "reviewed", "removed_from_platform")]
        manual_entries = self.db.get_all_manual_entries()
        manual_count = sum(1 for p in self._processed
                           if p.status == "no_match"
                           and p.platform_name in manual_entries)
        total = len(processed) + manual_count
        mode = self.settings.automation.mode
        mode_label = {"LIVE": "REAL (vai salvar na plataforma)",
                      "TEST": "TESTE (simulacao)",
                      "DRY_RUN": "DRY RUN (sem salvar)"}.get(mode, mode)

        if total == 0:
            self._log("Nenhum alimento para preencher!")
            return

        self._show_confirm_dialog(total, mode, mode_label)

    def _show_confirm_dialog(self, total, mode, mode_label):
        """Mostra popup de confirmacao antes de iniciar pipeline."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirmar")
        dialog.geometry("460x380")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_set()

        # Centralizar
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 460) // 2
        y = self.winfo_y() + (self.winfo_height() - 380) // 2
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            dialog, text="Confirmar Preenchimento",
            font=FONTS["title"], text_color=COLORS["text"]
        ).pack(pady=(20, 8))

        ctk.CTkLabel(
            dialog, text=f"Modo atual: {mode_label}",
            font=FONTS["body"], text_color=COLORS["text"]
        ).pack(pady=(0, 12))

        # Lista de alimentos
        processed = [p for p in self._processed
                     if p.status == "matched"
                     and p.skip_reason not in ("already_filled", "reviewed", "removed_from_platform")]
        manual_entries = self.db.get_all_manual_entries()
        manual_count = sum(1 for p in self._processed
                           if p.status == "no_match"
                           and p.platform_name in manual_entries)

        foods_frame = ctk.CTkFrame(dialog, fg_color=COLORS["card_bg"],
                                   corner_radius=8)
        foods_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        ctk.CTkLabel(
            foods_frame,
            text=f"{len(processed)} com match + {manual_count} manual = "
                 f"{total} alimentos",
            font=FONTS["small_bold"], text_color=COLORS["text"]
        ).pack(pady=(8, 4))

        list_frame = ctk.CTkScrollableFrame(
            foods_frame, fg_color="transparent", height=140
        )
        list_frame.pack(fill="both", expand=True, padx=8)

        for pf in processed[:30]:
            source = "TBCA" if "tbca" in (pf.match.match_method or "") else "IA"
            ctk.CTkLabel(
                list_frame,
                text=f"  {pf.platform_name[:35]}  ({source} {pf.match.confidence:.0f}%)",
                font=FONTS["small"], text_color=COLORS["text_soft"],
                anchor="w"
            ).pack(fill="x", pady=1)

        if len(processed) > 30:
            ctk.CTkLabel(
                list_frame,
                text=f"  ... e mais {len(processed) - 30}",
                font=FONTS["small"], text_color=COLORS["text_soft"]
            ).pack(pady=1)

        # Botoes
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 16))

        def _cancel():
            dialog.destroy()

        def _confirm():
            dialog.destroy()
            self._run_pipeline()

        ctk.CTkButton(
            btn_frame, text="Cancelar", width=120, height=36,
            fg_color=COLORS["card_bg"], text_color=COLORS["text"],
            hover_color=COLORS["primary_light"],
            corner_radius=8, command=_cancel
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text=f"Iniciar ({total})" if mode == "LIVE"
                 else f"Iniciar ({mode})",
            width=180, height=36,
            fg_color=COLORS["error"] if mode == "LIVE" else COLORS["primary"],
            text_color="white",
            hover_color=COLORS["error"],
            corner_radius=8, command=_confirm
        ).pack(side="right")

    def _run_pipeline(self):
        """Executa o pipeline apos confirmacao."""
        self._running = True
        self._stop_event.clear()
        self._log("Iniciando preenchimento...")
        self._set_status("Preenchendo...")

        perf_tracker = PerformanceTracker(DATA_DIR / "nutri_auto.db")
        perf_metrics = perf_tracker.start_session(self._session_id)

        def _run():
            try:
                mode = self.settings.automation.mode
                dry_run = mode in ("DRY_RUN", "TEST")
                processed = [p for p in self._processed
                             if p.status == "matched"
                             and p.skip_reason not in ("already_filled", "reviewed", "removed_from_platform", "match_suspeito")]

                manual_entries = self.db.get_all_manual_entries()
                manual_foods = []
                for p in self._processed:
                    if p.status == "no_match" and p.platform_name in manual_entries:
                        p.fields_to_fill = manual_entries[p.platform_name]
                        p.status = "matched"
                        manual_foods.append(p)

                processed = processed + manual_foods
                perf_metrics.total_foods = len(processed)
                perf_metrics.matched = len(processed)

                dashboard = self._pages["dashboard"]
                filled = 0
                saved = 0
                errors = 0

                for i, pf in enumerate(processed):
                    if self._stop_event.is_set():
                        self.after(0, lambda: self._log("Parado pelo usuario!"))
                        break

                    item_start = time.time()

                    self.after(0, lambda ii=i, n=pf.platform_name:
                               self._log(f"[{ii+1}/{len(processed)}] {n} -> "
                                         f"{pf.match.tbca_name[:30]}"))

                    try:
                        # Abrir dialog (Playwright)
                        def _open_dialog():
                            return self.orchestrator.platform.open_edit_dialog(
                                pf.platform_name
                            )
                        if not self._run_on_browser_thread(_open_dialog):
                            errors += 1
                            self.after(0, lambda ii=i: self._update_progress(
                                ii + 1, len(processed), filled, errors
                            ))
                            continue

                        # Ler dados atuais (Playwright)
                        current = self._run_on_browser_thread(
                            self.orchestrator.platform.get_nutritional_data
                        )

                        if not dry_run:
                            # Salvar backup
                            for field_name, new_val in pf.fields_to_fill.items():
                                old_val = current.get(field_name, "")
                                self.db.save_backup(
                                    self._session_id, pf.platform_name,
                                    i, field_name, str(old_val), str(new_val)
                                )

                            # Preencher (Playwright)
                            def _fill():
                                return self.orchestrator.platform.fill_nutritional_data(
                                    pf.fields_to_fill
                                )
                            filled_fields = self._run_on_browser_thread(_fill)
                            pf.fields_to_fill = filled_fields
                            pf.status = "filled"

                            # Salvar (Playwright)
                            if self._run_on_browser_thread(
                                self.orchestrator.platform.click_save
                            ):
                                pf.status = "saved"
                                saved += 1
                                self.db.log_operation(
                                    food_name=pf.platform_name,
                                    food_code=pf.match.tbca_code,
                                    operation="fill_save",
                                    status="success",
                                    details=f'{{"fields": {len(filled_fields)}}}'
                                )
                            else:
                                pf.status = "error"
                                pf.error = "Falha ao salvar"
                                errors += 1
                        else:
                            filled += 1
                            pf.status = "filled"

                        # Fechar popups (Playwright)
                        self._run_on_browser_thread(
                            self.orchestrator.platform._close_all_popups
                        )
                        self._run_on_browser_thread(
                            self.orchestrator.platform.clear_search
                        )
                        time.sleep(self.settings.automation.operation_interval)

                        # Verificar navegacao (Playwright)
                        if not dry_run and pf.status == "saved":
                            def _check_nav():
                                try:
                                    url = self.orchestrator.platform.page.url
                                    if "nutri" not in url:
                                        self.orchestrator.platform.navigate_to_nutri(
                                            self.settings.platform.nutri_url
                                        )
                                except Exception:
                                    self.orchestrator.platform.navigate_to_nutri(
                                        self.settings.platform.nutri_url
                                    )
                            self._run_on_browser_thread(_check_nav)

                        self.after(0, lambda ii=i, f=filled, e=errors:
                                   self._update_progress(
                                       ii + 1, len(processed), f, e
                                   ))

                    except Exception as e:
                        errors += 1
                        self.after(0, lambda err=str(e):
                                   self._log(f"Erro: {err}"))
                        try:
                            self._run_on_browser_thread(
                                self.orchestrator.platform._close_all_popups
                            )
                            self._run_on_browser_thread(
                                self.orchestrator.platform.clear_search
                            )
                        except Exception:
                            try:
                                self._run_on_browser_thread(
                                    self.orchestrator.platform.navigate_to_nutri,
                                    self.settings.platform.nutri_url
                                )
                            except Exception:
                                pass

                    item_duration = int((time.time() - item_start) * 1000)
                    perf_tracker.log_item(ItemMetrics(
                        session_id=self._session_id,
                        food_name=pf.platform_name,
                        food_code=pf.match.tbca_code if pf.match else "",
                        match_source="TBCA" if pf.match and "tbca" in pf.match.match_method else "Manual",
                        confidence=pf.match.confidence if pf.match else 0,
                        status=pf.status,
                        fields_filled=len(pf.fields_to_fill) if pf.fields_to_fill else 0,
                        duration_ms=item_duration,
                        error_message=pf.error if hasattr(pf, 'error') else "",
                        timestamp=time.time(),
                    ))
                    if pf.status == "saved":
                        perf_metrics.saved += 1
                    elif pf.status == "error":
                        perf_metrics.errors += 1

                self._running = False
                mode_str = "DRY RUN" if dry_run else "LIVE"
                self.after(0, lambda: self._log(
                    f"Concluido ({mode_str}): {saved} salvos, "
                    f"{filled} preenchidos, {errors} erros"
                ))
                self.after(0, lambda: self._set_status(
                    f"Concluido: {saved} salvos"
                ))

                perf_tracker.finish_session(perf_metrics)
                self._save_session()

            except Exception as e:
                self._running = False
                self.after(0, lambda: self._on_error(f"Erro no pipeline: {e}"))

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop_pipeline(self):
        """Para o pipeline."""
        if self._running:
            self._stop_event.set()
            self._log("Parando pipeline...")
            self._set_status("Parando...")

    def undo_last(self):
        """Desfaz o ultimo preenchimento."""
        if self._running:
            self._log("Erro: pare o pipeline primeiro!")
            return

        backups = self.db.get_backups(self._session_id)
        if not backups:
            self._log("Nada para desfazer!")
            return

        # Pegar alimentos distintos com backup
        foods = self.db.get_distinct_foods_backed_up(self._session_id)
        if not foods:
            self._log("Nada para desfazer!")
            return

        # Perguntar qual alimento desfazer
        food = foods[-1]  # Ultimo alimento
        food_backups = self.db.get_backups_by_food(self._session_id, food)

        self._log(f"Desfazendo: {food}...")

        def _undo():
            try:
                if not self._connected:
                    self._start_browser_worker()
                    self._run_on_browser_thread(
                        self.orchestrator.start_browser, headless=True
                    )
                    self._connected = True

                def _do_undo():
                    if self.orchestrator.platform.open_edit_dialog(food):
                        for backup in food_backups:
                            field = backup["field_name"]
                            old_val = backup["old_value"]
                            if old_val:
                                self.orchestrator.platform.set_field_value(
                                    field, old_val
                                )
                        self.orchestrator.platform.click_save()
                        self.orchestrator.platform._close_all_popups()
                        self.orchestrator.platform.clear_search()
                        return True
                    return False

                if self._run_on_browser_thread(_do_undo):
                    self.after(0, lambda: self._log(
                        f"Desfeito: {food} ({len(food_backups)} campos)"
                    ))
                else:
                    self.after(0, lambda: self._log(
                        f"Erro: nao foi possivel abrir {food}"
                    ))
            except Exception as e:
                self.after(0, lambda: self._on_error(
                    f"Erro ao desfazer: {e}"
                ))

        threading.Thread(target=_undo, daemon=True).start()

    def show_settings(self):
        """Mostra pagina de configuracoes."""
        self.show_page("settings")

    def show_manual_entry(self, food_name: str, source: str, data: dict):
        """Mostra pagina de preenchimento manual com dados pre-preenchidos."""
        self.show_page("manual_entry")
        page = self._pages["manual_entry"]
        page._food_var.set(food_name)
        page._current_food = food_name
        page._source_label.configure(text=source)
        for field_name, value in data.items():
            if field_name in page._entries:
                page._entries[field_name].delete(0, "end")
                page._entries[field_name].insert(0, str(value))

    def start_pipeline_from_approved(self, approved_actions: list):
        """Inicia pipeline a partir de acoes aprovadas no assistente."""
        if not self._connected:
            self._log("Erro: conecte-se primeiro!")
            return
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        def _run():
            try:
                saved = 0
                errors = 0
                total = len(approved_actions)

                for i, action in enumerate(approved_actions):
                    if self._stop_event.is_set():
                        break

                    food_name = action["food_name"]
                    fields = action["fields"]

                    self.after(0, lambda ii=i, n=food_name:
                               self._log(f"[{ii+1}/{total}] {n}"))

                    try:
                        def _do_fill():
                            if self.orchestrator.platform.open_edit_dialog(food_name):
                                self.orchestrator.platform.fill_nutritional_data(fields)
                                result = self.orchestrator.platform.click_save()
                                self.orchestrator.platform._close_all_popups()
                                self.orchestrator.platform.clear_search()
                                return result
                            return False

                        if self._run_on_browser_thread(_do_fill):
                            saved += 1
                            self.db.log_operation(
                                food_name=food_name,
                                operation="assistant_fill",
                                status="success",
                            )
                        else:
                            errors += 1
                        time.sleep(self.settings.automation.operation_interval)
                    except Exception as e:
                        errors += 1
                        self.after(0, lambda err=str(e): self._log(f"Erro: {err}"))

                self._running = False
                self.after(0, lambda: self._log(
                    f"Assistente concluido: {saved} salvos, {errors} erros"
                ))
            except Exception as e:
                self._running = False
                self.after(0, lambda: self._on_error(f"Erro: {e}"))

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    # === Verificador de atualizacoes ===

    def _start_updater(self):
        """Inicia o verificador periodico de atualizacoes."""
        self._updater.start()
        self._log("Verificador de atualizacoes ativo")

    def _on_update_event(self, event: str, data):
        """Callback de eventos do verificador."""
        self.after(0, lambda: self._handle_update_event(event, data))

    def _handle_update_event(self, event: str, data):
        """Trata eventos do verificador na thread da GUI."""
        if event == "checking":
            self._set_status(f"Verificando {data}...")
        elif event == "result":
            self._update_results[data.source] = data
            if data.new_items > 0 or data.updated_items > 0:
                self._log(
                    f"Atualizacao {data.source.upper()}: "
                    f"{data.new_items} novos, {data.updated_items} alterados"
                )
            else:
                self._log(f"{data.source.upper()}: {data.message}")
            self._update_sidebar_status()
        elif event == "error":
            self._log(f"Erro na verificacao: {data}")

    def _update_sidebar_status(self):
        """Atualiza status de atualizacoes na sidebar."""
        parts = []
        for source in ["tbca", "usda"]:
            result = self._update_results.get(source)
            if result:
                last = time.strftime(
                    "%H:%M",
                    time.localtime(result.checked_at)
                )
                parts.append(f"{source.upper()}: {last}")
        if parts:
            self._sidebar_status.configure(text=" | ".join(parts))

    def check_updates_now(self):
        """Verificacao imediata de atualizacoes."""
        self._log("Verificando atualizacoes...")
        self._updater.check_now()

    # === Metodos auxiliares ===

    def _log(self, message: str):
        """Adiciona mensagem ao log do dashboard."""
        if "dashboard" in self._pages:
            self._pages["dashboard"].log_message(message)
        logger.info(message)

    def _set_status(self, text: str):
        """Atualiza status na sidebar."""
        self._sidebar_status.configure(text=text)

    def _on_error(self, message: str):
        """Trata erro."""
        self._log(message)
        self._set_status("Erro")
        self._running = False

    def _update_progress(self, current: int, total: int,
                         filled: int, errors: int):
        """Atualiza progresso e estatisticas."""
        dashboard = self._pages["dashboard"]
        dashboard.update_progress(current, total)
        matched = self._count_matched(self._processed)
        saved = self._count_saved(self._processed)
        dashboard.update_stats(
            len(self._processed), matched, filled, saved
        )

    def _load_saved_session(self):
        """Carrega sessao salva e exibe no dashboard."""
        data = self.session_mgr.load()
        if not data:
            return

        platform_foods = data["platform_foods"]
        processed_raw = data["processed_raw"]

        processed = [self.session_mgr.deserialize_pf(r) for r in processed_raw]

        self._platform_foods = platform_foods
        self._processed = processed

        self._update_dashboard_data(platform_foods, processed)
        self.after(0, lambda: self._log(
            f"Sessao anterior carregada: {len(processed)} alimentos"
        ))

    def _save_session(self):
        """Salva sessao atual em disco."""
        if hasattr(self, '_processed') and self._processed:
            pf = getattr(self, '_platform_foods', [])
            self.session_mgr.save(pf, self._processed)

    def _sync_with_saved(self, platform_foods: list[dict], saved: dict) -> tuple:
        """Sincroniza dados atuais da plataforma com sessao salva.
        Retorna (processed, removed_count, new_count).
        """
        saved_processed_raw = saved.get("processed_raw", [])
        saved_by_name = {}
        for raw in saved_processed_raw:
            saved_by_name[raw["platform_name"]] = self.session_mgr.deserialize_pf(raw)

        current_by_name = {f["name"]: f for f in platform_foods}
        current_names = set(current_by_name.keys())
        saved_names = set(saved_by_name.keys())

        new_names = current_names - saved_names
        removed_names = saved_names - current_names
        existing_names = current_names & saved_names

        # Mantem existentes (com match anterior)
        processed = []
        for name in current_names:
            if name in existing_names:
                pf = saved_by_name[name]
                processed.append(pf)
            else:
                # Novo alimento: criar ProcessedFood e buscar match
                from nutrition.matcher import MatchResult
                from automation.orchestrator import ProcessedFood
                new_pf = ProcessedFood(platform_name=name)
                processed.append(new_pf)

        # Matching apenas para novos alimentos
        if new_names:
            new_platform_foods = [
                {"name": n} for n in new_names
            ]

            # Garantir indice TBCA carregado
            if not self.orchestrator.matcher._tbca_names:
                self.after(0, lambda: self._log("Fase 2: Carregando indice TBCA..."))
                search_terms = list(set(
                    f["name"].split(",")[0].strip()
                    for f in platform_foods if len(f["name"]) > 3
                ))
                self.orchestrator.step2_build_tbca_index(search_terms)

            self.after(0, lambda nc=len(new_names): self._log(
                f"Matching {nc} novos alimentos..."
            ))
            new_matches = self.orchestrator.matcher.match_all(
                [n for n in new_names]
            )

            for pf in processed:
                if pf.platform_name in new_names and not pf.match:
                    match = new_matches.get(pf.platform_name)
                    if match:
                        pf.match = match
                        pf.status = "matched"

            matched_new = sum(
                1 for pf in processed
                if pf.platform_name in new_names and pf.status == "matched"
            )
            self.after(0, lambda mn=matched_new, nn=len(new_names): self._log(
                f"Novos: {mn}/{nn} com match"
            ))

        # Itens removidos: marcar e ocultar
        removed_count = 0
        if removed_names:
            for pf in processed:
                if pf.platform_name in removed_names:
                    pf.status = "removed"
                    pf.skip_reason = "removed_from_platform"
                    pf.suggestion = "Alimento removido da plataforma"
                    removed_count += 1

            self.after(0, lambda rc=removed_count: self._log(
                f"Removidos da plataforma: {rc}"
            ))

        new_count = len(new_names)
        return processed, removed_count, new_count

    def _on_close(self):
        """Ao fechar a janela."""
        self._save_session()
        if self._running:
            self._stop_event.set()
        if self._updater:
            self._updater.stop()
        if self.orchestrator.session:
            try:
                self.orchestrator.stop_browser()
            except Exception:
                pass
        self.destroy()

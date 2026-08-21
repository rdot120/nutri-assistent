"""
Gerenciamento de sessão com Playwright.
Lida com login, persistência de sessão, detecção de expiração.
"""
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Callable
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright

if getattr(sys, 'frozen', False):
    _pw_browsers = Path.home() / "AppData" / "Local" / "ms-playwright"
    if _pw_browsers.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_pw_browsers)

logger = logging.getLogger(__name__)


class SessionManager:
    """Gerencia sessão do navegador com a plataforma."""

    def __init__(self, user_data_dir: str, headless: bool = True,
                 slow_mo: int = 0, timeout: int = 30000):
        self.user_data_dir = Path(user_data_dir)
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in: bool = False

    @property
    def page(self) -> Optional[Page]:
        return self._page

    @property
    def is_active(self) -> bool:
        return self._page is not None and not self._page.is_closed()

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    def start(self) -> Page:
        """Inicia o navegador e retorna a página."""
        logger.info("Iniciando navegador...")

        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()

        self._page.set_default_timeout(self.timeout)
        logger.info("Navegador iniciado com sucesso")
        return self._page

    def stop(self):
        """Fecha o navegador."""
        logger.info("Fechando navegador...")
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._logged_in = False
        logger.info("Navegador fechado")

    def navigate(self, url: str, wait_until: str = "networkidle") -> bool:
        """Navega para uma URL."""
        if not self._page:
            logger.error("Página não disponível")
            return False

        try:
            logger.info(f"Navegando para: {url}")
            self._page.goto(url, wait_until=wait_until, timeout=self.timeout)
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Erro ao navegar para {url}: {e}")
            return False

    def check_session_valid(self, login_url: str, dashboard_indicators: list[str]) -> bool:
        """Verifica se a sessão atual é válida."""
        if not self._page:
            return False

        current_url = self._page.url
        logger.debug(f"URL atual: {current_url}")

        # Se está na página de login, sessão não é válida
        if "login" in current_url.lower():
            logger.info("Sessão inválida: redirecionado para login")
            self._logged_in = False
            return False

        # Verificar indicadores de dashboard
        for indicator in dashboard_indicators:
            try:
                element = self._page.query_selector(indicator)
                if element and element.is_visible():
                    logger.info(f"Sessão válida: indicador '{indicator}' encontrado")
                    self._logged_in = True
                    return True
            except Exception:
                continue

        # Se não encontrou indicadores, verificar se não há erro
        try:
            body_text = self._page.text_content("body") or ""
            if "sessão expirada" in body_text.lower() or "session expired" in body_text.lower():
                logger.info("Sessão expirada detectada no conteúdo")
                self._logged_in = False
                return False
        except Exception:
            pass

        # Assumir válida se não encontrou evidências de expiração
        logger.info("Sessão aparentemente válida (sem indicadores negativos)")
        self._logged_in = True
        return True

    def login(self, login_url: str, username: str, password: str,
              username_selector: str = "input#email",
              password_selector: str = "input#password",
              submit_selector: str = 'button[type="submit"]',
              success_indicator: str = None) -> bool:
        """Realiza login na plataforma."""
        if not self._page:
            logger.error("Página não disponível")
            return False

        logger.info(f"Realizando login para usuário: {username[:3]}***")

        try:
            # Navegar para login
            self._page.goto(login_url, wait_until="networkidle", timeout=self.timeout)
            time.sleep(2)

            # Verificar se já está logado (redirecionado do login)
            if "login" not in self._page.url.lower():
                logger.info("Já está logado (redirecionado do login)")
                self._logged_in = True
                return True

            # Preencher credenciais
            self._page.fill(username_selector, username)
            time.sleep(0.5)
            self._page.fill(password_selector, password)
            time.sleep(0.5)

            # Submeter
            self._page.click(submit_selector)

            # Aguardar redirecionamento (URL mudar de /login)
            try:
                self._page.wait_for_function(
                    "() => !window.location.href.includes('login')",
                    timeout=15000
                )
            except Exception:
                pass

            self._page.wait_for_load_state("networkidle", timeout=self.timeout)
            time.sleep(3)

            # Verificar sucesso
            current_url = self._page.url
            logger.debug(f"URL após login: {current_url}")

            if "login" in current_url.lower():
                logger.error("Login falhou: ainda na página de login")
                return False

            self._logged_in = True
            logger.info("Login realizado com sucesso")
            return True

        except Exception as e:
            logger.error(f"Erro durante login: {e}")
            return False

    def ensure_session(self, login_url: str, nutri_url: str,
                       username: str, password: str,
                       dashboard_indicators: list[str] = None) -> bool:
        """Garante que a sessão está ativa e logada."""
        if dashboard_indicators is None:
            dashboard_indicators = [
                'button:has-text("Aplicativo de nutricionais")',
                '[class*="sidebar"]',
                'text=Bem vindo',
            ]

        # Verificar sessão atual
        if self.is_active and self.check_session_valid(login_url, dashboard_indicators):
            logger.info("Sessão existente reutilizada")
            return True

        # Tentar login
        logger.info("Sessão inválida ou inexistente, realizando login...")
        return self.login(login_url, username, password)

    def detect_session_expiry(self) -> bool:
        """Detecta se a sessão expirou durante operação."""
        if not self._page:
            return True

        try:
            current_url = self._page.url

            # Verificar redirecionamento para login
            if "login" in current_url.lower():
                return True

            # Verificar mensagens de expiração
            body_text = self._page.text_content("body") or ""
            expiry_messages = [
                "sessão expirada",
                "session expired",
                "acesso negado",
                "unauthorized",
                "faça login novamente",
                "realize o login",
            ]
            for msg in expiry_messages:
                if msg in body_text.lower():
                    return True

            # Verificar status HTTP (via interceptor)
            return False

        except Exception as e:
            logger.warning(f"Erro ao detectar expiração: {e}")
            return True

    def recover_session(self, login_url: str, username: str, password: str,
                        target_url: str = None) -> bool:
        """Tenta recuperar sessão expirada."""
        logger.info("Tentando recuperar sessão...")

        max_attempts = 3
        for attempt in range(max_attempts):
            logger.info(f"Tentativa {attempt + 1}/{max_attempts}")

            if self.login(login_url, username, password):
                if target_url:
                    self.navigate(target_url)
                logger.info("Sessão recuperada com sucesso")
                return True

            time.sleep(2 ** attempt)  # Backoff exponencial

        logger.error("Falha ao recuperar sessão após múltiplas tentativas")
        return False

    def take_screenshot(self, filename: str, output_dir: Path) -> Optional[Path]:
        """Captura screenshot da página atual."""
        if not self._page:
            return None

        path = output_dir / filename
        try:
            self._page.screenshot(path=str(path), full_page=True)
            logger.debug(f"Screenshot salvo: {path}")
            return path
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {e}")
            return None

    def get_cookies(self) -> list[dict]:
        """Retorna cookies da sessão."""
        if not self._context:
            return []
        return self._context.cookies()

    def get_local_storage(self) -> dict:
        """Retorna dados do localStorage."""
        if not self._page:
            return {}

        try:
            return self._page.evaluate("""
                () => {
                    const items = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        items[key] = localStorage.getItem(key);
                    }
                    return items;
                }
            """)
        except Exception:
            return {}

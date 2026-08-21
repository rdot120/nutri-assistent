"""
Pagina de configuracoes - amigavel para iniciantes.
"""
import customtkinter as ctk

from ..theme import COLORS, FONTS
from ..widgets import ActionButton


def _help_label(parent, text, wraplength=420, **kwargs):
    """Cria uma label de ajuda em texto pequeno e suave."""
    return ctk.CTkLabel(
        parent, text=text,
        font=FONTS["small"], text_color=COLORS["text_soft"],
        anchor="w", wraplength=wraplength, **kwargs
    )


def _section_badge(parent, text, color=COLORS["primary"]):
    """Cria um badge indicador de secao."""
    badge = ctk.CTkFrame(parent, fg_color=color, corner_radius=4)
    ctk.CTkLabel(
        badge, text=text, font=FONTS["small"],
        text_color="white", padx=8, pady=2
    ).pack()
    return badge


class SettingsPage(ctk.CTkScrollableFrame):
    """Pagina de configuracoes do sistema."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._vars = {}

        self._build_intro()
        self._build_platform_section()
        self._build_mode_section()
        self._build_sources_section()
        self._build_ai_section()
        self._build_matching_section()
        self._build_automation_section()
        self._build_save_button()

    def _build_intro(self):
        """Intro com instrucoes gerais."""
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(
            frame, text="Como configurar o Nutri Assistent",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(12, 4))

        _help_label(
            frame,
            text="Preencha os campos abaixo na ordem: "
                 "1) Dados da plataforma, 2) Modo de operacao, "
                 "3) Fontes de dados, 4) IA (opcional). "
                 "Depois clique em 'Salvar'. Os valores ja "
                 "preenchidos funcionam para a maioria dos casos.",
            wraplength=440
        ).pack(fill="x", padx=16, pady=(0, 12))

    def _build_platform_section(self):
        """Secao: Dados de acesso a plataforma."""
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(0, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        _section_badge(header, "1")
        ctk.CTkLabel(
            header, text="  Dados de Acesso",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        _help_label(
            frame,
            text="Sao as mesmas informacoes que voce usa para entrar "
                 "no site da plataforma de nutrientes pelo navegador."
        ).pack(fill="x", padx=16, pady=(0, 8))

        # URL
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            row, text="Endereco do site:", font=FONTS["body"],
            text_color=COLORS["text"], width=120, anchor="w"
        ).pack(side="left")
        var = ctk.StringVar(value="https://balancas.tecnosoftapps.com")
        self._vars["platform_url"] = var
        ctk.CTkEntry(
            row, textvariable=var, width=300,
            font=FONTS["body"], corner_radius=6
        ).pack(side="left", padx=(8, 0))
        _help_label(row, "  Nao altere, a menos que o site tenha mudado",
                    wraplength=250).pack(side="left", padx=(8, 0))

        # Usuario
        row2 = ctk.CTkFrame(frame, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            row2, text="Seu usuario:", font=FONTS["body"],
            text_color=COLORS["text"], width=120, anchor="w"
        ).pack(side="left")
        var2 = ctk.StringVar(value="")
        self._vars["platform_user"] = var2
        ctk.CTkEntry(
            row2, textvariable=var2, width=300,
            font=FONTS["body"], corner_radius=6,
            placeholder_text="ex: evelyn"
        ).pack(side="left", padx=(8, 0))

        # Senha
        row3 = ctk.CTkFrame(frame, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(2, 8))
        ctk.CTkLabel(
            row3, text="Sua senha:", font=FONTS["body"],
            text_color=COLORS["text"], width=120, anchor="w"
        ).pack(side="left")
        var3 = ctk.StringVar(value="")
        self._vars["platform_pass"] = var3
        entry3 = ctk.CTkEntry(
            row3, textvariable=var3, width=300,
            font=FONTS["body"], corner_radius=6, show="*"
        )
        entry3.pack(side="left", padx=(8, 0))
        _help_label(row3, "  Aparecera como bolinhas por seguranca",
                    wraplength=250).pack(side="left", padx=(8, 0))

    def _build_mode_section(self):
        """Secao: Modo de operacao."""
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(0, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        _section_badge(header, "2")
        ctk.CTkLabel(
            header, text="  Modo de Operacao",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        _help_label(
            frame,
            text="Escolha como o sistema vai trabalhar. "
                 "Comece pelo 'Simulacao' ate ter certeza que "
                 "esta funcionando, mude para 'Ao vivo' so quando "
                 "estiver pronto."
        ).pack(fill="x", padx=16, pady=(0, 8))

        # Modo com radio buttons
        modes_frame = ctk.CTkFrame(frame, fg_color="transparent")
        modes_frame.pack(fill="x", padx=16, pady=(0, 8))

        var = ctk.StringVar(value="DRY_RUN")
        self._vars["mode"] = var

        modes = [
            ("DRY_RUN", "Simulacao (recomendado)",
             "Mostra o que seria feito, sem alterar nada. "
             "Use para testar com seguranca."),
            ("TEST", "Teste",
             "Preenche os campos mas nao salva. Util para "
             "verificar se os dados estao corretos."),
            ("LIVE", "Ao vivo",
             "Preenche e salva de verdade. Use so quando "
             "tiver certeza que tudo esta certo."),
        ]

        for value, label, desc in modes:
            row = ctk.CTkFrame(modes_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)

            ctk.CTkRadioButton(
                row, text=label, variable=var, value=value,
                font=FONTS["body"], text_color=COLORS["text"],
                fg_color=COLORS["primary"],
                hover_color=COLORS["primary_light"],
                width=200
            ).pack(side="left")

            _help_label(row, desc, wraplength=300).pack(
                side="left", padx=(8, 0)
            )

    def _build_sources_section(self):
        """Secao: Fontes de dados nutricionais."""
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(0, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        _section_badge(header, "3")
        ctk.CTkLabel(
            header, text="  Fontes de Dados",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        _help_label(
            frame,
            text="De onde o sistema busca os valores nutricionais. "
                 "Mantenha as duas marcadas para ter mais chances "
                 "de encontrar o alimento."
        ).pack(fill="x", padx=16, pady=(0, 8))

        # TBCA
        var_tbca = ctk.BooleanVar(value=True)
        self._vars["tbca_enabled"] = var_tbca
        row_tbca = ctk.CTkFrame(frame, fg_color="transparent")
        row_tbca.pack(fill="x", padx=16, pady=2)
        ctk.CTkCheckBox(
            row_tbca, text="TBCA - Tabela Brasileira de Alimentos",
            variable=var_tbca, font=FONTS["body"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_light"],
            text_color=COLORS["text"]
        ).pack(side="left")
        _help_label(
            row_tbca,
            text="  Fonte oficial do Brasil. Recomendado.",
            wraplength=250
        ).pack(side="left", padx=(8, 0))

        # USDA
        var_usda = ctk.BooleanVar(value=True)
        self._vars["usda_enabled"] = var_usda
        row_usda = ctk.CTkFrame(frame, fg_color="transparent")
        row_usda.pack(fill="x", padx=16, pady=2)
        ctk.CTkCheckBox(
            row_usda, text="USDA - Tabela dos EUA",
            variable=var_usda, font=FONTS["body"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_light"],
            text_color=COLORS["text"]
        ).pack(side="left")
        _help_label(
            row_usda,
            text="  Complemento para alimentos nao encontrados na TBCA.",
            wraplength=280
        ).pack(side="left", padx=(8, 0))

        # USDA API Key
        row_key = ctk.CTkFrame(frame, fg_color="transparent")
        row_key.pack(fill="x", padx=16, pady=(4, 8))
        ctk.CTkLabel(
            row_key, text="Chave USDA:", font=FONTS["body"],
            text_color=COLORS["text"], width=100, anchor="w"
        ).pack(side="left")
        var = ctk.StringVar(value="DEMO_KEY")
        self._vars["usda_api_key"] = var
        ctk.CTkEntry(
            row_key, textvariable=var, width=200,
            font=FONTS["body"], corner_radius=6
        ).pack(side="left", padx=(8, 0))
        _help_label(
            row_key,
            text="  Deixe 'DEMO_KEY' (ja funciona). Para mais "
                 "buscas, crie uma gratis em fdc.nal.usda.gov",
            wraplength=250
        ).pack(side="left", padx=(8, 0))

    def _build_ai_section(self):
        """Secao: Inteligencia Artificial."""
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(0, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        _section_badge(header, "4", color=COLORS["accent"])
        ctk.CTkLabel(
            header, text="  Inteligencia Artificial (opcional)",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        _help_label(
            frame,
            text="Se um alimento nao for encontrado nas tabelas "
                 "acima, a IA pode calcular os valores. "
                 "Recomendamos o Gemini (gratuito do Google)."
        ).pack(fill="x", padx=16, pady=(0, 8))

        # Habilitar/desabilitar IA
        var_ai = ctk.BooleanVar(value=False)
        self._vars["ai_enabled"] = var_ai
        ctk.CTkCheckBox(
            frame, text="Ativar busca por IA quando nao encontrar na tabela",
            variable=var_ai, font=FONTS["body"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_light"],
            text_color=COLORS["text"]
        ).pack(fill="x", padx=16, pady=2)

        _help_label(
            frame,
            text="Se marcado, o sistema usa inteligencia artificial "
                 "como ultimo recurso para buscar valores nutricionais."
        ).pack(fill="x", padx=16, pady=(0, 4))

        # Provedor
        row_prov = ctk.CTkFrame(frame, fg_color="transparent")
        row_prov.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            row_prov, text="Qual IA usar:", font=FONTS["body"],
            text_color=COLORS["text"], width=100, anchor="w"
        ).pack(side="left")
        var_prov = ctk.StringVar(value="gemini")
        self._vars["ai_provider"] = var_prov
        ctk.CTkOptionMenu(
            row_prov, variable=var_prov,
                values=["groq", "openai", "claude", "ollama"],
            width=150, font=FONTS["body"]
        ).pack(side="left", padx=(8, 0))

        # Descricao do provedor
        self._provider_desc = ctk.CTkLabel(
            row_prov, text="  Gratuito (recomendado)",
            font=FONTS["small"], text_color=COLORS["primary"]
        )
        self._provider_desc.pack(side="left", padx=(8, 0))

        # Bind para atualizar descricao
        var_prov.trace_add("write", self._update_provider_desc)

        # API Key
        row_key = ctk.CTkFrame(frame, fg_color="transparent")
        row_key.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            row_key, text="Chave de acesso:", font=FONTS["body"],
            text_color=COLORS["text"], width=100, anchor="w"
        ).pack(side="left")
        var_key = ctk.StringVar(value="")
        self._vars["ai_api_key"] = var_key
        ctk.CTkEntry(
            row_key, textvariable=var_key, width=300,
            font=FONTS["body"], corner_radius=6, show="*"
        ).pack(side="left", padx=(8, 0))

        # Instrucoes para obter chave
        row_how = ctk.CTkFrame(frame, fg_color="transparent")
        row_how.pack(fill="x", padx=16, pady=(0, 4))
        _help_label(
            row_how,
            text="Como pegar a chave: Groq - console.groq.com (gratuito, rapido) | "
                 "Gemini - aistudio.google.com/app/apikey (gratuito, 20/dia) | "
                 "OpenAI - platform.openai.com (pago) | "
                 "Ollama - ollama.com (local, sem chave)",
            wraplength=440
        ).pack(fill="x", padx=110)

        # Modelo
        row_model = ctk.CTkFrame(frame, fg_color="transparent")
        row_model.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            row_model, text="Modelo:", font=FONTS["body"],
            text_color=COLORS["text"], width=100, anchor="w"
        ).pack(side="left")
        var_model = ctk.StringVar(value="")
        self._vars["ai_model"] = var_model
        ctk.CTkEntry(
            row_model, textvariable=var_model, width=200,
            font=FONTS["body"], corner_radius=6,
            placeholder_text="deixe vazio para usar o padrao"
        ).pack(side="left", padx=(8, 0))
        _help_label(
            row_model,
            text="  Nao precisa alterar. O sistema escolhe "
                 "o melhor modelo automaticamente.",
            wraplength=250
        ).pack(side="left", padx=(8, 0))

        # Botao testar
        row_test = ctk.CTkFrame(frame, fg_color="transparent")
        row_test.pack(fill="x", padx=16, pady=(4, 4))
        ctk.CTkLabel(
            row_test, text="             ", font=FONTS["body"],
            width=100
        ).pack(side="left")
        ActionButton(
            row_test, "Testar conexao",
            command=self._test_ai,
            color=COLORS["primary_light"], text_color=COLORS["text"],
            width=120
        ).pack(side="left", padx=(8, 0))

        self._ai_status = ctk.CTkLabel(
            row_test, text="",
            font=FONTS["small"], text_color=COLORS["text_soft"]
        )
        self._ai_status.pack(side="left", padx=(8, 0))

        # Auto fallback
        var_fb = ctk.BooleanVar(value=True)
        self._vars["ai_auto_fallback"] = var_fb
        ctk.CTkCheckBox(
            frame,
            text="Usar IA automaticamente quando nao achar na tabela",
            variable=var_fb, font=FONTS["body"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_light"],
            text_color=COLORS["text"]
        ).pack(fill="x", padx=16, pady=(4, 12))

    def _update_provider_desc(self, *args):
        """Atualiza descricao do provedor selecionado."""
        descs = {
            "groq": "  Gratuito, rapido (recomendado)",
            "openai": "  Pago (necessita chave)",
            "claude": "  Pago (necessita chave)",
            "ollama": "  Gratuito e local (sem internet)",
        }
        prov = self._vars["ai_provider"].get()
        text = descs.get(prov, "")
        color = COLORS["primary"] if "Gratuito" in text else COLORS["text_soft"]
        self._provider_desc.configure(text=text, text_color=color)

    def _update_ai_key_hint(self):
        """Atualiza hint da chave API baseado no provedor."""
        prov = self._vars["ai_provider"].get()
        if not hasattr(self, '_settings'):
            return
        if prov == "groq":
            self._vars["ai_api_key"].set(self._settings.ai.groq_api_key or "")
            self._vars["ai_model"].set(self._settings.ai.groq_model or "")
        elif prov == "ollama":
            self._vars["ai_api_key"].set("")
            self._vars["ai_model"].set(self._settings.ai.ollama_model or "")
        else:
            self._vars["ai_api_key"].set(self._settings.ai.api_key or "")
            self._vars["ai_model"].set(self._settings.ai.model or "")

    def _test_ai(self):
        """Testa conexao com provedor IA."""
        provider = self._vars["ai_provider"].get()
        api_key = self._vars["ai_api_key"].get()
        model = self._vars["ai_model"].get()

        self._ai_status.configure(text="Testando...", text_color=COLORS["text_soft"])

        def _test():
            try:
                from nutrition.ai_provider import (
                    OpenAIProvider,
                    ClaudeProvider, OllamaProvider, GroqProvider
                )
                provider_classes = {
                    "groq": GroqProvider,
                    "openai": OpenAIProvider,
                    "claude": ClaudeProvider,
                    "ollama": OllamaProvider,
                }
                cls = provider_classes.get(provider)
                if not cls:
                    self.after(0, lambda: self._ai_status.configure(
                        text="Provedor invalido",
                        text_color=COLORS["error"]))
                    return

                p = cls(api_key=api_key, model=model)
                if not p.is_available():
                    self.after(0, lambda: self._ai_status.configure(
                        text="Nao disponivel. Verifique a chave.",
                        text_color=COLORS["error"]))
                    return

                result = p.query_nutrition("arroz")
                if result.success:
                    self.after(0, lambda: self._ai_status.configure(
                        text=f"Funcionando! {len(result.fields)} campos "
                             f"em {result.duration_ms}ms",
                        text_color=COLORS["primary"]))
                else:
                    self.after(0, lambda: self._ai_status.configure(
                        text=f"Erro: {result.error[:60]}",
                        text_color=COLORS["error"]))
            except Exception as e:
                self.after(0, lambda: self._ai_status.configure(
                    text=f"Erro: {str(e)[:60]}",
                    text_color=COLORS["error"]))

        import threading
        threading.Thread(target=_test, daemon=True).start()

    def _build_matching_section(self):
        """Secao: Precisao do matching."""
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(0, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        _section_badge(header, "5", color=COLORS["accent"])
        ctk.CTkLabel(
            header, text="  Precisao da Busca",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        _help_label(
            frame,
            text="Arraste para ajustar. Quanto mais alto, mais "
                 "parecido o nome precisa ser. Na duvida, "
                 "mantenha no padrao."
        ).pack(fill="x", padx=16, pady=(0, 8))

        # === Nivel alto ===
        lbl_high = ctk.CTkLabel(
            frame, text="Nivel alto: 80%",
            font=FONTS["body"], text_color=COLORS["text"],
            anchor="w"
        )
        lbl_high.pack(fill="x", padx=16, pady=(4, 0))

        row_high = ctk.CTkFrame(frame, fg_color="transparent")
        row_high.pack(fill="x", padx=16, pady=(0, 2))

        ctk.CTkLabel(
            row_high, text="Baixa", font=FONTS["small"],
            text_color=COLORS["text_soft"], width=40
        ).pack(side="left")

        var_high = ctk.DoubleVar(value=80)
        self._vars["high_threshold"] = var_high
        slider_high = ctk.CTkSlider(
            row_high, from_=40, to=100,
            variable=var_high, width=280,
            fg_color=COLORS["primary_light"],
            progress_color=COLORS["primary"],
            button_color=COLORS["primary"],
            button_hover_color=COLORS["primary_light"],
            command=lambda v: self._on_slider_high(v)
        )
        slider_high.pack(side="left", padx=(8, 8))

        ctk.CTkLabel(
            row_high, text="Alta", font=FONTS["small"],
            text_color=COLORS["text_soft"], width=40
        ).pack(side="left")

        _help_label(
            frame,
            text="  So aceita alimentos com nome muito parecido. "
                 "Mais seguro, pode deixar alguns de fora.",
            wraplength=420
        ).pack(fill="x", padx=16, pady=(0, 8))

        # === Nivel medio ===
        lbl_med = ctk.CTkLabel(
            frame, text="Nivel medio: 60%",
            font=FONTS["body"], text_color=COLORS["text"],
            anchor="w"
        )
        lbl_med.pack(fill="x", padx=16, pady=(4, 0))

        row_med = ctk.CTkFrame(frame, fg_color="transparent")
        row_med.pack(fill="x", padx=16, pady=(0, 2))

        ctk.CTkLabel(
            row_med, text="Baixa", font=FONTS["small"],
            text_color=COLORS["text_soft"], width=40
        ).pack(side="left")

        var_med = ctk.DoubleVar(value=60)
        self._vars["medium_threshold"] = var_med
        slider_med = ctk.CTkSlider(
            row_med, from_=30, to=90,
            variable=var_med, width=280,
            fg_color=COLORS["primary_light"],
            progress_color=COLORS["primary"],
            button_color=COLORS["primary"],
            button_hover_color=COLORS["primary_light"],
            command=lambda v: self._on_slider_med(v)
        )
        slider_med.pack(side="left", padx=(8, 8))

        ctk.CTkLabel(
            row_med, text="Alta", font=FONTS["small"],
            text_color=COLORS["text_soft"], width=40
        ).pack(side="left")

        _help_label(
            frame,
            text="  Aceita nomes mais diferentes. Mais abrangente, "
                 "pode aceitar alimentos parecidos mas nao iguais.",
            wraplength=420
        ).pack(fill="x", padx=16, pady=(0, 12))

        # Salvar referencias para atualizacao
        self._lbl_high = lbl_high
        self._lbl_med = lbl_med

    def _on_slider_high(self, value):
        """Atualiza label do slider alto."""
        v = int(round(value))
        self._lbl_high.configure(text=f"Nivel alto: {v}%")

    def _on_slider_med(self, value):
        """Atualiza label do slider medio."""
        v = int(round(value))
        self._lbl_med.configure(text=f"Nivel medio: {v}%")

    def _build_automation_section(self):
        """Secao: Velocidade e repeticoes."""
        frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"],
                             corner_radius=10)
        frame.pack(fill="x", padx=12, pady=(0, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        _section_badge(header, "6", color=COLORS["accent"])
        ctk.CTkLabel(
            header, text="  Velocidade e Tentativas",
            font=FONTS["section"], text_color=COLORS["text"],
            anchor="w"
        ).pack(side="left")

        _help_label(
            frame,
            text="Controla a velocidade do preenchimento. "
                 "Valores maiores = mais lento, mas mais seguro. "
                 "Nao altere a menos que tenha um motivo."
        ).pack(fill="x", padx=16, pady=(0, 8))

        # Intervalo
        row_int = ctk.CTkFrame(frame, fg_color="transparent")
        row_int.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(
            row_int, text="Pausa entre alimento:", font=FONTS["body"],
            text_color=COLORS["text"], width=130, anchor="w"
        ).pack(side="left")
        var_int = ctk.StringVar(value="1.0")
        self._vars["operation_interval"] = var_int
        ctk.CTkEntry(
            row_int, textvariable=var_int, width=60,
            font=FONTS["body"], corner_radius=6
        ).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            row_int, text="segundos", font=FONTS["body"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(4, 0))
        _help_label(
            row_int,
            text="  Tempo de espera entre cada alimento. "
                 "1s funciona bem na maioria dos casos.",
            wraplength=300
        ).pack(side="left", padx=(8, 0))

        # Max retries
        row_ret = ctk.CTkFrame(frame, fg_color="transparent")
        row_ret.pack(fill="x", padx=16, pady=(2, 8))
        ctk.CTkLabel(
            row_ret, text="Tentar novamente:", font=FONTS["body"],
            text_color=COLORS["text"], width=130, anchor="w"
        ).pack(side="left")
        var_ret = ctk.StringVar(value="3")
        self._vars["max_retries"] = var_ret
        ctk.CTkEntry(
            row_ret, textvariable=var_ret, width=60,
            font=FONTS["body"], corner_radius=6
        ).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(
            row_ret, text="vezes", font=FONTS["body"],
            text_color=COLORS["text"]
        ).pack(side="left", padx=(4, 0))
        _help_label(
            row_ret,
            text="  Se der erro, tenta novamente. 3 vezes e suficiente.",
            wraplength=300
        ).pack(side="left", padx=(8, 0))

    def _build_save_button(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=12, pady=(8, 24))

        ActionButton(
            frame, "Salvar Configuracoes",
            command=self._save,
            color=COLORS["primary"]
        ).pack(side="left")

        self._save_label = ctk.CTkLabel(
            frame, text="",
            font=FONTS["small"], text_color=COLORS["success_dark"]
        )
        self._save_label.pack(side="left", padx=(12, 0))

    def _save(self):
        """Salva configuracoes."""
        settings = self.app.settings

        # Plataforma
        settings.platform.url = self._vars["platform_url"].get()
        settings.platform.username = self._vars["platform_user"].get()
        settings.platform.password = self._vars["platform_pass"].get()
        settings.automation.mode = self._vars["mode"].get()

        # Fontes
        settings.tbca.enabled = self._vars["tbca_enabled"].get()
        settings.usda.enabled = self._vars["usda_enabled"].get()
        settings.usda.api_key = self._vars["usda_api_key"].get()

        # Matching
        try:
            settings.matching.high_confidence = float(
                self._vars["high_threshold"].get()
            )
            settings.matching.medium_confidence = float(
                self._vars["medium_threshold"].get()
            )
        except ValueError:
            pass

        # Automacao
        try:
            settings.automation.operation_interval = float(
                self._vars["operation_interval"].get()
            )
            settings.automation.max_retries = int(
                self._vars["max_retries"].get()
            )
        except ValueError:
            pass

        # IA
        settings.ai.enabled = self._vars["ai_enabled"].get()
        settings.ai.provider = self._vars["ai_provider"].get()
        settings.ai.api_key = self._vars["ai_api_key"].get()
        settings.ai.model = self._vars["ai_model"].get()
        settings.ai.auto_fallback = self._vars["ai_auto_fallback"].get()
        if settings.ai.provider == "groq":
            settings.ai.groq_api_key = self._vars["ai_api_key"].get()
            settings.ai.groq_model = self._vars["ai_model"].get()
        elif settings.ai.provider == "ollama":
            settings.ai.ollama_model = self._vars["ai_model"].get()

        settings.save()
        settings.save_env()
        self._save_label.configure(text="Configuracoes salvas com sucesso!")

    def load_from_settings(self, settings):
        """Carrega valores do settings para os campos."""
        self._settings = settings
        self._vars["platform_url"].set(settings.platform.url)
        self._vars["platform_user"].set(settings.platform.username)
        self._vars["platform_pass"].set(settings.platform.password)
        self._vars["mode"].set(settings.automation.mode)
        self._vars["tbca_enabled"].set(settings.tbca.enabled)
        self._vars["usda_enabled"].set(settings.usda.enabled)
        self._vars["usda_api_key"].set(settings.usda.api_key)
        self._vars["high_threshold"].set(
            float(settings.matching.high_confidence)
        )
        self._vars["medium_threshold"].set(
            float(settings.matching.medium_confidence)
        )
        self._on_slider_high(settings.matching.high_confidence)
        self._on_slider_med(settings.matching.medium_confidence)
        self._vars["operation_interval"].set(
            str(settings.automation.operation_interval)
        )
        self._vars["max_retries"].set(
            str(settings.automation.max_retries)
        )
        self._vars["ai_enabled"].set(settings.ai.enabled)
        self._vars["ai_provider"].set(settings.ai.provider)
        self._vars["ai_api_key"].set(settings.ai.api_key)
        self._vars["ai_model"].set(settings.ai.model)
        self._vars["ai_auto_fallback"].set(settings.ai.auto_fallback)
        self._update_provider_desc()
        self._update_ai_key_hint()

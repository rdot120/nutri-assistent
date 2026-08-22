"""
Validacao de sanidade nutricional para valores por 100 g (RDC 429).

Aplica regras fisico-quimicas para detectar valores impossiveis ou
inconsistentes antes de preencher a plataforma:

- Atwater: kcal ~ 4*carboidrato + 4*proteina + 9*gordura
- Relacoes: fibras <= carboidratos; acucares <= carboidratos;
  acucares adicionados <= totais; saturadas <= totais; trans <= totais
- Limites superiores plausiveis por nutriente
- Nenhum valor negativo

Uso:
    score, issues = validate_fields(fields)
    # score: 0.0 (inaceitavel) a 1.0 (perfeito)
    # issues: lista de strings "SEVERIDADE: descricao"
"""
import logging
import re

logger = logging.getLogger(__name__)

# Campos numericos por 100g e limites superiores plausiveis (por 100 g)
UPPER_BOUNDS = {
    "valorEnergetico429": 900,      # oleo puro = 884
    "carboidratos429": 100,
    "acucaresTotais429": 100,
    "acucaresAdicionados": 100,
    "proteinas429": 100,            # gelatina pura ~85
    "gordurasTotais429": 100,
    "gordurasSaturadas429": 95,
    "gordurasTrans429": 60,
    "fibraAlimentar429": 90,        # farelo
    "sodio429": 9000,               # sal grosso ja passa; shoyu ~6000
    "lactose": 70,                  # leite em po
    "galactose": 50,
    "colesterol": 1400,             # gema em po
    "calcio": 2500,
    "ferro": 45,
    "fosforo": 1300,
    "magnesio": 800,
    "potassio": 4000,
    "zinco": 60,
}

# Tolerancias de arredondamento (g) nas relacoes entre campos
RELATION_TOL = 1.0


def _to_float(value) -> float | None:
    """Converte '12,5' / '12.5' / '12,5 mg' para float."""
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    s = value.strip().replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    if not s or s in ("-", ".", "-."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _f(fields: dict, key: str) -> float | None:
    return _to_float(fields.get(key))


def validate_fields(fields: dict) -> tuple[float, list[str]]:
    """Valida um dicionario de campos nutricionais.

    Retorna (score 0-1, lista de problemas).
    Score: -0.35 por problema grave, -0.15 por leve.
    """
    issues: list[str] = []

    def add(sev: str, msg: str):
        issues.append(f"{sev}: {msg}")

    # --- Negativos sao sempre graves ---
    for key, val in fields.items():
        num = _to_float(val)
        if num is not None and num < -0.01:
            add("GRAVE", f"{key} negativo ({num})")

    # --- Limites superiores ---
    for key, bound in UPPER_BOUNDS.items():
        num = _f(fields, key)
        if num is not None and num > bound * 1.5:
            add("GRAVE", f"{key} acima do plausivel ({num} > {bound})")
        elif num is not None and num > bound:
            add("LEVE", f"{key} alto demais ({num} > {bound})")

    # --- Relacoes entre macronutrientes ---
    carb = _f(fields, "carboidratos429")
    fibra = _f(fields, "fibraAlimentar429")
    if carb is not None and fibra is not None and fibra > carb + RELATION_TOL:
        add("GRAVE", f"fibra ({fibra}) > carbo ({carb})")

    acu_tot = _f(fields, "acucaresTotais429")
    if carb is not None and acu_tot is not None \
            and acu_tot > carb + RELATION_TOL:
        add("GRAVE", f"acucar total ({acu_tot}) > carbo ({carb})")

    acu_add = _f(fields, "acucaresAdicionados")
    if acu_tot is not None and acu_add is not None \
            and acu_add > acu_tot + RELATION_TOL:
        add("LEVE", f"acucar adicionado ({acu_add}) > total ({acu_tot})")

    gord = _f(fields, "gordurasTotais429")
    sat = _f(fields, "gordurasSaturadas429")
    if gord is not None and sat is not None \
            and sat > gord + RELATION_TOL:
        add("GRAVE", f"saturada ({sat}) > gordura total ({gord})")

    trans = _f(fields, "gordurasTrans429")
    if gord is not None and trans is not None \
            and trans > gord + RELATION_TOL:
        add("GRAVE", f"trans ({trans}) > gordura total ({gord})")

    # --- Atwater: kcal vs macros ---
    kcal = _f(fields, "valorEnergetico429")
    prot = _f(fields, "proteinas429")
    if None not in (kcal, carb, prot, gord):
        expected = 4 * carb + 4 * prot + 9 * gord
        if expected >= 10:
            dev = abs(kcal - expected) / max(kcal, expected)
            if dev > 0.40:
                add("GRAVE",
                    f"kcal fora de Atwater: {kcal} vs esperado {expected:.0f}")
            elif dev > 0.20:
                add("LEVE",
                    f"kcal desvia de Atwater: {kcal} vs {expected:.0f} "
                    f"({dev*100:.0f}%)")

    # --- Score final ---
    score = 1.0
    for issue in issues:
        if issue.startswith("GRAVE"):
            score -= 0.35
        else:
            score -= 0.15

    return max(0.0, min(1.0, score)), issues

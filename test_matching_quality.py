import sqlite3, sys, time
sys.path.insert(0, ".")
from nutrition.matcher import FoodMatcher, normalize_food_name, extract_food_base

conn = sqlite3.connect("data/tbca_cache.db")
rows = conn.execute("SELECT code, name FROM tbca_index ORDER BY name").fetchall()
conn.close()

matcher = FoodMatcher(high_threshold=55.0, medium_threshold=35.0)
foods = [{"code": r[0], "name": r[1]} for r in rows]
matcher.load_tbca_index(foods)
print(f"TBCA index: {len(foods)} alimentos")

# Test all problematic names + some good ones
test_names = [
    ("TRIGO", None),
    ("CARNE MOIDA", None),
    ("CREME DE LEITE", None),
    ("FRANGO INTEIRO", None),
    ("QUEIJO MUSSARELA", None),
    ("SAL REFINADO", None),
    ("ACUCAR REFINADO", None),
    ("IOGURTE NATURAL", "Iogurte, natural"),
    ("LEITE INTEGRAL", "Leite, vaca, integral"),
    ("BANANA", "Banana"),
    ("ARROZ", "Arroz"),
    ("FEIJAO", None),
    ("OVO", "Ovo"),
    ("OLEO DE SOJA", None),
    ("FARINHA DE TRIGO", None),
    ("FARINHA DE CENTEIO", None),
    ("MANTEIGA", "Manteiga"),
    ("ACUCAR CRISTAL", None),
    ("REQUEIJAO", None),
    ("CAFE", None),
    ("LEITE DESNATADO", None),
    ("FRANGO PEITO", "Carne, frango, peito"),
    ("CARNE BOI", "Carne, boi"),
    ("CARNE BOVINA", "Carne, bovina"),
    ("MACARRAO", None),
    ("MOLHO DE TOMATE", None),
    ("PAPAGAIO", None),
    ("UVA", None),
    ("MELANCIA", None),
    ("TOMATE", None),
    ("CEBOLA", None),
    ("BATATA", None),
    ("ALHO", None),
    ("LIMAO", None),
    ("ABACAXI", None),
    ("LARANJA", None),
    ("PERA", None),
    ("MANGA", None),
    ("MEXERICAO", None),
    ("COUVE", "Couve"),
    ("BROCOLIS", None),
    ("SPAGHETTI", None),
    ("PRESUNTO", None),
    ("PEixe", None),
    ("SARDINHA", None),
    ("ATUM", None),
    ("LAGOSTA", None),
    ("CAMARAO", None),
]

print(f"\n--- Testes de matching ---")
ok = 0
wrong = 0
miss = 0
total = len(test_names)
for name, expected_hint in test_names:
    result = matcher.match(name)
    if result:
        status = "OK"
        # Check if hint is in the match
        hint_ok = ""
        if expected_hint and expected_hint.lower() not in result.tbca_name.lower():
            hint_ok = " <-- WRONG!"
            wrong += 1
        else:
            ok += 1
        print(f"  {status:3s} {name:25s} -> {result.tbca_name[:55]:55s} ({result.confidence:5.1f}% {result.match_method:12s}){hint_ok}")
    else:
        miss += 1
        print(f"  N/A {name:25s} -> (sem match)")

print(f"\nResumo: {ok} OK, {wrong} ERRADOS, {miss} sem match / {total} total")

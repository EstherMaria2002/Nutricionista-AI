"""
Validación del payload del formulario (rangos + coherencia cruzada).
Devuelve una lista de dicts {nivel: 'error'|'aviso', paso: 0..5, msg}. Un 'error' bloquea la generación.
Pasos: 0 Datos · 1 Objetivo · 2 Alimentación · 3 Cocina · 4 Salud · 5 Resumen
"""
from datetime import date, datetime
from typing import Dict, List

from filtros import construir_prohibidos, ingrediente_prohibido, normalizar
from nutricion import RITMOS

RANGOS = {  # campo: (min, max, etiqueta, paso)
    "edad": (14, 100, "La edad", 0), "altura": (120, 230, "La altura (cm)", 0), "peso": (30, 250, "El peso (kg)", 0),
    "personas": (1, 10, "El número de personas", 2), "comidas_semana": (5, 21, "Los platos únicos por semana", 3),
    "tiempo_coccion": (15, 120, "El tiempo máximo de preparación", 3), "comidas_dia": (3, 6, "El número de comidas al día", 3),
}
INCOMPATIBLES = [("vegano", "pescetariano"), ("vegano", "flexitariano"), ("vegetariano", "pescetariano"),
                 ("vegano", "omnivoro"), ("vegetariano", "omnivoro"), ("pescetariano", "omnivoro")]


def _e(paso, msg): return {"nivel": "error", "paso": paso, "msg": msg}
def _a(paso, msg): return {"nivel": "aviso", "paso": paso, "msg": msg}


def validar_datos(d: dict) -> List[Dict]:
    out: List[Dict] = []
    for campo, (lo, hi, etq, paso) in RANGOS.items():
        v = d.get(campo)
        if v is None or not (lo <= v <= hi):
            out.append(_e(paso, f"{etq} debe estar entre {lo} y {hi}."))
    if out:  # sin rangos válidos no tiene sentido seguir con la coherencia cruzada
        return out

    po = d.get("peso_objetivo")
    if po is not None and not 30 <= po <= 250:
        out.append(_e(0, "El peso objetivo debe estar entre 30 y 250 kg (o déjalo vacío)."))
    if d.get("sexo") == "Prefiero no decirlo":
        out.append(_a(0, "Sin sexo biológico usamos una fórmula neutra para la TMB (±80 kcal de margen)."))

    obj, ritmo = d.get("objetivo"), d.get("ritmo")
    if obj == "Perder peso":
        if po and po > d["peso"]:
            out.append(_a(1, "Tu objetivo es perder peso pero el peso objetivo es mayor que el actual."))
        if d.get("edad", 30) < 18:
            out.append(_a(1, "Eres menor de 18 años: no aplicamos déficit calórico. Consulta con tu pediatra."))
        if d.get("embarazo_lactancia"):
            out.append(_a(1, "⚠️ Embarazo/lactancia: NO se recomienda un déficit calórico. Lo ignoraremos; consulta a tu médico."))
    if obj == "Ganar masa muscular" and po and po < d["peso"]:
        out.append(_a(1, "Quieres ganar masa pero el peso objetivo es menor que el actual."))
    if d.get("tca") == "Sí":
        if obj == "Perder peso" and ritmo == "Rápido (0,75 kg/sem)":
            out.append(_e(1, "Con antecedentes de TCA no ofrecemos un ritmo de pérdida rápido. Elige 'Suave' o consulta a un profesional."))
        elif obj == "Perder peso":
            out.append(_a(1, "Con antecedentes de TCA no aplicamos déficit calórico; trabaja el objetivo con un profesional."))
    fecha = d.get("fecha_limite")
    if fecha:
        f = fecha if isinstance(fecha, date) else datetime.fromisoformat(str(fecha)).date()
        dias = (f - date.today()).days
        if dias <= 0:
            out.append(_a(1, "La fecha límite ya ha pasado o es hoy."))
        elif po and abs(po - d["peso"]) / (dias / 7) > 1.0:
            out.append(_a(1, f"Para llegar a {po} kg en {dias} días necesitarías más de 1 kg/semana: no es un ritmo seguro."))

    pats = {normalizar(p) for p in d.get("restricciones", [])}
    for a, b in INCOMPATIBLES:
        if a in pats and b in pats:
            out.append(_e(2, f"Patrones incompatibles: «{a}» y «{b}». Elige solo uno."))
    if "vegano" in pats and "vegetariano" in pats:
        out.append(_a(2, "«Vegano» ya incluye «vegetariano»."))
    if "vegetariano" in pats and "flexitariano" in pats:
        out.append(_a(2, "Vegetariano y flexitariano se contradicen; priorizamos vegetariano."))
    if "vegano" in pats and "alto en proteinas" in pats:
        out.append(_a(2, "Vegano + alto en proteínas: priorizaremos legumbres, tofu, tempeh, seitán, quinoa y proteína de guisante."))
    if "cetogenica" in pats and "bajo en carbohidratos" in pats:
        out.append(_a(2, "Cetogénica ya implica pocos carbohidratos; aplicaremos el límite más estricto."))
    if "cetogenica" in pats and ("vegano" in pats or "vegetariano" in pats):
        out.append(_a(2, "Keto + vegetal es posible pero con pocas opciones; revisa el resultado."))
    if "cetogenica" in pats and "Mediterránea" in d.get("cocina_preferida", []):
        out.append(_a(2, "Cetogénica + cocina mediterránea: hay tensión (legumbres, cereales y fruta); adaptaremos las recetas."))

    prohibidos = construir_prohibidos(d)
    for campo, etq, nivel in (("ingredientes_obligatorios", "ingrediente obligatorio", "error"),
                              ("ingredientes_aprovechar", "ingrediente a aprovechar", "aviso"),
                              ("alimentos_favoritos", "alimento favorito", "aviso")):
        for ing in d.get(campo) or []:
            m = ingrediente_prohibido(ing, prohibidos)
            if m:
                msg = f"Conflicto: el {etq} {m}."
                out.append(_e(2, msg + " Quítalo o elimina la restricción.") if nivel == "error"
                           else _a(2, msg + " Se ignorará."))
    if d.get("sustitutos") == "Según" and not d.get("sustitutos_detalle"):
        out.append(_a(2, "Dices que aceptas sustitutos 'según' el caso: indica cuáles (tofu, seitán…)."))

    veces = d.get("comer_fuera_veces") or 0
    if veces:
        tipos = d.get("comer_fuera_tipos") or []
        if not tipos:
            out.append(_e(3, "Indica en qué comidas comes fuera (desayuno, comida o cena)."))
        elif veces > 7 * len(tipos):
            out.append(_e(3, f"No puedes comer fuera {veces} veces con solo {len(tipos)} tipo(s) de comida (máx. {7 * len(tipos)})."))
    if d.get("comidas_dia", 4) > 3 and not d.get("incluir_snacks", True):
        out.append(_a(3, "Con más de 3 comidas y sin snacks, las tomas intermedias serán ligeras igualmente."))

    if d.get("condiciones_lista"):
        out.append(_a(4, "Con condiciones médicas, valida este plan con tu médico o dietista-nutricionista."))
    if d.get("dieta_pautada"):
        out.append(_a(4, "Sigues una dieta pautada: la pauta de tu profesional prevalece sobre este plan."))
    return out


def hay_errores(issues: List[Dict]) -> bool:
    return any(i["nivel"] == "error" for i in issues)

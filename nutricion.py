"""
Cálculos nutricionales reproducibles (bug 6) y estructura de comidas del día (bug 8).

Fórmulas
--------
TMB (Mifflin-St Jeor): 10·peso(kg) + 6,25·altura(cm) − 5·edad + s
    s = +5 (masculino) · −161 (femenino) · −78 (prefiero no decirlo: media de ambos, se avisa)
TDEE = TMB · factor de actividad  (1,2 · 1,375 · 1,55 · 1,725 · 1,9)
Ajuste por objetivo (kcal/día): 1 kg de peso ≈ 7.700 kcal  ->  ritmo(kg/sem)·1.100 kcal/día
    perder peso: −ritmo·1100 (máx. −25 % TDEE) · ganar masa: +ritmo·1100 (máx. +20 %)
    recomposición: −5 % · rendimiento deportivo: +5 % · mantener / salud: 0
Límites de seguridad: mínimo 1.500 (H) / 1.200 (M) / 1.350 kcal; sin déficit si embarazo/lactancia,
    TCA = sí, IMC < 18,5 o edad < 18.
Macros: proteína g/kg según objetivo (+0,4 con «alto en proteínas»; 0,8 si enfermedad renal),
    grasa 28 % kcal (mín. 20 %), carbohidratos = resto. Keto: carbos ≈ 8 % kcal. Bajo en carbos: 25 %.
"""
from typing import Dict, List, Optional

from filtros import normalizar

FACTORES_ACTIVIDAD = {"Sedentario": 1.2, "Ligero": 1.375, "Moderado": 1.55, "Activo": 1.725, "Muy activo": 1.9}
DESCRIPCION_ACTIVIDAD = {
    "Sedentario": "Trabajo sentado, poco o nada de ejercicio.",
    "Ligero": "Ejercicio suave 1–3 días/semana.",
    "Moderado": "Ejercicio moderado 3–5 días/semana.",
    "Activo": "Ejercicio intenso 6–7 días/semana.",
    "Muy activo": "Entrenamiento muy intenso o trabajo físico exigente.",
}
OBJETIVOS = ["Perder peso", "Mantener peso", "Ganar masa muscular", "Recomposición corporal",
             "Mejorar rendimiento deportivo", "Mejorar salud general"]
RITMOS = {"Suave (0,25 kg/sem)": 0.25, "Moderado (0,5 kg/sem)": 0.5, "Rápido (0,75 kg/sem)": 0.75}
OBJETIVOS_CON_RITMO = ("Perder peso", "Ganar masa muscular")
KCAL_POR_KG_DIA = 7700 / 7  # ≈ 1100

PROTEINA_G_KG = {"Perder peso": 1.8, "Ganar masa muscular": 1.8, "Recomposición corporal": 2.0,
                 "Mejorar rendimiento deportivo": 1.6, "Mantener peso": 1.2, "Mejorar salud general": 1.2}


def calcular_imc(peso: float, altura_cm: float) -> float:
    return round(peso / ((altura_cm / 100) ** 2), 1)


def categoria_imc(imc: float) -> str:
    if imc < 18.5: return "Bajo peso"
    if imc < 25: return "Normal"
    if imc < 30: return "Sobrepeso"
    return "Obesidad"


def _tiene(lista, *claves) -> bool:
    texto = " | ".join(normalizar(x) for x in (lista or []))
    return any(normalizar(c) in texto for c in claves)


def calcular_tmb(datos: dict):
    """-> (tmb, aviso|None)"""
    base = 10 * datos["peso"] + 6.25 * datos["altura"] - 5 * datos["edad"]
    sexo = datos.get("sexo")
    if sexo == "Masculino":
        return base + 5, None
    if sexo == "Femenino":
        return base - 161, None
    return base - 78, "Sexo no indicado: usamos la media de las fórmulas masculina y femenina (±80 kcal)."


def objetivos_diarios(datos: dict) -> Dict:
    """Devuelve tmb, tdee, kcal objetivo y macros diarios (g) + avisos. Entrada: payload del formulario."""
    avisos: List[str] = []
    peso, altura, edad = float(datos["peso"]), float(datos["altura"]), int(datos["edad"])
    tmb, aviso = calcular_tmb(datos)
    if aviso:
        avisos.append(aviso)
    tdee = tmb * FACTORES_ACTIVIDAD.get(datos.get("actividad"), 1.55)
    imc = calcular_imc(peso, altura)
    obj = datos.get("objetivo", "Mejorar salud general")
    condiciones = datos.get("condiciones_lista") or []
    medicamentos = datos.get("medicamentos_lista") or []

    # ---- ajuste calórico
    ajuste = 0.0
    if obj in OBJETIVOS_CON_RITMO:
        ritmo = RITMOS.get(datos.get("ritmo"), 0.5)
        if obj == "Perder peso":
            ajuste = -min(ritmo * KCAL_POR_KG_DIA, 0.25 * tdee)
        else:
            ajuste = min(ritmo * KCAL_POR_KG_DIA, 0.20 * tdee)
    elif obj == "Recomposición corporal":
        ajuste = -0.05 * tdee
    elif obj == "Mejorar rendimiento deportivo":
        ajuste = 0.05 * tdee

    if ajuste < 0:
        if datos.get("embarazo_lactancia"):
            ajuste = 0; avisos.append("Embarazo/lactancia: no se aplica déficit calórico. Pide pauta a tu matrona o médico.")
        if datos.get("tca") == "Sí":
            ajuste = 0; avisos.append("Por tu historial de TCA no se aplica déficit; trabaja con un profesional.")
        if imc < 18.5:
            ajuste = 0; avisos.append("IMC < 18,5: no se aplica déficit calórico.")
        if edad < 18:
            ajuste = 0; avisos.append("Menor de 18 años: no se aplica déficit calórico; consulta con tu pediatra.")

    kcal = tdee + ajuste
    suelo = {"Masculino": 1500, "Femenino": 1200}.get(datos.get("sexo"), 1350)
    if kcal < suelo:
        avisos.append(f"El objetivo calculado ({kcal:.0f} kcal) quedaba por debajo del mínimo de seguridad; se fija en {suelo} kcal.")
        kcal = suelo
    kcal = round(kcal / 10) * 10

    # ---- macros
    h = altura / 100
    peso_ref = peso if imc < 30 else (peso + 25 * h * h) / 2
    prot_kg = PROTEINA_G_KG.get(obj, 1.2)
    patrones = [normalizar(x) for x in (datos.get("restricciones") or [])]
    if "alto en proteinas" in patrones:
        prot_kg += 0.4
    if _tiene(condiciones, "renal"):
        prot_kg = 0.8
        avisos.append("Enfermedad renal: limitamos la proteína a 0,8 g/kg. Es imprescindible la pauta de tu nefrólogo.")
    prot = min(prot_kg * peso_ref, 0.35 * kcal / 4)

    if "cetogenica" in patrones:
        carbos = max(25.0, 0.08 * kcal / 4)
        grasas = max(0.0, (kcal - 4 * prot - 4 * carbos) / 9)
    else:
        if "bajo en carbohidratos" in patrones:
            carbos = 0.25 * kcal / 4
        else:
            grasas_pct = 0.28
            carbos = (kcal - 4 * prot - 9 * grasas_pct * kcal / 9) / 4
        if _tiene(condiciones, "diabetes", "resistencia a la insulina"):
            carbos = min(carbos, 0.40 * kcal / 4)
        carbos = max(carbos, 100.0 if "bajo en carbohidratos" not in patrones else 60.0)
        grasas = max(0.20 * kcal / 9, (kcal - 4 * prot - 4 * carbos) / 9)
        # reajuste si los mínimos rompieron el total
        total = 4 * prot + 4 * carbos + 9 * grasas
        if abs(total - kcal) > 15:
            carbos = max(0.0, (kcal - 4 * prot - 9 * grasas) / 4)

    # ---- avisos por condiciones / medicación
    if _tiene(condiciones, "diabetes", "resistencia a la insulina"):
        avisos.append("Diabetes/resistencia a la insulina: limitamos carbohidratos al 40 % y priorizamos fibra. Coméntalo con tu equipo médico.")
    if _tiene(condiciones, "hipertension"):
        avisos.append("Hipertensión: reduce la sal y los ultraprocesados; el menú no calcula sodio.")
    if _tiene(condiciones, "gota", "hiperuricemia"):
        avisos.append("Hiperuricemia/gota: conviene limitar vísceras, marisco y alcohol (el menú no calcula purinas).")
    if _tiene(medicamentos, "anticoagul", "acenocumarol", "warfarina", "sintrom"):
        avisos.append("Anticoagulantes: mantén constante la ingesta de verduras de hoja verde (vitamina K).")
    if _tiene(medicamentos, "levotiroxina"):
        avisos.append("Levotiroxina: tómala en ayunas y separada 30–60 min del desayuno; soja y fibra pueden reducir su absorción.")
    if _tiene(medicamentos, "estatina"):
        avisos.append("Estatinas: algunas (p. ej. simvastatina) interaccionan con el pomelo.")
    if _tiene(medicamentos, "metformina"):
        avisos.append("Metformina: reparte los carbohidratos a lo largo del día; consulta tu pauta.")
    if _tiene(medicamentos, "corticoide"):
        avisos.append("Corticoides: pueden aumentar el apetito y la retención de líquidos.")

    return {
        "imc": imc, "categoria_imc": categoria_imc(imc),
        "tmb": round(tmb), "tdee": round(tdee), "ajuste_kcal": round(ajuste),
        "kcal": kcal, "proteinas": round(prot), "grasas": round(grasas), "carbos": round(carbos),
        "avisos": avisos,
    }


# ----------------------------------------------------------------------------
# Estructura de comidas (bug 8)
# ----------------------------------------------------------------------------
PESO_COMIDA = {"Desayuno": 0.25, "Media mañana": 0.10, "Comida": 0.35, "Merienda": 0.12, "Cena": 0.25, "Recena": 0.08}
DISTRIBUCIONES: Dict[int, Dict[str, List[str]]] = {
    3: {"Desayuno · Comida · Cena": ["Desayuno", "Comida", "Cena"]},
    4: {"Desayuno · Comida · Merienda · Cena": ["Desayuno", "Comida", "Merienda", "Cena"],
        "Desayuno · Media mañana · Comida · Cena": ["Desayuno", "Media mañana", "Comida", "Cena"]},
    5: {"Desayuno · Media mañana · Comida · Merienda · Cena": ["Desayuno", "Media mañana", "Comida", "Merienda", "Cena"],
        "Desayuno · Comida · Merienda · Cena · Recena": ["Desayuno", "Comida", "Merienda", "Cena", "Recena"]},
    6: {"Desayuno · Media mañana · Comida · Merienda · Cena · Recena":
        ["Desayuno", "Media mañana", "Comida", "Merienda", "Cena", "Recena"]},
}
AUTOMATICA = "Automática"


def opciones_distribucion(n: int) -> List[str]:
    return [AUTOMATICA] + list(DISTRIBUCIONES[n].keys())


def nombres_comidas(n: int, distribucion: Optional[str] = None) -> List[str]:
    """Nombres de las comidas del día para n comidas y la distribución elegida."""
    n = max(3, min(6, int(n)))
    opciones = DISTRIBUCIONES[n]
    if distribucion in opciones:
        return list(opciones[distribucion])
    return list(next(iter(opciones.values())))


def estructura_comidas(datos: dict) -> List[Dict]:
    """[{nombre, fraccion}] con fracciones de kcal que suman 1 (ajustadas al horario de entreno)."""
    nombres = nombres_comidas(datos.get("comidas_dia", 4), datos.get("distribucion"))
    pesos = {n: PESO_COMIDA[n] for n in nombres}
    horario, tipo = datos.get("horario_entreno"), datos.get("tipo_actividad")
    if horario and tipo and tipo != "Ninguno":
        destino = {"Mañana": "Desayuno", "Mediodía": "Comida", "Noche": "Cena",
                   "Tarde": "Merienda" if "Merienda" in pesos else "Comida"}.get(horario)
        if destino in pesos:
            pesos[destino] += 0.05
    total = sum(pesos.values())
    return [{"nombre": n, "fraccion": pesos[n] / total} for n in nombres]

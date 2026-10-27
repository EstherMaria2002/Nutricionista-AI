# formulario.py
"""
Formulario de 7 bloques (en 6 pasos) para Nutricionista AI.

Cambios de arquitectura respecto al original:
  * Ya NO usa st.form: dentro de un form los widgets no reaccionan hasta el submit, así que no pueden existir
    campos condicionales ni cálculos en vivo. Se usan widgets con `key` + st.session_state.
  * Los widgets de pasos no visibles se conservan con el truco `session_state[k] = session_state[k]`.
  * Chips + texto libre = st.multiselect(accept_new_options=True)  ->  requiere streamlit >= 1.45.
  * Los campos condicionales se limpian (limpiar_condicionales) y además construir_datos() NO envía
    los que no apliquen (sin "datos fantasma").
Contrato: mostrar_formulario() devuelve el payload (dict) solo al pulsar «Generar» con todo válido y con
consentimiento; mantiene los nombres antiguos (edad, sexo, peso, altura, actividad, objetivo, restricciones,
alergias, cocina_preferida, presupuesto, comidas_dia, comidas_semana, tiempo_coccion, incluir_snacks,
condiciones_medicas, medicamentos) y AÑADE los nuevos.
"""
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st

from nutricion import (AUTOMATICA, DESCRIPCION_ACTIVIDAD, FACTORES_ACTIVIDAD, OBJETIVOS, OBJETIVOS_CON_RITMO, RITMOS,
                       calcular_imc as _imc, nombres_comidas, objetivos_diarios, opciones_distribucion)
from ui_components import mostrar_avisos, mostrar_calculos
from validaciones import hay_errores, validar_datos

DISCLAIMER = ("Nutricionista AI no sustituye el consejo de un profesional sanitario. Consulta a tu médico o "
              "dietista-nutricionista antes de iniciar cambios importantes.")
PASOS = ["Datos", "Objetivo", "Alimentación", "Cocina", "Salud", "Resumen"]
RUTA_BORRADOR = Path(os.getenv("NUTRI_BORRADOR", "borrador_formulario.json"))

PATRONES = ["Omnívoro", "Vegetariano", "Vegano", "Flexitariano", "Pescetariano", "Cetogénica", "Paleo",
            "Bajo en carbohidratos", "Alto en proteínas"]
COCINAS = ["Sin preferencia", "Mediterránea", "Asiática", "Mexicana", "Italiana", "Española", "Árabe", "India",
           "Nórdica", "Americana"]
PRESUPUESTO = {"Bajo": "< 30 €", "Medio-Bajo": "30–45 €", "Medio": "45–65 €", "Medio-Alto": "65–90 €", "Alto": "> 90 €"}
SUPERMERCADOS = ["Sin preferencia", "Mercadona", "Lidl", "Carrefour", "Aldi", "Dia", "Comercio local", "Online"]
FORMATOS = ["Tabla semanal", "Lista de recetas", "PDF imprimible", "Solo lista de compra"]

CHIPS_ALERGIAS = ["frutos secos", "marisco", "huevo", "lactosa", "gluten", "soja", "pescado", "sésamo", "cacahuete"]
CHIPS_INTOL = ["FODMAP", "fructosa", "histamina", "lactosa", "gluten"]
CHIPS_VETADOS = ["hígado", "coliflor", "brócoli", "cilantro", "cebolla", "setas", "atún", "legumbres"]
CHIPS_OBLIG = ["pollo", "salmón", "huevos", "legumbres", "arroz", "avena", "aguacate", "tofu", "garbanzos", "quinoa"]
CHIPS_AHORRO = ["arroz", "pasta", "patatas", "huevos", "tomate", "cebolla", "legumbres", "pollo"]
CHIPS_FAV = ["pasta", "pizza", "tortilla", "paella", "ensalada", "sushi", "tacos"]
CHIPS_COND = ["hipertensión", "diabetes tipo 1", "diabetes tipo 2", "resistencia a la insulina", "colesterol alto",
              "hipotiroidismo", "hiperuricemia/gota", "SOP", "enfermedad renal", "celiaquía", "SII", "anemia",
              "hígado graso"]
CHIPS_MED = ["antihistamínicos", "anticonceptivos", "enalapril", "metformina", "levotiroxina", "estatinas",
             "anticoagulantes", "corticoides"]
CHIPS_SUPL = ["proteína en polvo", "creatina", "vitamina D", "omega-3", "magnesio", "hierro", "B12"]
CHIPS_SINT = ["hinchazón", "estreñimiento", "diarrea", "reflujo"]
CHIPS_SUSTIT = ["tofu", "seitán", "proteína vegetal", "edulcorantes"]
CHIPS_EQUIPO = ["Thermomix", "Airfryer", "Olla exprés", "Horno", "Microondas", "Robot de cocina", "Slow cooker"]

DEFAULTS = {
    # Bloque 1
    "nombre": "", "edad": 30, "sexo": "Masculino", "altura": 170.0, "peso": 70.0, "peso_objetivo": 0.0, "cintura": 0.0,
    "composicion": "No lo sé", "grasa_pct": 20.0, "embarazo": False, "menopausia": False,
    # Bloque 2
    "objetivo": "Mejorar salud general", "ritmo": "Moderado (0,5 kg/sem)", "usar_fecha": False,
    "fecha_limite": date.today() + timedelta(weeks=12), "actividad": "Moderado", "tipo_actividad": "Mixto",
    "horario_entreno": "Sin especificar",
    # Bloque 3
    "patrones": ["Omnívoro"], "sin_gluten": False, "sin_lactosa": False, "sin_frutos_secos": False, "sin_huevo": False,
    "sin_soja": False, "sin_marisco": False, "alergias": [], "intolerancias": [], "vetados": [],
    "cocinas": ["Sin preferencia"], "obligatorios": [], "aprovechar": [], "favoritos": [], "picante": "Suave",
    "dulzor": "Medio", "sustitutos": "Sí", "sustitutos_detalle": [],
    # Bloque 4
    "presupuesto": "Medio", "personas": 1, "supermercado": "Sin preferencia", "frecuencia_compra": "1 vez/semana",
    "congelados": True, "suplementos_ok": False,
    # Bloque 5
    "comidas_dia": 4, "distribucion": AUTOMATICA, "tiempo_coccion": 30, "tiempo_por_comida_on": False,
    "t_desayuno": 15, "t_comida": 30, "t_cena": 30, "comidas_semana": 10, "sobras": False, "batch": False,
    "equipamiento": [], "habilidad": "Intermedio", "snacks": True, "postres": False, "bebidas": False,
    "fuera_veces": 0, "fuera_tipos": ["Comida"],
    # Bloque 6
    "condiciones": [], "medicamentos": [], "suplementos": [], "dieta_pautada": False, "dieta_pautada_txt": "",
    "sintomas": [], "tca": "Prefiero no responder",
    # Bloque 7
    "formato": "Tabla semanal", "lista_compra": True, "recetas_det": True, "macros_comida": True, "nombre_plan": "",
}
EJEMPLO = dict(
    nombre="Ana", edad=32, sexo="Femenino", altura=165.0, peso=68.0, peso_objetivo=62.0, objetivo="Perder peso",
    ritmo="Suave (0,25 kg/sem)", actividad="Moderado", tipo_actividad="Mixto", horario_entreno="Tarde",
    patrones=["Flexitariano"], sin_lactosa=True, alergias=["marisco"], vetados=["coliflor"],
    cocinas=["Mediterránea", "Española"], obligatorios=["salmón", "garbanzos"], aprovechar=["arroz"], picante="Suave",
    personas=2, supermercado="Mercadona", comidas_dia=5, tiempo_coccion=30, comidas_semana=12, postres=True,
    equipamiento=["Airfryer"], condiciones=["colesterol alto"], medicamentos=["estatinas"], sintomas=["hinchazón"],
    nombre_plan="Plan primavera",
)


def _k(n): return f"f_{n}"
def _g(n): return st.session_state[_k(n)]


# ----------------------------------------------------------------------------- estado
def _init_estado():
    for n, v in DEFAULTS.items():
        st.session_state.setdefault(_k(n), v)
    st.session_state.setdefault("f_paso", 0)
    st.session_state.setdefault("f_consent", False)
    for n in DEFAULTS:  # mantiene vivos los widgets de pasos no visibles
        st.session_state[_k(n)] = st.session_state[_k(n)]
    st.session_state["f_consent"] = st.session_state["f_consent"]


def limpiar_condicionales():
    """Resetea los campos que dejaron de aplicar (evita datos fantasma y valores inválidos)."""
    s = st.session_state
    if _g("sexo") != "Femenino":
        s[_k("embarazo")] = False; s[_k("menopausia")] = False
    if _g("objetivo") not in OBJETIVOS_CON_RITMO:
        s[_k("ritmo")] = DEFAULTS["ritmo"]
    if _g("composicion") != "% de grasa aproximado":
        s[_k("grasa_pct")] = DEFAULTS["grasa_pct"]
    if not _g("usar_fecha"):
        s[_k("fecha_limite")] = DEFAULTS["fecha_limite"]
    if _g("tipo_actividad") == "Ninguno":
        s[_k("horario_entreno")] = DEFAULTS["horario_entreno"]
    if _g("sustitutos") != "Según":
        s[_k("sustitutos_detalle")] = []
    if not _g("tiempo_por_comida_on"):
        for n in ("t_desayuno", "t_comida", "t_cena"):
            s[_k(n)] = DEFAULTS[n]
    if _g("fuera_veces") == 0:
        s[_k("fuera_tipos")] = DEFAULTS["fuera_tipos"]
    if not _g("dieta_pautada"):
        s[_k("dieta_pautada_txt")] = ""
    if _g("distribucion") not in opciones_distribucion(_g("comidas_dia")):
        s[_k("distribucion")] = AUTOMATICA


# ----------------------------------------------------------------------------- widgets
def chips(label, n, sugerencias, ayuda="", maximo=None):
    """Chips rápidos + texto libre: escribe y pulsa Enter para añadir, o elige una sugerencia."""
    opciones = list(dict.fromkeys(list(sugerencias) + list(st.session_state[_k(n)])))
    kw = {"max_selections": maximo} if maximo else {}
    st.multiselect(label, options=opciones, key=_k(n), accept_new_options=True, help=ayuda,
                   placeholder="Elige una sugerencia o escribe y pulsa Enter", **kw)
    if maximo:
        st.caption(f"{len(_g(n))}/{maximo} seleccionados")


def _lista(n):
    vistos, out = set(), []
    for x in _g(n):
        x = str(x).strip()
        if x and x.lower() not in vistos:
            vistos.add(x.lower()); out.append(x)
    return out


def _ir(i): st.session_state["f_paso"] = i


# ----------------------------------------------------------------------------- payload
def construir_datos() -> dict:
    """Payload final para el motor/IA. Los campos condicionales que no aplican NO se incluyen."""
    sexo, objetivo, tipo = _g("sexo"), _g("objetivo"), _g("tipo_actividad")
    patrones = _g("patrones")
    condiciones, meds = _lista("condiciones"), _lista("medicamentos")
    fuera = _g("fuera_veces")
    d = {
        # --- Bloque 1
        "nombre": _g("nombre").strip() or None, "edad": int(_g("edad")), "sexo": sexo,
        "altura": float(_g("altura")), "peso": float(_g("peso")),
        "peso_objetivo": _g("peso_objetivo") or None, "cintura": _g("cintura") or None,
        "composicion_corporal": "No lo sé" if _g("composicion") == "No lo sé" else f"{_g('grasa_pct'):.0f} % grasa",
        "embarazo_lactancia": _g("embarazo") if sexo == "Femenino" else None,
        "menopausia": _g("menopausia") if sexo == "Femenino" else None,
        # --- Bloque 2
        "objetivo": objetivo, "ritmo": _g("ritmo") if objetivo in OBJETIVOS_CON_RITMO else None,
        "fecha_limite": _g("fecha_limite").isoformat() if _g("usar_fecha") else None,
        "actividad": _g("actividad"), "tipo_actividad": tipo,
        "horario_entreno": _g("horario_entreno") if tipo != "Ninguno" and _g("horario_entreno") != "Sin especificar" else None,
        # --- Bloque 3
        "patrones": list(patrones), "restricciones": [p for p in patrones if p != "Omnívoro"] or ["Ninguna"],
        "sin_gluten": _g("sin_gluten"), "sin_lactosa": _g("sin_lactosa"), "sin_frutos_secos": _g("sin_frutos_secos"),
        "sin_huevo": _g("sin_huevo"), "sin_soja": _g("sin_soja"), "sin_marisco": _g("sin_marisco"),
        "alergias": _lista("alergias"), "intolerancias": _lista("intolerancias"), "vetados": _lista("vetados"),
        "cocina_preferida": list(_g("cocinas")) or ["Sin preferencia"],
        "ingredientes_obligatorios": _lista("obligatorios"), "ingredientes_aprovechar": _lista("aprovechar"),
        "alimentos_favoritos": _lista("favoritos"), "picante": _g("picante"), "dulzor": _g("dulzor"),
        "sustitutos": _g("sustitutos"),
        "sustitutos_detalle": _lista("sustitutos_detalle") if _g("sustitutos") == "Según" else None,
        # --- Bloque 4
        "presupuesto": _g("presupuesto"), "presupuesto_rango": PRESUPUESTO[_g("presupuesto")] + "/persona/semana",
        "personas": int(_g("personas")), "supermercado": _g("supermercado"), "frecuencia_compra": _g("frecuencia_compra"),
        "acepta_congelados": _g("congelados"), "acepta_suplementos": _g("suplementos_ok"),
        # --- Bloque 5
        "comidas_dia": int(_g("comidas_dia")), "distribucion": _g("distribucion"),
        "nombres_comidas": nombres_comidas(_g("comidas_dia"), _g("distribucion")),
        "tiempo_coccion": int(_g("tiempo_coccion")),
        "tiempo_por_comida": ({"Desayuno": _g("t_desayuno"), "Comida": _g("t_comida"), "Cena": _g("t_cena")}
                              if _g("tiempo_por_comida_on") else None),
        "comidas_semana": int(_g("comidas_semana")), "repetir_sobras": _g("sobras"), "batch_cooking": _g("batch"),
        "equipamiento": _lista("equipamiento"), "habilidad_cocina": _g("habilidad"),
        "incluir_snacks": _g("snacks"), "incluir_postres": _g("postres"), "incluir_bebidas": _g("bebidas"),
        "comer_fuera_veces": int(fuera), "comer_fuera_tipos": list(_g("fuera_tipos")) if fuera else None,
        # --- Bloque 6  (str = compatibilidad con el formato antiguo; *_lista = lista)
        "condiciones_medicas": ", ".join(condiciones) or None, "condiciones_lista": condiciones,
        "medicamentos": ", ".join(meds) or None, "medicamentos_lista": meds,
        "suplementos_actuales": _lista("suplementos"), "sintomas_digestivos": _lista("sintomas"),
        "dieta_pautada": _g("dieta_pautada"),
        "dieta_pautada_detalle": _g("dieta_pautada_txt").strip() or None if _g("dieta_pautada") else None,
        "tca": None if _g("tca") == "Prefiero no responder" else _g("tca"),
        # --- Bloque 7
        "formato_menu": _g("formato"), "lista_compra": _g("lista_compra"), "recetas_detalladas": _g("recetas_det"),
        "macros_por_comida": _g("macros_comida"), "idioma": "es", "unidades": "métrico",
        "nombre_plan": _g("nombre_plan").strip() or None,
    }
    return {k: v for k, v in d.items() if v is not None}


# ----------------------------------------------------------------------------- pasos
def _paso_datos():
    st.subheader("1 · Datos personales y antropométricos")
    st.caption("Con estos datos calculamos tu gasto energético. Solo se usan para generar tu menú.")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Nombre (opcional)", key=_k("nombre"), help="Para personalizar tu plan y el PDF.")
        st.number_input("Edad (años)", 14, 100, step=1, key=_k("edad"), help="Entre 14 y 100. La edad ajusta tu metabolismo basal.")
        st.number_input("Altura (cm)", 120.0, 230.0, step=1.0, key=_k("altura"),
                        help="La altura nos ayuda a calcular tus necesidades energéticas.")
        st.number_input("Peso objetivo (kg, opcional)", 0.0, 250.0, step=0.5, key=_k("peso_objetivo"),
                        help="0 = sin peso objetivo. Si lo indicas, lo contrastamos con tu objetivo y ritmo.")
    with c2:
        st.selectbox("Sexo biológico", ["Masculino", "Femenino", "Prefiero no decirlo"], key=_k("sexo"),
                     help="Necesario para la fórmula de metabolismo basal. Si prefieres no decirlo usamos una fórmula neutra.")
        st.number_input("Peso (kg)", 30.0, 250.0, step=0.5, key=_k("peso"), help="Entre 30 y 250 kg.")
        st.number_input("Perímetro de cintura (cm, opcional)", 0.0, 250.0, step=1.0, key=_k("cintura"),
                        help="0 = no indicado. Es un buen indicador de riesgo cardiometabólico.")
    st.selectbox("Composición corporal", ["No lo sé", "% de grasa aproximado"], key=_k("composicion"),
                 help="Si no la conoces, estimamos con valores estándar; no bloquea nada.")
    if _g("composicion") == "% de grasa aproximado":
        st.number_input("% de grasa corporal aproximado", 3.0, 60.0, step=1.0, key=_k("grasa_pct"))
    if _g("sexo") == "Femenino":
        st.markdown("**Situación fisiológica**")
        st.checkbox("Embarazo / lactancia", key=_k("embarazo"),
                    help="Crítico: en embarazo/lactancia nunca aplicamos déficit calórico.")
        st.checkbox("Menopausia", key=_k("menopausia"), help="Puede influir en el reparto de macros y en el apetito.")
    st.divider()
    mostrar_calculos(objetivos_diarios(construir_datos()))


def _paso_objetivo():
    st.subheader("2 · Objetivo y contexto")
    st.selectbox("Objetivo principal", OBJETIVOS, key=_k("objetivo"), help="Define el ajuste calórico y el reparto de macros.")
    if _g("objetivo") in OBJETIVOS_CON_RITMO:
        st.selectbox("Ritmo deseado", list(RITMOS), key=_k("ritmo"),
                     help="Un ritmo moderado es sostenible; el rápido solo se permite sin antecedentes de TCA.")
    st.checkbox("Tengo una fecha límite / horizonte", key=_k("usar_fecha"))
    if _g("usar_fecha"):
        st.date_input("Fecha límite", min_value=date.today(), key=_k("fecha_limite"))
    st.select_slider("Nivel de actividad física", options=list(FACTORES_ACTIVIDAD), key=_k("actividad"))
    st.caption(f"ℹ️ **{_g('actividad')}:** {DESCRIPCION_ACTIVIDAD[_g('actividad')]}")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Tipo de actividad principal", ["Ninguno", "Fuerza", "Cardio", "Mixto"], key=_k("tipo_actividad"))
    with c2:
        if _g("tipo_actividad") != "Ninguno":
            st.selectbox("Horario de entrenamiento", ["Sin especificar", "Mañana", "Mediodía", "Tarde", "Noche"],
                         key=_k("horario_entreno"), help="Colocamos más energía en la comida más cercana al entrenamiento.")
    st.divider()
    mostrar_calculos(objetivos_diarios(construir_datos()))


def _paso_alimentacion():
    st.subheader("3 · Preferencias y restricciones alimentarias")
    st.markdown("##### 3.1 Restricciones (excluyentes)")
    st.multiselect("Patrón alimentario", PATRONES, key=_k("patrones"),
                   help="Puedes combinar los que sean compatibles (p. ej. vegano + alto en proteínas).")
    st.markdown("**Excluir siempre:**")
    c = st.columns(3)
    for col, (n, t) in zip(c * 2, [("sin_gluten", "Sin gluten"), ("sin_lactosa", "Sin lactosa"),
                                   ("sin_frutos_secos", "Sin frutos secos"), ("sin_huevo", "Sin huevo"),
                                   ("sin_soja", "Sin soja"), ("sin_marisco", "Sin marisco")]):
        with col:
            st.checkbox(t, key=_k(n))
    chips("Alergias específicas", "alergias", CHIPS_ALERGIAS, "Se tratan como PROHIBICIÓN ABSOLUTA (incluye sinónimos: gambas → marisco).")
    chips("Intolerancias", "intolerancias", CHIPS_INTOL, "FODMAP, fructosa, histamina… también se filtran.")
    chips("Alimentos que NO quieres ver nunca", "vetados", CHIPS_VETADOS, "Nunca aparecerán en ninguna receta.")
    st.markdown("##### 3.2 Preferencias positivas")
    st.multiselect("Estilo de cocina preferido", COCINAS, key=_k("cocinas"))
    chips("Ingredientes que quieres usar sí o sí ⭐", "obligatorios", CHIPS_OBLIG,
          "Intentaremos incluirlos en alguna comida. Si chocan con una alergia/restricción te avisamos.", maximo=10)
    chips("Ingredientes que quieres aprovechar / tienes en casa", "aprovechar", CHIPS_AHORRO, "Se priorizan, sin obligar.")
    chips("Alimentos favoritos (opcional)", "favoritos", CHIPS_FAV)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox("Nivel de picante", ["Sin picante", "Suave", "Medio", "Alto"], key=_k("picante"))
    with c2:
        st.selectbox("Dulzor preferido", ["Bajo", "Medio", "Alto"], key=_k("dulzor"))
    with c3:
        st.radio("¿Aceptas sustitutos?", ["Sí", "No", "Según"], key=_k("sustitutos"), horizontal=True,
                 help="Tofu, seitán, proteína vegetal, edulcorantes…")
    if _g("sustitutos") == "Según":
        chips("¿Cuáles aceptas?", "sustitutos_detalle", CHIPS_SUSTIT)
    st.markdown("##### 4 · Presupuesto y logística de compra")
    st.select_slider("Presupuesto semanal aproximado", options=list(PRESUPUESTO), key=_k("presupuesto"),
                     format_func=lambda x: f"{x} ({PRESUPUESTO[x]}/persona)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.number_input("Nº de personas", 1, 10, step=1, key=_k("personas"), help="Escala la lista de la compra.")
    with c2:
        st.selectbox("Supermercado habitual", SUPERMERCADOS, key=_k("supermercado"))
    with c3:
        st.selectbox("Frecuencia de compra", ["1 vez/semana", "2 veces/semana", "Diaria"], key=_k("frecuencia_compra"))
    c1, c2 = st.columns(2)
    with c1:
        st.toggle("Acepto congelados / conservas", key=_k("congelados"))
    with c2:
        st.toggle("Acepto suplementos (opcional)", key=_k("suplementos_ok"))


def _paso_cocina():
    st.subheader("5 · Organización y cocina")
    c1, c2 = st.columns(2)
    with c1:
        st.slider("Nº de comidas al día", 3, 6, key=_k("comidas_dia"), help="El menú tendrá exactamente este número de comidas.")
        st.selectbox("Distribución deseada", opciones_distribucion(_g("comidas_dia")), key=_k("distribucion"))
        st.slider("Platos únicos por semana (evita repeticiones)", 5, 21, key=_k("comidas_semana"))
        st.toggle("Permitir repetir sobras", key=_k("sobras"), help="Repetir el plato de ayer sin penalización.")
        st.toggle("Batch cooking", key=_k("batch"), help="Cocinar una vez y repetir varios días: menos platos distintos.")
    with c2:
        st.select_slider("Tiempo máximo de preparación (min)", [15, 30, 45, 60, 90, 120], key=_k("tiempo_coccion"))
        st.checkbox("Definir tiempo máximo por comida", key=_k("tiempo_por_comida_on"))
        if _g("tiempo_por_comida_on"):
            for n, t in (("t_desayuno", "Desayuno"), ("t_comida", "Comida"), ("t_cena", "Cena")):
                st.select_slider(f"Máx. {t.lower()} (min)", [15, 30, 45, 60, 90, 120], key=_k(n))
        st.selectbox("Nivel en la cocina", ["Principiante", "Intermedio", "Avanzado"], key=_k("habilidad"))
    chips("Equipamiento", "equipamiento", CHIPS_EQUIPO)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.checkbox("Incluir snacks saludables", key=_k("snacks"))
    with c2:
        st.checkbox("Incluir postres", key=_k("postres"))
    with c3:
        st.checkbox("Incluir bebidas (smoothies, infusiones)", key=_k("bebidas"))
    st.number_input("¿Cuántas veces por semana comes fuera de casa?", 0, 21, step=1, key=_k("fuera_veces"),
                    help="Esas tomas no se planifican y se ajustan los objetivos del día.")
    if _g("fuera_veces") > 0:
        st.multiselect("¿En qué comidas?", ["Desayuno", "Comida", "Cena"], key=_k("fuera_tipos"))


def _paso_salud():
    st.subheader("6 · Salud (crítico)")
    st.caption("Esta información ajusta el plan y genera avisos de seguridad. Es opcional pero muy recomendable.")
    chips("Condiciones médicas", "condiciones", CHIPS_COND)
    chips("Medicamentos", "medicamentos", CHIPS_MED, "Para avisarte de interacciones habituales con la dieta.")
    chips("Suplementos actuales (opcional)", "suplementos", CHIPS_SUPL)
    st.toggle("¿Sigues una dieta pautada por un profesional?", key=_k("dieta_pautada"))
    if _g("dieta_pautada"):
        st.text_input("Cuéntanos en qué consiste", key=_k("dieta_pautada_txt"))
    chips("Síntomas digestivos frecuentes (opcional)", "sintomas", CHIPS_SINT)
    st.selectbox("¿Has tenido un trastorno de la conducta alimentaria (TCA)?", ["Prefiero no responder", "No", "Sí"],
                 key=_k("tca"), help="Pregunta sensible y opcional. Si respondes «Sí», evitamos déficits y ritmos rápidos.")
    st.info(DISCLAIMER, icon="⚕️")


def _bloque_resumen(titulo, paso, filas):
    with st.container(border=True):
        c1, c2 = st.columns([5, 1])
        c1.markdown(f"**{titulo}**")
        c2.button("✏️ Editar", key=f"edit_{paso}_{titulo}", on_click=_ir, args=(paso,), use_container_width=True)
        for k, v in filas:
            if v not in (None, "", [], False):
                st.markdown(f"- **{k}:** {', '.join(v) if isinstance(v, list) else v}")


def _paso_resumen(datos):
    st.subheader("7 · Entrega del menú y resumen")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Formato del menú", FORMATOS, key=_k("formato"))
        st.text_input("Nombre del plan (opcional)", key=_k("nombre_plan"))
        st.text_input("Idioma / unidades", "Español · Sistema métrico (kg, cm, kcal, €)", disabled=True)
    with c2:
        st.toggle("Lista de la compra", key=_k("lista_compra"))
        st.toggle("Recetas detalladas", key=_k("recetas_det"))
        st.toggle("Macros por comida", key=_k("macros_comida"))
    datos = construir_datos()
    st.markdown("### Revisa esto: es lo que la IA usará")
    _bloque_resumen("Datos personales", 0, [("Edad", f"{datos['edad']} años"), ("Sexo", datos["sexo"]),
                    ("Altura / peso", f"{datos['altura']:.0f} cm / {datos['peso']:.1f} kg"),
                    ("Peso objetivo", datos.get("peso_objetivo")), ("Embarazo/lactancia", datos.get("embarazo_lactancia"))])
    _bloque_resumen("Objetivo", 1, [("Objetivo", datos["objetivo"]), ("Ritmo", datos.get("ritmo")),
                    ("Actividad", datos["actividad"]), ("Tipo", datos.get("tipo_actividad")),
                    ("Horario", datos.get("horario_entreno")), ("Fecha límite", datos.get("fecha_limite"))])
    _bloque_resumen("Alimentación", 2, [("Patrón", datos["restricciones"]), ("Alergias", datos["alergias"]),
                    ("Intolerancias", datos["intolerancias"]), ("Vetados", datos["vetados"]),
                    ("Sí o sí", datos["ingredientes_obligatorios"]), ("Cocina", datos["cocina_preferida"]),
                    ("Presupuesto", f"{datos['presupuesto']} ({datos['presupuesto_rango']})"), ("Personas", datos["personas"])])
    _bloque_resumen("Cocina", 3, [("Comidas/día", f"{datos['comidas_dia']}: {', '.join(datos['nombres_comidas'])}"),
                    ("Platos únicos/semana", datos["comidas_semana"]), ("Tiempo máx.", f"{datos['tiempo_coccion']} min"),
                    ("Comer fuera", datos.get("comer_fuera_veces") or None)])
    _bloque_resumen("Salud", 4, [("Condiciones", datos["condiciones_lista"]), ("Medicamentos", datos["medicamentos_lista"]),
                    ("Dieta pautada", datos.get("dieta_pautada_detalle") or datos.get("dieta_pautada"))])
    mostrar_calculos(objetivos_diarios(datos), "📐 Objetivos que usará el menú")

    issues = validar_datos(datos)
    if issues:
        st.markdown("### Avisos y errores")
        for i in issues:
            col1, col2 = st.columns([6, 1])
            (col1.error if i["nivel"] == "error" else col1.warning)(i["msg"])
            if i["paso"] != 5:
                col2.button("Ir", key=f"ir_{hashlib.md5(i['msg'].encode()).hexdigest()[:8]}", on_click=_ir, args=(i["paso"],))

    st.divider()
    st.markdown("#### 🔒 Privacidad y datos de salud")
    st.caption("Tratamos datos de salud (categoría especial, art. 9 RGPD) únicamente para generar tu menú. "
               "Se guardan en la base de datos local de esta aplicación y puedes pedir su borrado. "
               "No se venden ni se comparten con terceros, salvo los proveedores de IA/recetas necesarios para generar el plan.")
    st.checkbox("Doy mi consentimiento explícito para el tratamiento de mis datos de salud con esta finalidad.",
                key="f_consent")
    st.info(DISCLAIMER, icon="⚕️")
    return datos, issues


# ----------------------------------------------------------------------------- borrador / ejemplo
def _guardar_borrador():
    datos = {n: st.session_state[_k(n)] for n in DEFAULTS}
    datos["_paso"] = st.session_state.get("f_paso", 0)
    RUTA_BORRADOR.write_text(json.dumps(datos, ensure_ascii=False, indent=1,
                                        default=lambda o: o.isoformat() if isinstance(o, (date, datetime)) else str(o)),
                             encoding="utf-8")
    st.toast("💾 Borrador guardado. Podrás recuperarlo más tarde.")


def _cargar_borrador():
    try:
        datos = json.loads(RUTA_BORRADOR.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        st.toast("No se pudo leer el borrador."); return
    for n, base in DEFAULTS.items():
        if n not in datos:
            continue
        v = datos[n]
        try:
            v = date.fromisoformat(v) if isinstance(base, date) else (type(base)(v) if not isinstance(base, list) else list(v))
        except (TypeError, ValueError):
            continue
        st.session_state[_k(n)] = v
    st.session_state["f_paso"] = int(datos.get("_paso", 0))
    st.toast("📂 Borrador recuperado.")


def _rellenar_ejemplo():
    for n, v in DEFAULTS.items():
        st.session_state[_k(n)] = v
    for n, v in EJEMPLO.items():
        st.session_state[_k(n)] = v
    st.session_state["f_consent"] = False
    st.toast("🧪 Datos de ejemplo cargados. Revisa el resumen y acepta el consentimiento para generar.")


# ----------------------------------------------------------------------------- entrada principal
def mostrar_formulario():
    """Devuelve el payload (dict) al pulsar «Generar» con datos válidos y consentimiento; si no, None."""
    _init_estado()
    limpiar_condicionales()

    st.title("🍽️ Planificador de menús con IA")
    st.markdown("Completa tus datos para recibir un menú semanal personalizado")

    a, b, c = st.columns(3)
    a.button("🧪 Rellenar con ejemplo", on_click=_rellenar_ejemplo, use_container_width=True)
    b.button("💾 Guardar y continuar más tarde", on_click=_guardar_borrador, use_container_width=True)
    c.button("📂 Recuperar borrador", on_click=_cargar_borrador, use_container_width=True, disabled=not RUTA_BORRADOR.exists())

    paso = st.session_state["f_paso"]
    st.progress((paso + 1) / len(PASOS), text=f"Paso {paso + 1} de {len(PASOS)} · {PASOS[paso]}")
    cols = st.columns(len(PASOS))
    for i, (col, nombre) in enumerate(zip(cols, PASOS)):
        col.button(f"{i + 1}. {nombre}", key=f"nav_{i}", on_click=_ir, args=(i,), use_container_width=True,
                   type="primary" if i == paso else "secondary")

    generar = False
    datos = None
    if paso == 0: _paso_datos()
    elif paso == 1: _paso_objetivo()
    elif paso == 2: _paso_alimentacion()
    elif paso == 3: _paso_cocina()
    elif paso == 4: _paso_salud()
    else:
        datos, issues = _paso_resumen(None)
        bloqueado = hay_errores(issues) or not st.session_state["f_consent"]
        if not st.session_state["f_consent"]:
            st.caption("🔒 Acepta el consentimiento para poder generar el menú.")
        if hay_errores(issues):
            st.caption("⛔ Corrige los errores marcados en rojo para poder generar el menú.")
        generar = st.button("🎯 Generar menú semanal", type="primary", use_container_width=True, disabled=bloqueado)

    if paso < 5:
        mostrar_avisos(validar_datos(construir_datos()), paso)
        n1, n2 = st.columns(2)
        n1.button("← Anterior", on_click=_ir, args=(max(0, paso - 1),), disabled=paso == 0, use_container_width=True)
        n2.button("Siguiente →", on_click=_ir, args=(paso + 1,), use_container_width=True, type="primary")
    else:
        st.button("← Anterior", on_click=_ir, args=(4,))

    if generar and datos is not None:
        d = dict(datos)
        d["consentimiento_rgpd"] = True
        return d
    return None


# ----------------------------------------------------------------------------- utilidades (existentes)
def calcular_imc(peso: float, altura: float) -> float:
    """Calcula el IMC del usuario"""
    return _imc(peso, altura)


def obtener_recomendacion_imc(imc: float) -> str:
    """Recomendación basada en IMC"""
    if imc < 18.5:
        return "Bajo peso - Consulta con un profesional"
    elif imc < 25:
        return "Peso normal - Mantén hábitos saludables"
    elif imc < 30:
        return "Sobrepeso - Enfoque en alimentación balanceada"
    else:
        return "Obesidad - Recomendamos supervisión profesional"


def mostrar_resumen_usuario(datos: dict):
    """Muestra un resumen de los datos ingresados"""
    imc = calcular_imc(datos["peso"], datos["altura"])
    with st.expander("📋 Resumen de tus datos"):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Edad:** {datos['edad']} años")
            st.write(f"**Peso:** {datos['peso']} kg")
            st.write(f"**Altura:** {datos['altura']} cm")
            st.write(f"**IMC:** {imc} - {obtener_recomendacion_imc(imc)}")
        with col2:
            st.write(f"**Objetivo:** {datos['objetivo']}")
            st.write(f"**Actividad:** {datos['actividad']}")
            st.write(f"**Restricciones:** {', '.join(datos['restricciones'])}")
            if datos['alergias']:
                st.write(f"**Alergias:** {', '.join(datos['alergias'])}")

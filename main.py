# main.py
import socket
import time

import streamlit as st

from apis_recetas import APIRecetas
from database import inicializar_db
from exportador import Exportador, nombre_archivo_pdf
from formulario import mostrar_formulario
from generar_menu import GeneradorMenuIA
from nutricion import objetivos_diarios
from orquestador import PlanError, generar_plan
from planificador import DIAS
from ui_components import show_friendly_error

socket.setdefaulttimeout(30)

DISCLAIMER = ("Nutricionista AI no sustituye el consejo de un profesional sanitario. Consulta a tu médico o "
              "dietista-nutricionista antes de iniciar cambios importantes.")

# --- TEMAS: todo el CSS usa variables (nada hardcodeado en claro) --------------------------------------------------
TEMAS = {
    "Oscuro": {"bg": "#0e1117", "card": "#1a1d27", "input": "#262a36", "border": "#3d4252", "text": "#f1f1f4",
               "muted": "#b9bcc8", "button": "#2b3040", "hover": "#343a4d", "accent": "#2e7d32",
               "chip": "#284b32", "chip_text": "#f1f1f4", "scheme": "dark"},
    "Claro": {"bg": "#f5f6f8", "card": "#ffffff", "input": "#ffffff", "border": "#c4c8d0", "text": "#1b1d22",
              "muted": "#4a4f5a", "button": "#e6e9ee", "hover": "#e7eaf0", "accent": "#2e7d32",
              "chip": "#dff0e1", "chip_text": "#14391a", "scheme": "light"},
}


def apply_theme(theme: str):
    c = TEMAS[theme]
    variables = "".join(f"--{k.replace('_', '-')}: {v};" for k, v in c.items() if k != "scheme")
    st.markdown(f"""
<style>
:root {{ {variables} color-scheme: {c['scheme']}; }}
html {{ font-size: 16px; }}   /* tamaño de fuente FIJO (medio): ya no hay selector (punto 1) */
#MainMenu, footer {{ visibility: hidden; }}

/* ---- base */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background: var(--bg); color: var(--text); }}
.stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"] *, .stApp [data-testid="stMetric"] *,
.stApp th, .stApp td, .stApp summary {{ color: var(--text) !important; }}
.stApp [data-testid="stCaptionContainer"], .stApp small, .stApp [data-testid="stMetricDelta"] {{ color: var(--muted) !important; }}
table, th, td {{ border-color: var(--border) !important; }}
* {{ scrollbar-color: var(--border) transparent; }}

/* ---- cabecera + Deploy (punto 3) */
header[data-testid="stHeader"], [data-testid="stToolbar"] {{ background: var(--bg) !important; border-bottom: 1px solid var(--border); }}
[data-testid="stToolbar"] *, [data-testid="stAppDeployButton"] *, [data-testid="stMainMenu"] *,
[data-testid="stToolbarActionButton"] * {{ color: var(--text) !important; fill: var(--text) !important; }}
[data-testid="stAppDeployButton"] button {{ background: var(--button) !important; border: 1px solid var(--border) !important; }}
div[role="dialog"], [data-testid="stDialog"] > div, [data-baseweb="modal"] > div > div, [data-testid="stModal"] div[role="dialog"] {{
    background: var(--card) !important; color: var(--text) !important; border: 1px solid var(--border) !important; }}
div[role="dialog"] *, [data-baseweb="modal"] * {{ color: var(--text) !important; border-color: var(--border) !important; }}
div[role="dialog"] code, div[role="dialog"] pre, div[role="dialog"] input, div[role="dialog"] textarea {{ background: var(--input) !important; }}
div[role="dialog"] a {{ color: #7cc4ff !important; }}

/* ---- sidebar + "Configuración" sin recortar (punto 4) */
section[data-testid="stSidebar"] {{ background: var(--card) !important; border-right: 1px solid var(--border); }}
section[data-testid="stSidebar"][aria-expanded="true"] {{ min-width: 320px !important; width: 320px !important; }}
section[data-testid="stSidebar"] h1 {{ font-size: 1.5rem !important; white-space: nowrap; overflow: visible; text-overflow: clip; }}
@media (max-width: 768px) {{
  section[data-testid="stSidebar"][aria-expanded="true"] {{ min-width: 0 !important; width: min(88vw, 320px) !important; }}
  section[data-testid="stSidebar"] h1 {{ white-space: normal; }}
}}

/* ---- inputs */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {{
    background: var(--input) !important; border-color: var(--border) !important; border-radius: 8px !important; }}
input, textarea, [data-baseweb="select"] input, [data-baseweb="select"] [class*="singleValue"], [data-baseweb="select"] div {{
    background-color: transparent; color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; caret-color: var(--text); }}
input::placeholder, textarea::placeholder {{ color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; opacity: 1; }}
[data-baseweb="select"] svg, [data-baseweb="input"] svg {{ fill: var(--text) !important; }}
select, option {{ background: var(--input); color: var(--text); }}
[data-baseweb="tag"] {{ background: var(--chip) !important; color: var(--chip-text) !important; }}
[data-baseweb="tag"] * {{ color: var(--chip-text) !important; fill: var(--chip-text) !important; }}

/* ---- DESPLEGABLES legibles en oscuro (punto 2): panel + opciones + hover/selected/disabled */
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"], div[role="listbox"] {{
    background: var(--card) !important; color: var(--text) !important; border-color: var(--border) !important; }}
[data-baseweb="popover"] li, [data-baseweb="menu"] li, li[role="option"], div[role="option"] {{
    background: transparent !important; color: var(--text) !important; min-height: 44px; display: flex; align-items: center; }}
[data-baseweb="popover"] li *, li[role="option"] *, div[role="option"] * {{ color: inherit !important; }}
li[role="option"]:hover, div[role="option"]:hover, [data-baseweb="menu"] li:hover, li[role="option"]:focus-visible,
li[role="option"][aria-selected="true"], div[role="option"][aria-selected="true"], li[data-highlighted="true"] {{
    background: var(--hover) !important; color: var(--text) !important; }}
li[role="option"][aria-disabled="true"], div[role="option"][aria-disabled="true"] {{ color: var(--muted) !important; opacity: .7; }}

/* ---- botones / controles (táctil >= 44px, contraste AA) */
.stButton button, .stDownloadButton button, .stFormSubmitButton button {{
    background: var(--button) !important; color: var(--text) !important; border: 1px solid var(--border) !important;
    border-radius: 8px !important; min-height: 44px; }}
.stButton button:hover, .stDownloadButton button:hover {{ background: var(--accent) !important; color: #fff !important; }}
.stButton button:hover *, .stDownloadButton button:hover * {{ color: #fff !important; }}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {{ background: var(--accent) !important; color: #fff !important; }}
.stButton button[kind="primary"] * {{ color: #fff !important; }}
.stButton button:disabled {{ opacity: .55; cursor: not-allowed; }}
[data-testid="stCheckbox"] label, [data-testid="stToggle"] label, [data-testid="stRadio"] label {{ min-height: 44px; align-items: center; }}
:focus-visible {{ outline: 3px solid #ffb300 !important; outline-offset: 2px; }}

/* ---- contenedores */
[data-testid="stExpander"] details, [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stStatusWidget"],
[data-testid="stMetric"] {{ background: var(--card) !important; border-color: var(--border) !important; border-radius: 10px; }}
.stProgress > div > div > div > div {{ background-color: var(--accent) !important; }}
code, pre {{ background: var(--card) !important; color: var(--text) !important; }}
</style>""", unsafe_allow_html=True)


# --- Spoonacular: no gastar puntos en cada rerun -------------------------------------------------------------------
def _spoonacular_disponible(api: APIRecetas) -> bool:
    cache = st.session_state.get("spoon_cache")
    if cache and time.time() - cache[0] < 600:
        return cache[1]
    ok = api.hay_puntos_disponibles()
    st.session_state["spoon_cache"] = (time.time(), ok)
    return ok


def _tabla_objetivos(plan):
    o, p, s = plan["objetivos"], plan["promedio_diario"], plan["semaforo_semana"]
    filas = [("Calorías", "calorias", o["kcal"], "kcal"), ("Proteínas", "proteinas", o["proteinas"], "g"),
             ("Grasas", "grasas", o["grasas"], "g"), ("Carbohidratos", "carbos", o["carbos"], "g")]
    md = "| Macro | Objetivo diario | Promedio del menú | Estado |\n|---|---|---|---|\n"
    md += "\n".join(f"| {n} | {obj} {u} | {p[k]:.0f} {u} | {s[k]} |" for n, k, obj, u in filas)
    st.markdown(md)
    st.caption("🟢 dentro del ±7 % (kcal) / ±12 % (macros) · 🟡 hasta ±15 % / ±25 % · 🔴 fuera de rango")


def mostrar_resultado(plan: dict, datos: dict):
    formato = datos.get("formato_menu", "Tabla semanal")
    st.success(f"✅ Menú generado: {len(plan['estructura'])} comidas/día · {plan['platos_unicos']} platos distintos · "
               f"{plan['descartadas']} recetas descartadas por tus restricciones")
    for a in plan["avisos"] + plan["objetivos"].get("avisos", []):
        st.warning(a)
    _tabla_objetivos(plan)

    if formato == "Solo lista de compra":
        _lista_compra(plan, datos)
    else:
        if formato == "Lista de recetas":
            _recetas(plan, datos, abiertas=True)
        else:
            st.markdown(plan["menu_markdown"], unsafe_allow_html=True)
        if datos.get("macros_por_comida", True):
            with st.expander("📊 Totales por día y semana"):
                md = "| Día | kcal | Proteínas | Grasas | Carbos |\n|---|---|---|---|---|\n"
                for d in DIAS:
                    t, o, s = plan["totales_dia"][d]["total"], plan["totales_dia"][d]["objetivo"], plan["totales_dia"][d]["semaforo"]
                    md += (f"| {d} | {t['calorias']:.0f}/{o['calorias']} {s['calorias']} | {t['proteinas']:.0f}/{o['proteinas']} g {s['proteinas']} "
                           f"| {t['grasas']:.0f}/{o['grasas']} g {s['grasas']} | {t['carbos']:.0f}/{o['carbos']} g {s['carbos']} |\n")
                w, ws = plan["totales_semana"], plan["semaforo_semana"]
                md += (f"| **Semana** | **{w['calorias']:.0f}** {ws['calorias']} | **{w['proteinas']:.0f} g** {ws['proteinas']} "
                       f"| **{w['grasas']:.0f} g** {ws['grasas']} | **{w['carbos']:.0f} g** {ws['carbos']} |")
                st.markdown(md)
        if datos.get("recetas_detalladas", True) and formato != "Lista de recetas":
            _recetas(plan, datos)
        if datos.get("lista_compra", True):
            _lista_compra(plan, datos)

    # --- PDF real (bug 9): bytes en session_state + download_button
    st.divider()
    c1, c2 = st.columns([1, 2])
    if c1.button("📄 Generar PDF", key="btn_pdf", use_container_width=True, type="primary" if formato == "PDF imprimible" else "secondary"):
        with st.spinner("Generando PDF…"):
            try:
                st.session_state["pdf"] = (nombre_archivo_pdf(datos), Exportador().exportar_plan_pdf(plan, datos))
            except Exception as e:  # noqa: BLE001
                st.session_state["pdf"] = None
                show_friendly_error("pdf", str(e))
    if st.session_state.get("pdf"):
        nombre, contenido = st.session_state["pdf"]
        c2.download_button("📥 Descargar PDF", contenido, file_name=nombre, mime="application/pdf", use_container_width=True)
    st.caption(DISCLAIMER)


def _recetas(plan, datos, abiertas=False):
    macros = datos.get("macros_por_comida", True)
    with st.expander("📖 Recetas del menú", expanded=abiertas):
        for r in plan["recetas_usadas"]:
            st.markdown(f"**🥘 {r['nombre']}** · {r.get('tiempo_preparacion', '?')} min · usada {r['veces']}×")
            if macros:
                st.caption(f"Por ración: {r['calorias']:.0f} kcal · P {r['proteinas']:.0f} g · G {r['grasas']:.0f} g · C {r['carbos']:.0f} g")
            st.write("**Ingredientes:** " + ", ".join(map(str, r.get("ingredientes", []))))
            st.write(r.get("instrucciones", ""))
            st.divider()


def _lista_compra(plan, datos):
    n = datos.get("personas", 1)
    with st.expander(f"🛒 Lista de la compra (para {n} persona{'s' if n != 1 else ''})", expanded=datos.get("formato_menu") == "Solo lista de compra"):
        for cat, items in plan["lista_compra"].items():
            st.markdown(f"**{cat}**")
            st.markdown("\n".join(f"- {i}" for i in items))


def main():
    st.set_page_config(page_title="Nutricionista AI", page_icon="🥗", layout="wide", initial_sidebar_state="expanded",
                       menu_items={'Get Help': None, 'Report a bug': None, 'About': None})

    # Punto 1: limpiar restos del antiguo selector de fuente
    st.session_state.pop("app_font_size", None)
    st.session_state.pop("font_selector", None)
    st.session_state.setdefault("app_theme", "Claro")
    st.session_state.setdefault("plan", None)
    st.session_state.setdefault("pdf", None)
    st.session_state.setdefault("panel_abierto", False)   # punto 5: el panel de resultados nace CERRADO

    with st.sidebar:
        st.title("⚙️ Configuración")
        st.radio("🎨 Modo", ["Claro", "Oscuro"], horizontal=True, key="app_theme", help="Cambia entre modo claro y oscuro")
        st.divider()
        usar_spoonacular = st.checkbox("Intentar Spoonacular", value=True)
    apply_theme(st.session_state["app_theme"])

    inicializar_db()
    api_recetas, ia_menu = APIRecetas(), GeneradorMenuIA()
    hay_puntos = False
    if usar_spoonacular:
        try:
            hay_puntos = _spoonacular_disponible(api_recetas)
            (st.sidebar.success if hay_puntos else st.sidebar.warning)("✅ Spoonacular disponible" if hay_puntos else "⚠️ Sin puntos en Spoonacular")
        except Exception:  # noqa: BLE001
            st.sidebar.error("❌ Error conectando con Spoonacular")

    datos = mostrar_formulario()

    if datos:
        st.session_state.update(plan=None, pdf=None, panel_abierto=True)
        with st.status("🔄 Procesando solicitud…", expanded=True) as status:
            barra = st.progress(0)

            def progreso(p, msg):
                barra.progress(p); st.write(msg)

            try:
                st.session_state["plan"] = generar_plan(datos, api_recetas, ia_menu, usar_spoonacular, hay_puntos, progreso)
                st.session_state["plan_datos"] = datos
                status.update(label="Completado", state="complete", expanded=False)
            except PlanError as e:
                status.update(label="No se pudo generar el menú", state="error")
                show_friendly_error("plan", str(e))
            except Exception as e:  # noqa: BLE001
                status.update(label="Error inesperado", state="error")
                show_friendly_error("conexion", str(e))

    # El resultado vive en session_state: sobrevive a los reruns de cualquier botón (causa raíz del bug 9)
    if st.session_state.get("plan"):
        with st.expander("📅 Tu menú semanal", expanded=st.session_state["panel_abierto"]):
            mostrar_resultado(st.session_state["plan"], st.session_state["plan_datos"])

    st.sidebar.divider()
    st.sidebar.caption("🥗 Nutricionista AI v3.0")
    st.sidebar.caption("Menús personalizados con IA")


if __name__ == "__main__":
    main()

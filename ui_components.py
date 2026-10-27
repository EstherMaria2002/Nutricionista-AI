# ui_components.py
import streamlit as st


def show_friendly_error(error_type: str, error_details: str = "", on_retry=None):
    """Muestra errores amigables según tipo y ofrece reintentar"""

    errors_config = {
        "conexion": {"title": "❌ Error de conexión", "message": "No se pudo conectar a los servidores externos.",
                     "suggestion": "Verifica tu conexión a internet y vuelve a intentarlo.", "icon": "🌐"},
        "api_keys": {"title": "🔑 Error de configuración", "message": "Faltan claves de API o son inválidas.",
                     "suggestion": "Revisa que SPOONACULAR_API_KEY y DEEPSEEK_API_KEY estén configuradas.", "icon": "🔧"},
        "timeout": {"title": "⏰ Tiempo de espera agotado", "message": "La operación tomó demasiado tiempo.",
                    "suggestion": "Intenta nuevamente o reduce el número de recetas solicitadas.", "icon": "🕒"},
        "quota": {"title": "📊 Límite de API alcanzado", "message": "No quedan puntos disponibles en Spoonacular.",
                  "suggestion": "El sistema usará DeepSeek como respaldo automáticamente.", "icon": "⚠️"},
        "invalid_data": {"title": "📝 Datos inválidos", "message": "Algunos datos ingresados no son correctos.",
                         "suggestion": "Revisa tu peso, altura y objetivos antes de continuar.", "icon": "📋"},
        "plan": {"title": "🍽️ No se pudo generar el menú", "message": "El motor de menús no pudo completar el plan.",
                 "suggestion": "Relaja algún veto o restricción, o activa Spoonacular/DeepSeek.", "icon": "🧩"},
        "pdf": {"title": "📄 No se pudo crear el PDF", "message": "Falló la generación del documento.",
                "suggestion": "Inténtalo de nuevo; si persiste, revisa que fpdf2 esté instalado (pip install fpdf2).", "icon": "🖨️"},
    }
    config = errors_config.get(error_type, errors_config["conexion"])
    with st.container():
        st.markdown(f"## {config['icon']} {config['title']}")
        st.error(f"{config['message']} {error_details}")
        st.info(f"💡 **Sugerencia:** {config['suggestion']}")
        if on_retry and st.button("🔄 Reintentar", key=f"retry_{error_type}"):
            on_retry()


def mostrar_calculos(calc: dict, titulo: str = "📐 Tus cálculos (se actualizan en tiempo real)"):
    """IMC / TMB / TDEE y objetivos diarios de kcal y macros, con unidades claras."""
    st.markdown(f"**{titulo}**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("IMC", f"{calc['imc']} kg/m²", calc["categoria_imc"], delta_color="off",
              help="Peso(kg) / altura(m)². Orientativo: no distingue músculo de grasa.")
    c2.metric("TMB", f"{calc['tmb']} kcal", help="Energía en reposo (Mifflin-St Jeor).")
    c3.metric("TDEE", f"{calc['tdee']} kcal", help="TMB × factor de actividad: lo que gastas al día.")
    c4.metric("Objetivo diario", f"{calc['kcal']} kcal", f"{calc['ajuste_kcal']:+d} kcal" if calc["ajuste_kcal"] else None,
              delta_color="off", help="TDEE ajustado por tu objetivo y ritmo, con límites de seguridad.")
    m1, m2, m3 = st.columns(3)
    m1.metric("Proteínas", f"{calc['proteinas']} g/día")
    m2.metric("Grasas", f"{calc['grasas']} g/día")
    m3.metric("Carbohidratos", f"{calc['carbos']} g/día")
    for a in calc.get("avisos", []):
        st.warning(a)


def mostrar_avisos(issues: list, paso: int = None):
    """Muestra errores (rojo) y avisos (ámbar). Si `paso` es None muestra todos."""
    for i in issues:
        if paso is not None and i["paso"] != paso:
            continue
        (st.error if i["nivel"] == "error" else st.warning)(i["msg"], icon="⛔" if i["nivel"] == "error" else "⚠️")

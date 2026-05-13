import streamlit as st

def mostrar_formulario():
    """Muestra el formulario completo y retorna los datos del usuario"""
    
    st.title("🍽️ Planificador de menús con IA")
    st.markdown("Completa tus datos para recibir un menú semanal personalizado")
    
    with st.form("datos_usuario"):
        st.subheader("📊 Datos personales")
        col1, col2 = st.columns(2)
        
        with col1:
            edad = st.number_input("Edad", min_value=1, max_value=120, value=30, step=1)
            peso = st.number_input("Peso (kg)", min_value=20.0, max_value=200.0, value=70.0, step=0.5)
            altura = st.number_input("Altura (cm)", min_value=100.0, max_value=250.0, value=170.0, step=1.0)
        
        with col2:
            sexo = st.radio("Sexo", ["Masculino", "Femenino"], horizontal=True)
            actividad = st.select_slider(
                "Nivel actividad física",
                options=["Sedentario", "Ligero", "Moderado", "Activo", "Muy activo"],
                value="Moderado"
            )
            objetivo = st.selectbox(
                "Objetivo principal",
                options=["Perder peso", "Mantener peso", "Ganar masa muscular", "Mejorar salud general"]
            )
        
        st.subheader("🥗 Preferencias alimentarias")
        col3, col4 = st.columns(2)
        
        with col3:
            restricciones = st.multiselect(
                "Restricciones alimentarias",
                options=["Ninguna", "Vegetariano", "Vegano", "Sin gluten", "Sin lactosa", 
                        "Bajo en carbohidratos", "Alto en proteínas", "Cetogénica", "Paleo"]
            )
            
            alergias = st.text_input("Alergias específicas", 
                                    placeholder="Ej: frutos secos, mariscos, huevo...")
        
        with col4:
            cocina_preferida = st.multiselect(
                "Estilo de cocina preferido",
                options=["Mediterránea", "Asiática", "Mexicana", "Italiana", 
                        "Española", "Árabe", "Sin preferencia"],
                default=["Sin preferencia"]
            )
            
            presupuesto = st.select_slider(
                "Presupuesto semanal aproximado",
                options=["Bajo", "Medio-Bajo", "Medio", "Medio-Alto", "Alto"],
                value="Medio"
            )
        
        st.subheader("📅 Organización del menú")
        col5, col6 = st.columns(2)
        
        with col5:
            comidas_dia = st.slider("Número de comidas al día", min_value=3, max_value=6, value=4)
            comidas_semana = st.slider("Platos únicos por semana (evita repeticiones)", 
                                      min_value=5, max_value=21, value=14)
        
        with col6:
            tiempo_coccion = st.select_slider(
                "Tiempo máximo de preparación (minutos)",
                options=[15, 30, 45, 60, 90, 120],
                value=45
            )
            
            incluir_snacks = st.checkbox("Incluir snacks saludables", value=True)
        
        st.subheader("🏥 Información adicional (opcional)")
        condiciones_medicas = st.text_area("Condiciones médicas relevantes",
                                          placeholder="Ej: diabetes, hipertensión, colesterol alto...")
        
        medicamentos = st.text_input("¿Tomas algún medicamento?", placeholder="Opcional")
        
        submitted = st.form_submit_button("🎯 Generar menú semanal", use_container_width=True)
        
        if submitted:
            # Validación básica
            if peso <= 0 or altura <= 0:
                st.error("❌ Peso y altura deben ser valores positivos")
                return None
            
            # Procesar alergias
            lista_alergias = [a.strip() for a in alergias.split(",") if a.strip()] if alergias else []
            
            # Asegurar que "Ninguna" no esté junto con otras restricciones
            if "Ninguna" in restricciones and len(restricciones) > 1:
                restricciones.remove("Ninguna")
            
            # Retornar todos los datos
            return {
                "edad": edad,
                "sexo": sexo,
                "peso": peso,
                "altura": altura,
                "actividad": actividad,
                "objetivo": objetivo,
                "restricciones": restricciones if restricciones else ["Ninguna"],
                "alergias": lista_alergias,
                "cocina_preferida": cocina_preferida if cocina_preferida else ["Sin preferencia"],
                "presupuesto": presupuesto,
                "comidas_dia": comidas_dia,
                "comidas_semana": comidas_semana,
                "tiempo_coccion": tiempo_coccion,
                "incluir_snacks": incluir_snacks,
                "condiciones_medicas": condiciones_medicas if condiciones_medicas else None,
                "medicamentos": medicamentos if medicamentos else None
            }
    
    return None


def calcular_imc(peso: float, altura: float) -> float:
    """Calcula el IMC del usuario"""
    altura_m = altura / 100
    return round(peso / (altura_m ** 2), 1)


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
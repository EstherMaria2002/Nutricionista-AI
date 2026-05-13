import streamlit as st
from formulario import mostrar_formulario
from apis_recetas import APIRecetas
from database import inicializar_db, obtener_recetas_db, guardar_menu_db
from balance_nutricional import calcular_balance
from generar_menu import GeneradorMenuIA
from exportador import Exportador
import socket

socket.setdefaulttimeout(30)

def main():
    st.set_page_config(page_title="Nutricionista AI", page_icon="🥗", layout="wide")
    
    # Inicializar
    inicializar_db()
    
    st.sidebar.title("⚙️ Configuración")
    usar_spoonacular = st.sidebar.checkbox("Intentar Spoonacular", value=True)
    
    # Verificar disponibilidad de Spoonacular
    api_recetas = APIRecetas()
    hay_puntos = False
    if usar_spoonacular:
        with st.sidebar:
            with st.spinner("Verificando disponibilidad..."):
                try:
                    hay_puntos = api_recetas.hay_puntos_disponibles()
                    if hay_puntos:
                        st.sidebar.success("✅ Spoonacular disponible")
                    else:
                        st.sidebar.warning("⚠️ Sin puntos en Spoonacular")
                except:
                    st.sidebar.error("❌ Error conectando con Spoonacular")
                    hay_puntos = False
    
    # Mostrar formulario
    datos = mostrar_formulario()
    
    if datos:
        ia_menu = GeneradorMenuIA()
        exportador = Exportador()
        
        recetas = []
        fallback_total = False
        
        # ---------- INTENTAR SPOONACULAR ----------
        if usar_spoonacular and hay_puntos:
            with st.spinner("🔍 Buscando recetas en Spoonacular..."):
                try:
                    keywords = " ".join(datos["cocina_preferida"] + ["healthy"])
                    dieta = datos["restricciones"][0] if datos["restricciones"] and datos["restricciones"][0] != "Ninguna" else None
                    
                    recetas_spoon = api_recetas.buscar_recetas(
                        query=keywords,
                        dieta=dieta,
                        alergias=[a for a in datos["restricciones"] if a != "Ninguna"],
                        max_recetas=40
                    )
                    recetas.extend(recetas_spoon)
                    st.info(f"📡 {len(recetas_spoon)} recetas de Spoonacular")
                except Exception as e:
                    st.warning(f"Error en Spoonacular: {e}")
        
        # ---------- INTENTAR BASE LOCAL ----------
        if len(recetas) < 20:
            with st.spinner("💾 Buscando recetas en base local..."):
                try:
                    recetas_db = obtener_recetas_db(50)
                    nombres_existentes = {r['nombre'] for r in recetas}
                    recetas_nuevas = [r for r in recetas_db if r['nombre'] not in nombres_existentes]
                    recetas.extend(recetas_nuevas)
                    if recetas_nuevas:
                        st.info(f"💾 {len(recetas_nuevas)} recetas de la base local")
                except Exception as e:
                    st.warning(f"Error en base local: {e}")
        
        # ---------- FALLBACK TOTAL: DEEPSEEK ----------
        if len(recetas) < 10:
            st.warning("⚠️ No hay suficientes recetas de fuentes externas. Usando DeepSeek para generar todo...")
            fallback_total = True
            
            with st.spinner("🤖 Generando menú completo con DeepSeek AI..."):
                try:
                    contenido_generado = ia_menu.generar_todo_con_deepseek(datos)
                    
                    if contenido_generado:
                        # Mostrar menú generado
                        st.success("✅ Menú generado completamente con DeepSeek")
                        
                        if "menu_semanal" in contenido_generado:
                            st.markdown(contenido_generado["menu_semanal"])
                        
                        # Mostrar consejos nutricionales
                        if "consejos_nutricionales" in contenido_generado:
                            with st.expander("💡 Consejos nutricionales personalizados"):
                                for consejo in contenido_generado["consejos_nutricionales"]:
                                    st.write(f"• {consejo}")
                        
                        # Mostrar lista de compra
                        if "lista_compra" in contenido_generado:
                            with st.expander("🛒 Lista de compras recomendada"):
                                for categoria, items in contenido_generado["lista_compra"].items():
                                    st.write(f"**{categoria}:**")
                                    for item in items:
                                        st.write(f"  • {item}")
                        
                        # Mostrar recetas generadas
                        if "recetas" in contenido_generado:
                            with st.expander("📖 Ver recetas generadas"):
                                for receta in contenido_generado["recetas"][:10]:
                                    st.write(f"### 🥘 {receta.get('nombre', 'Receta')}")
                                    st.write(f"**Calorías:** {receta.get('calorias', 'N/A')} kcal")
                                    st.write(f"**Proteínas:** {receta.get('proteinas', 'N/A')}g | **Grasas:** {receta.get('grasas', 'N/A')}g | **Carbos:** {receta.get('carbos', 'N/A')}g")
                                    st.write(f"**Tiempo:** {receta.get('tiempo_preparacion', 30)} minutos")
                                    st.write("**Ingredientes:**")
                                    for ing in receta.get('ingredientes', [])[:8]:
                                        st.write(f"  • {ing}")
                                    st.write("**Instrucciones:**")
                                    st.write(receta.get('instrucciones', 'No disponibles')[:300])
                                    st.divider()
                        
                        # Botón para exportar a PDF
                        if st.button("📄 Exportar menú generado a PDF"):
                            try:
                                recetas_para_pdf = contenido_generado.get("recetas", [])
                                menu_texto = contenido_generado.get("menu_semanal", "Menú generado por IA")
                                archivo = exportador.exportar_menu_pdf(menu_texto, recetas_para_pdf[:15])
                                with open(archivo, "rb") as f:
                                    st.download_button("📥 Descargar PDF", f, archivo)
                            except Exception as e:
                                st.error(f"Error al exportar: {e}")
                        
                        # Si se generó todo con DeepSeek, no continuar con el flujo normal
                        return
                    else:
                        st.error("No se pudo generar contenido con DeepSeek")
                        fallback_total = False
                        
                except Exception as e:
                    st.error(f"Error con DeepSeek: {e}")
                    fallback_total = False
        
        # ---------- FLUJO NORMAL (con recetas existentes) ----------
        if not fallback_total and recetas:
            with st.spinner("⚖️ Calculando balance nutricional..."):
                recetas_balanceadas = calcular_balance(recetas, datos)
            
            with st.spinner("🤖 Creando menú semanal..."):
                mejor_seleccion = ia_menu.seleccionar_mejor_combinacion(
                    recetas_balanceadas[:50],
                    datos["comidas_dia"],
                    datos["objetivo"]
                )
                
                if mejor_seleccion:
                    menu = ia_menu.generar_menu_semanal(
                        mejor_seleccion,
                        datos["comidas_dia"],
                        datos
                    )
                    
                    # Guardar en base de datos
                    ids_recetas = [r.get('id_api', f"temp_{i}") for i, r in enumerate(mejor_seleccion)]
                    guardar_menu_db(datos, menu, ids_recetas)
                    
                    st.success("✅ ¡Menú generado con éxito!")
                    st.markdown(menu)
                    
                    # Botones
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("📄 Exportar menú a PDF"):
                            try:
                                archivo = exportador.exportar_menu_pdf(menu, mejor_seleccion[:15])
                                with open(archivo, "rb") as f:
                                    st.download_button("📥 Descargar PDF", f, archivo)
                            except Exception as e:
                                st.error(f"Error: {e}")
                    
                    with col2:
                        if st.button("📖 Ver recetas"):
                            for receta in mejor_seleccion[:10]:
                                with st.expander(f"🥘 {receta.get('nombre', 'Receta')}"):
                                    st.write(f"**Calorías:** {receta.get('calorias', 'N/A')} kcal")
                                    st.write(f"**Proteínas:** {receta.get('proteinas', 'N/A')}g")
                                    st.write(f"**Ingredientes:** {', '.join(receta.get('ingredientes', [])[:8])}")
                else:
                    st.error("No se pudo generar el menú")
        elif not fallback_total:
            st.warning("No se encontraron recetas. Asegúrate de tener internet o recetas locales.")
            st.info("💡 Si no hay puntos de Spoonacular, el sistema usará DeepSeek automáticamente.")

if __name__ == "__main__":
    main()
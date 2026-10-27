<<<<<<< HEAD
# Nutricionista AI v3

## Arranque
    pip install -r requirements.txt
    export DEEPSEEK_API_KEY=...  SPOONACULAR_API_KEY=...   # opcionales: sin ellas usa BD local + respaldo
    streamlit run main.py        ·   pytest -q

## Flujo del motor
formulario → payload → `filtros.construir_prohibidos` → Spoonacular + BD local → **filtro duro** →
(si faltan recetas) IA con prompt de prohibiciones + **validador** (3 reintentos) → respaldo filtrado →
`planificador.construir_menu` (n comidas, macros) → `validador_ia.validar_plan` → PDF/UI.

## Contrato con la IA (extendido, compatible)
Se mantienen los campos antiguos. **Consume la IA/motor**: patrones y `restricciones`, `sin_*`, `alergias`,
`intolerancias`, `vetados` (prohibiciones absolutas), `ingredientes_obligatorios`/`aprovechar`/`favoritos`,
`cocina_preferida`, `picante`, `dulzor`, `equipamiento`, `habilidad_cocina`, `tiempo_coccion`, `tiempo_por_comida`,
`comidas_dia` + `nombres_comidas`, `objetivo`, kcal/macros objetivo, `condiciones_lista`, `medicamentos_lista`.
**Solo UX / logística**: nombre, supermercado, frecuencia_compra, formato_menu, lista_compra, recetas_detalladas,
macros_por_comida, nombre_plan, idioma/unidades, consentimiento_rgpd.
Los campos condicionales que no aplican NO se envían.

**Respuesta de la IA** (array JSON): `nombre, racion, ingredientes[], instrucciones, tiempo_preparacion,
calorias, proteinas, grasas, carbos, momentos[]`. Validación (`validador_ia.py`): estructura; macros numéricos,
≥0, kcal 20–2500 y coherentes con 4P+4C+9G (±35 %); sin ingredientes prohibidos; `momentos` ⊂ nombres de comida;
cobertura ≥2 recetas por comida. Fallo → reintento (con motivos en el prompt) → respaldo filtrado → mensaje.

## Cálculos (nutricion.py)
Mifflin-St Jeor × actividad; ajuste = ritmo·1100 kcal/día (máx. −25 %/+20 %); suelos 1500/1200/1350 kcal;
sin déficit con embarazo/lactancia, TCA, IMC<18,5 o <18 años. Proteína 1,2–2,0 g/kg (+0,4 alto en proteínas,
0,8 renal), grasa 28 % (mín. 20 %), carbos = resto; keto ≈8 %, bajo en carbos 25 %, diabetes ≤40 %.

## Limitaciones conocidas
* Filtro heurístico: no sustituye a un etiquetado oficial de alérgenos. Términos libres del usuario se traducen
  al inglés solo si están en `filtros.TRADUCCIONES` (para Spoonacular); en BD local/IA funcionan siempre.
* Borrador = fichero local `borrador_formulario.json` (Streamlit no tiene localStorage); válido para uso de 1 usuario.
=======
🥗 Nutricionista AI - Planificador de Menús con IA

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=Streamlit&logoColor=white)](https://streamlit.io)

Sistema automatizado para nutricionistas que genera menús semanales personalizados usando IA.

✨ Características
- 📝 Formulario completo con múltiples parámetros
- 🔍 Búsqueda en Spoonacular (API gratuita)
- 🧠 Balance nutricional optimizado
- 🤖 Fallback completo a DeepSeek AI cuando no hay recetas externas
- 💾 Base de datos local SQLite
- 📄 Exportación a PDF

🚀 Instalación
Requisitos previos
- Python 3.8 o superior
- Cuentas API gratuitas:
  - [Spoonacular](https://spoonacular.com/food-api) (150 puntos/día gratis)
  - [DeepSeek](https://platform.deepseek.com/) (muy económico)
 
Pasos
1. Clonar el repositorio:
git clone https://github.com/TU-USUARIO/nutricionista-ai.git
cd nutricionista-ai

2. Crear entorno virtual:
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

3. Instalar dependencias:
pip install -r requirements.txt

4. Configurar variables:
cp .env.example .env
# Editar .env con tus claves API

5.Ejecutar:
streamlit run main.py
>>>>>>> d36f220e20039c78f2acc624d13a4362c4aaed0d

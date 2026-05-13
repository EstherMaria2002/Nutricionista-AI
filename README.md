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

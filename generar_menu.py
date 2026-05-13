import requests
import os
import json
from typing import List, Dict

class GeneradorMenuIA:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")
    
    def generar_con_deepseek(self, prompt: str, temperatura: float = 0.7) -> str:
        """Llama a la API de DeepSeek"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Eres un nutricionista experto que crea menús saludables y personalizados."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperatura,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"❌ Error con DeepSeek: {e}")
            return None
    
    def generar_todo_con_deepseek(self, datos_usuario: Dict) -> Dict:
        """
        Genera menú completo, recetas y nutrientes solo con DeepSeek
        cuando no hay Spoonacular ni recetas locales
        """
        
        prompt = f"""
        Eres un nutricionista experto. Necesito que generes un plan nutricional COMPLETO para un cliente.
        
        **Datos del cliente:**
        - Edad: {datos_usuario.get('edad', 30)} años
        - Sexo: {datos_usuario.get('sexo', 'No especificado')}
        - Peso: {datos_usuario.get('peso', 70)} kg
        - Altura: {datos_usuario.get('altura', 170)} cm
        - Actividad física: {datos_usuario.get('actividad', 'Moderado')}
        - Objetivo: {datos_usuario.get('objetivo', 'Mejorar salud general')}
        - Restricciones alimentarias: {', '.join(datos_usuario.get('restricciones', ['Ninguna']))}
        - Alergias: {', '.join(datos_usuario.get('alergias', ['Ninguna'])) if datos_usuario.get('alergias') else 'Ninguna'}
        - Comidas por día: {datos_usuario.get('comidas_dia', 4)}
        - Estilo de cocina preferido: {', '.join(datos_usuario.get('cocina_preferida', ['Sin preferencia']))}
        
        **Genera los siguientes elementos en formato JSON:**
        
        1. **menu_semanal**: Tabla markdown con 7 días y las comidas según el número de comidas por día
        2. **recetas**: Lista de {datos_usuario.get('comidas_semana', 14)} recetas únicas (una por cada plato de la semana)
           Cada receta debe tener: nombre, ingredientes (lista), instrucciones paso a paso, 
           tiempo_preparacion (minutos), calorias, proteinas(g), grasas(g), carbos(g)
        3. **consejos_nutricionales**: Lista de 5 consejos personalizados
        4. **lista_compra**: Lista de ingredientes agrupada por categorías (verduras, proteinas, granos, etc.)
        
        **Formato exacto de respuesta (SOLO JSON, sin texto extra):**
        {{
            "menu_semanal": "tabla markdown aquí",
            "recetas": [
                {{
                    "nombre": "Nombre receta",
                    "ingredientes": ["ing1", "ing2"],
                    "instrucciones": "paso a paso",
                    "tiempo_preparacion": 30,
                    "calorias": 400,
                    "proteinas": 25,
                    "grasas": 15,
                    "carbos": 45
                }}
            ],
            "consejos_nutricionales": ["consejo1", "consejo2"],
            "lista_compra": {{
                "Verduras": ["item1", "item2"],
                "Proteínas": ["item1", "item2"],
                "Granos": ["item1", "item2"],
                "Otros": ["item1", "item2"]
            }}
        }}
        
        Asegúrate de que las recetas sean realistas, saludables y respeten las restricciones del cliente.
        """
        
        respuesta = self.generar_con_deepseek(prompt, temperatura=0.7)
        
        if respuesta:
            try:
                # Extraer JSON de la respuesta
                import re
                json_match = re.search(r'\{.*\}', respuesta, re.DOTALL)
                if json_match:
                    datos_generados = json.loads(json_match.group())
                    return datos_generados
            except json.JSONDecodeError as e:
                print(f"Error parseando JSON: {e}")
                return self._fallback_completo(datos_usuario)
        
        return self._fallback_completo(datos_usuario)
    
    def generar_recetas_desde_cero(self, datos_usuario: Dict, cantidad: int = 14) -> List[Dict]:
        """Genera recetas completas desde cero con DeepSeek"""
        
        prompt = f"""
        Genera {cantidad} recetas saludables y completas para una persona con:
        - Objetivo: {datos_usuario.get('objetivo', 'Salud general')}
        - Restricciones: {', '.join(datos_usuario.get('restricciones', ['Ninguna']))}
        - Alergias: {', '.join(datos_usuario.get('alergias', ['Ninguna']))}
        - Estilo de cocina: {', '.join(datos_usuario.get('cocina_preferida', ['Variada']))}
        
        Cada receta debe tener:
        - nombre atractivo
        - lista de ingredientes (con cantidades aproximadas)
        - instrucciones paso a paso
        - tiempo de preparación (minutos)
        - información nutricional: calorías, proteínas(g), grasas(g), carbohidratos(g)
        
        Devuelve SOLO un array JSON como este:
        [
            {{
                "nombre": "Ejemplo",
                "ingredientes": ["ing1", "ing2"],
                "instrucciones": "Paso 1... Paso 2...",
                "tiempo_preparacion": 30,
                "calorias": 400,
                "proteinas": 25,
                "grasas": 15,
                "carbos": 45
            }}
        ]
        """
        
        respuesta = self.generar_con_deepseek(prompt, temperatura=0.8)
        
        if respuesta:
            try:
                import re
                json_match = re.search(r'\[.*\]', respuesta, re.DOTALL)
                if json_match:
                    recetas = json.loads(json_match.group())
                    return recetas
            except:
                pass
        
        return self._recetas_fallback()
    
    def seleccionar_mejor_combinacion(self, recetas: List[Dict], 
                                      comidas_por_dia: int, 
                                      objetivo_usuario: str) -> List[Dict]:
        """Selecciona la mejor combinación de recetas (si hay recetas)"""
        
        if not recetas:
            return []
        
        total_comidas = comidas_por_dia * 7
        
        prompt = f"""
        Selecciona {total_comidas} recetas de esta lista para un menú semanal balanceado.
        Objetivo: {objetivo_usuario}
        Comidas por día: {comidas_por_dia}
        
        Lista de recetas disponibles:
        {json.dumps([r['nombre'] for r in recetas[:40]], ensure_ascii=False)}
        
        Devuelve SOLO un array JSON con los nombres seleccionados:
        ["Receta 1", "Receta 2", ...]
        """
        
        respuesta = self.generar_con_deepseek(prompt, temperatura=0.5)
        
        if respuesta:
            try:
                import re
                json_match = re.search(r'\[.*\]', respuesta, re.DOTALL)
                if json_match:
                    nombres_recetas = json.loads(json_match.group())
                    seleccionadas = [r for r in recetas if r['nombre'] in nombres_recetas]
                    if seleccionadas:
                        return seleccionadas
            except:
                pass
        
        return recetas[:total_comidas] if len(recetas) >= total_comidas else recetas
    
    def generar_menu_semanal(self, recetas_seleccionadas: List[Dict], 
                            comidas_por_dia: int,
                            datos_usuario: Dict) -> str:
        """Genera un menú semanal en formato markdown"""
        
        if not recetas_seleccionadas:
            return self._menu_fallback()
        
        prompt = f"""
        Crea un menú semanal para {comidas_por_dia} comidas al día usando estas recetas:
        
        {json.dumps([r['nombre'] for r in recetas_seleccionadas[:30]], ensure_ascii=False)}
        
        **Datos del usuario:**
        - Edad: {datos_usuario.get('edad', 30)}
        - Objetivo: {datos_usuario.get('objetivo', 'Salud general')}
        - Restricciones: {datos_usuario.get('restricciones', [])}
        
        **Formato requerido (tabla markdown):**
        
        | Día | Desayuno | Almuerzo | Cena | Snacks (si aplica) |
        |-----|----------|----------|------|---------------------|
        | Lunes | [Receta] | [Receta] | [Receta] | [Receta opcional] |
        | Martes | ... | ... | ... | ... |
        
        Además, al final incluye:
        1. **Consejos nutricionales** personalizados
        2. **Lista de compras** agrupada por categorías
        
        Sé práctico y específico.
        """
        
        respuesta = self.generar_con_deepseek(prompt, temperatura=0.7)
        
        if respuesta:
            return respuesta
        
        return self._menu_fallback()
    
    def _recetas_fallback(self) -> List[Dict]:
        """Recetas de respaldo si DeepSeek falla"""
        return [
            {
                "nombre": "Ensalada de quinoa y vegetales",
                "ingredientes": ["quinoa", "pepino", "tomate cherry", "aguacate", "limón", "aceite de oliva"],
                "instrucciones": "1. Cocer la quinoa según instrucciones. 2. Cortar los vegetales. 3. Mezclar todo. 4. Aliñar con limón y aceite.",
                "tiempo_preparacion": 20,
                "calorias": 350,
                "proteinas": 12,
                "grasas": 14,
                "carbos": 45
            },
            {
                "nombre": "Pollo a la plancha con verduras",
                "ingredientes": ["pechuga de pollo", "brócoli", "zanahoria", "calabacín", "ajo", "aceite de oliva"],
                "instrucciones": "1. Sazonar el pollo. 2. Cocinar el pollo a la plancha. 3. Saltear las verduras. 4. Servir junto.",
                "tiempo_preparacion": 25,
                "calorias": 420,
                "proteinas": 38,
                "grasas": 12,
                "carbos": 32
            },
            {
                "nombre": "Tortilla de espinacas",
                "ingredientes": ["huevos", "espinacas frescas", "cebolla", "sal", "pimienta"],
                "instrucciones": "1. Lavar y picar espinacas. 2. Batir huevos. 3. Mezclar con espinacas. 4. Cocinar en sartén antiadherente.",
                "tiempo_preparacion": 15,
                "calorias": 280,
                "proteinas": 18,
                "grasas": 18,
                "carbos": 8
            }
        ]
    
    def _menu_fallback(self) -> str:
        """Menú de respaldo si todo falla"""
        return """
        ### Menú Semanal Sugerido
        
        | Día | Desayuno | Almuerzo | Cena |
        |-----|----------|----------|------|
        | Lunes | Avena con frutas y nueces | Ensalada de quinoa con vegetales | Pollo a la plancha con brócoli |
        | Martes | Yogur griego con granola | Lentejas estofadas con arroz integral | Pescado al horno con verduras |
        | Miércoles | Tostada integral con aguacate | Ensalada de garbanzos | Tortilla de espinacas |
        | Jueves | Batido de proteínas con frutos rojos | Crema de calabaza y jengibre | Pechuga de pavo con quinoa |
        | Viernes | Huevos revueltos con espinacas | Pasta integral con verduras | Salmón al vapor con espárragos |
        | Sábado | Panqueques de avena | Ensalada de pollo | Tofu salteado con vegetables |
        | Domingo | Fruta fresca con frutos secos | Menestra de verduras | Revuelto de setas con huevo |
        
        **Consejos nutricionales:**
        - Bebe al menos 2 litros de agua al día
        - Incluye vegetales en todas las comidas
        - Controla las porciones de carbohidratos
        - Prioriza proteínas magras
        - Reduce el consumo de azúcares procesados
        
        **Lista de compras básica:**
        - **Verduras:** brócoli, espinacas, calabaza, espárragos, setas
        - **Proteínas:** pollo, pescado, huevos, tofu, lentejas
        - **Granos:** quinoa, arroz integral, avena, pasta integral
        - **Frutas:** frutos rojos, aguacate, frutas de temporada
        """
    
    def _fallback_completo(self, datos_usuario: Dict) -> Dict:
        """Respuesta completa de emergencia"""
        return {
            "menu_semanal": self._menu_fallback(),
            "recetas": self._recetas_fallback(),
            "consejos_nutricionales": [
                "Mantén una hidratación adecuada durante todo el día",
                "Prioriza alimentos enteros sobre procesados",
                "Incluye proteína en cada comida principal",
                "Consume al menos 5 porciones de frutas y verduras al día",
                "Planifica tus comidas con anticipación"
            ],
            "lista_compra": {
                "Verduras": ["brócoli", "espinacas", "calabacín", "tomate", "cebolla"],
                "Proteínas": ["pollo", "huevos", "lentejas", "garbanzos", "pescado"],
                "Granos": ["quinoa", "arroz integral", "avena", "pasta integral"],
                "Frutas": ["manzana", "plátano", "frutos rojos", "naranja"],
                "Otros": ["aceite de oliva", "nueces", "especias"]
            }
        }
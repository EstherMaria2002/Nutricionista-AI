import requests
import os
from typing import List, Dict
from database import guardar_receta_db

class APIRecetas:
    def __init__(self):
        self.spoonacular_key = os.getenv("SPOONACULAR_API_KEY")
        self.base_url = "https://api.spoonacular.com"
    
    def buscar_recetas(self, query: str, dieta: str = None, 
                       alergias: List[str] = None, max_recetas: int = 30) -> List[Dict]:
        """Busca recetas en Spoonacular con todos los filtros"""
        url = f"{self.base_url}/recipes/complexSearch"
        
        params = {
            "apiKey": self.spoonacular_key,
            "query": query,
            "number": max_recetas,
            "addRecipeInformation": True,
            "addRecipeNutrition": True,
            "sort": "healthiness",
            "sortDirection": "desc"
        }
        
        if dieta and dieta != "Ninguna":
            dieta_map = {
                "Vegetariano": "vegetarian",
                "Vegano": "vegan",
                "Sin gluten": "gluten free",
                "Cetogénica": "ketogenic",
                "Paleo": "paleo"
            }
            if dieta in dieta_map:
                params["diet"] = dieta_map[dieta]
        
        if alergias and "Ninguna" not in alergias:
            alergias_map = {
                "Frutos secos": "tree nut free",
                "Lácteos": "dairy free",
                "Huevo": "egg free",
                "Gluten": "gluten free",
                "Soja": "soy free",
                "Mariscos": "shellfish free"
            }
            excluir = [alergias_map[a] for a in alergias if a in alergias_map]
            if excluir:
                params["excludeIngredients"] = ",".join(alergias)
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            recetas = []
            puntos_restantes = int(response.headers.get('X-Api-Request-Quota-Remaining', 0))
            print(f"📊 Puntos Spoonacular restantes: {puntos_restantes}")
            
            for recipe in data.get("results", []):
                nutrientes = recipe.get('nutrition', {}).get('nutrients', [])
                
                receta = {
                    "id_api": f"spoonacular_{recipe['id']}",
                    "nombre": recipe['title'],
                    "ingredientes": [ing['name'] for ing in recipe.get('extendedIngredients', [])],
                    "instrucciones": self._limpiar_instrucciones(recipe.get('instructions', '')),
                    "url_receta": recipe.get('sourceUrl', ''),
                    "calorias": self._obtener_nutriente(nutrientes, 'Calories'),
                    "proteinas": self._obtener_nutriente(nutrientes, 'Protein'),
                    "grasas": self._obtener_nutriente(nutrientes, 'Fat'),
                    "carbos": self._obtener_nutriente(nutrientes, 'Carbohydrates'),
                    "fibra": self._obtener_nutriente(nutrientes, 'Fiber'),
                    "azucar": self._obtener_nutriente(nutrientes, 'Sugar'),
                    "tiempo_preparacion": recipe.get('readyInMinutes', 30),
                    "url_imagen": recipe.get('image', ''),
                    "puntuacion_salud": recipe.get('healthScore', 0),
                    "fuente": "Spoonacular",
                    "vegana": recipe.get('vegan', False),
                    "vegetariana": recipe.get('vegetarian', False),
                    "sin_gluten": recipe.get('glutenFree', False)
                }
                recetas.append(receta)
                guardar_receta_db(receta)
            
            return recetas
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error con Spoonacular: {e}")
            return []
    
    def verificar_puntos_restantes(self) -> int:
        """Verifica cuántos puntos quedan en Spoonacular"""
        url = f"{self.base_url}/recipes/complexSearch"
        params = {
            "apiKey": self.spoonacular_key,
            "number": 1
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            return int(response.headers.get('X-Api-Request-Quota-Remaining', 0))
        except:
            return 0
    
    def hay_puntos_disponibles(self) -> bool:
        """Retorna True si hay al menos 10 puntos disponibles"""
        try:
            puntos = self.verificar_puntos_restantes()
            return puntos > 10
        except:
            return False
    
    def _obtener_nutriente(self, nutrientes: List[Dict], nombre: str) -> float:
        for n in nutrientes:
            if n['name'] == nombre:
                return n['amount']
        return 0
    
    def _limpiar_instrucciones(self, html_instrucciones: str) -> str:
        if not html_instrucciones:
            return "Instrucciones no disponibles en formato texto."
        
        import re
        texto_limpio = re.sub(r'<[^>]+>', ' ', html_instrucciones)
        texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
        return texto_limpio
import requests
import os
import re
from typing import List, Dict, Optional
from database import guardar_receta_db

# Valores de "dieta" que entiende Spoonacular
DIETA_MAP = {
    "Vegetariano": "vegetarian", "Vegano": "vegan", "Pescetariano": "pescetarian",
    "Sin gluten": "gluten free", "Cetogénica": "ketogenic", "Paleo": "paleo",
}


class APIRecetas:
    def __init__(self):
        self.spoonacular_key = os.getenv("SPOONACULAR_API_KEY")
        self.base_url = "https://api.spoonacular.com"

    def buscar_recetas(self, query: str, dieta: str = None, alergias: List[str] = None,
                       max_recetas: int = 30, *, dietas: Optional[List[str]] = None,
                       intolerancias_api: Optional[List[str]] = None,
                       excluir_ingredientes: Optional[List[str]] = None,
                       max_minutos: Optional[int] = None) -> List[Dict]:
        """
        Busca recetas en Spoonacular.

        CORRECCIÓN bug 7: antes se calculaba `excluir` pero se enviaba `alergias` (en español y sin
        mapear) en excludeIngredients, y main.py pasaba las *restricciones* como alergias. Ahora:
          · `intolerancias_api`  -> parámetro `intolerances` (valores oficiales de Spoonacular)
          · `excluir_ingredientes` -> `excludeIngredients` (en inglés)
          · `dietas` (o `dieta`)  -> `diet`
        Aun así, los resultados se vuelven a filtrar localmente con filtros.receta_segura.
        """
        url = f"{self.base_url}/recipes/complexSearch"
        params = {
            "apiKey": self.spoonacular_key, "query": query, "number": max_recetas,
            "addRecipeInformation": True, "addRecipeNutrition": True,
            "fillIngredients": True, "instructionsRequired": True,
            "sort": "healthiness", "sortDirection": "desc",
        }
        lista_dietas = list(dietas or [])
        if dieta and dieta != "Ninguna":
            lista_dietas.append(dieta)
        mapeadas = []
        for d in lista_dietas:
            if d in DIETA_MAP and DIETA_MAP[d] not in mapeadas:
                mapeadas.append(DIETA_MAP[d])
        if mapeadas:
            params["diet"] = ",".join(mapeadas)
        if intolerancias_api:
            params["intolerances"] = ",".join(intolerancias_api)
        if excluir_ingredientes:
            params["excludeIngredients"] = ",".join(excluir_ingredientes)
        if max_minutos:
            params["maxReadyTime"] = max_minutos

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            recetas = []
            puntos_restantes = int(float(response.headers.get('X-Api-Request-Quota-Remaining', 0)))
            print(f"📊 Puntos Spoonacular restantes: {puntos_restantes}")

            for recipe in data.get("results", []):
                nutrientes = recipe.get('nutrition', {}).get('nutrients', [])
                ingredientes = [ing['name'] for ing in recipe.get('extendedIngredients', []) if ing.get('name')]
                if not ingredientes:  # fallback: ingredientes de la sección nutrition
                    ingredientes = [i['name'] for i in recipe.get('nutrition', {}).get('ingredients', []) if i.get('name')]
                receta = {
                    "id_api": f"spoonacular_{recipe['id']}",
                    "nombre": recipe['title'],
                    "ingredientes": ingredientes,
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
                    "sin_gluten": recipe.get('glutenFree', False),
                    "momentos": [],
                }
                recetas.append(receta)
                guardar_receta_db(receta)
            return recetas

        except requests.exceptions.RequestException as e:
            print(f"❌ Error con Spoonacular: {e}")
            return []

    def verificar_puntos_restantes(self) -> int:
        """Verifica cuántos puntos quedan en Spoonacular (consume ~1 punto)."""
        url = f"{self.base_url}/recipes/complexSearch"
        params = {"apiKey": self.spoonacular_key, "number": 1}
        try:
            response = requests.get(url, params=params, timeout=10)
            return int(float(response.headers.get('X-Api-Request-Quota-Remaining', 0)))
        except Exception:
            return 0

    def hay_puntos_disponibles(self) -> bool:
        """Retorna True si hay al menos 10 puntos disponibles"""
        try:
            return self.verificar_puntos_restantes() > 10
        except Exception:
            return False

    def _obtener_nutriente(self, nutrientes: List[Dict], nombre: str) -> float:
        for n in nutrientes:
            if n['name'] == nombre:
                return n['amount']
        return 0

    def _limpiar_instrucciones(self, html_instrucciones: str) -> str:
        if not html_instrucciones:
            return "Instrucciones no disponibles en formato texto."
        texto_limpio = re.sub(r'<[^>]+>', ' ', html_instrucciones)
        return re.sub(r'\s+', ' ', texto_limpio).strip()

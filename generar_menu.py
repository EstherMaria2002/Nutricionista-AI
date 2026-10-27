import requests
import os
import json
import re
from typing import List, Dict, Optional, Tuple

from filtros import construir_prohibidos, resumen_para_prompt, Prohibido
from nutricion import estructura_comidas
from recetas_respaldo import recetas_respaldo
from validador_ia import validar_lista_recetas, momentos_sin_cobertura


class GeneradorMenuIA:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")

    # ------------------------------------------------------------------ llamada HTTP (sin cambios)
    def generar_con_deepseek(self, prompt: str, temperatura: float = 0.7) -> Optional[str]:
        """Llama a la API de DeepSeek"""
        if not self.api_key:
            print("❌ DEEPSEEK_API_KEY no configurada")
            return None
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Eres un nutricionista experto que crea menús saludables y personalizados. "
                                              "Respondes SOLO con JSON válido cuando se te pide JSON."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperatura,
            "max_tokens": 4000,
        }
        try:
            response = requests.post(f"{self.api_url}/chat/completions", headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"❌ Error con DeepSeek: {e}")
            return None

    # ------------------------------------------------------------------ prompt + parseo
    def _prompt_recetas(self, datos: Dict, prohibidos: List[Prohibido], cantidad: int, comidas: List[str],
                        comidas_sin_cobertura: List[str], objetivos: Optional[Dict], motivos_previos: str) -> str:
        kcal_c = f"~{objetivos['kcal'] // len(comidas)} kcal de media por comida" if objetivos else ""
        prohib = "\n".join(f"  - {x}" for x in resumen_para_prompt(prohibidos)) or "  - (ninguna)"
        cocina = ", ".join(datos.get("cocina_preferida") or ["variada"])
        extra = ""
        if comidas_sin_cobertura:
            extra += f"\nHAZ ESPECIAL FOCO en recetas para: {', '.join(comidas_sin_cobertura)}."
        if motivos_previos:
            extra += f"\nTu respuesta anterior fue RECHAZADA por estos motivos, evítalos:\n{motivos_previos}"
        return f"""Genera {cantidad} recetas saludables, realistas y distintas entre sí.

PERFIL
- Objetivo: {datos.get('objetivo', 'Salud general')} · {kcal_c}
- Patrón alimentario: {', '.join(datos.get('restricciones') or ['Ninguna'])}
- Cocina preferida: {cocina}
- Tiempo máximo de preparación: {datos.get('tiempo_coccion', 45)} min · Nivel de cocina: {datos.get('habilidad_cocina', 'intermedio')}
- Equipamiento: {', '.join(datos.get('equipamiento') or ['básico'])}
- Ingredientes que SÍ o SÍ deben aparecer en alguna receta: {', '.join(datos.get('ingredientes_obligatorios') or ['ninguno'])}
- Picante: {datos.get('picante', 'sin preferencia')} · Dulzor: {datos.get('dulzor', 'sin preferencia')}

PROHIBICIONES ABSOLUTAS (ningún ingrediente, salsa, caldo, aderezo o derivado de esta lista; si dudas, no lo uses):
{prohib}

El menú tiene {len(comidas)} comidas al día: {', '.join(comidas)}.
Para cada receta indica en "momentos" en cuáles de esas comidas encaja (nombres EXACTOS).{extra}

Devuelve SOLO un array JSON (sin texto ni markdown) con objetos de esta forma. TODOS los campos son obligatorios,
los macros son NÚMEROS por ración y deben ser coherentes (kcal ≈ 4·proteínas + 4·carbos + 9·grasas):
[
  {{"nombre": "…", "racion": "1 plato (350 g)",
    "ingredientes": ["200 g pechuga de pollo", "…"],
    "instrucciones": "Paso 1… Paso 2…", "tiempo_preparacion": 30,
    "calorias": 450, "proteinas": 35, "grasas": 15, "carbos": 40,
    "momentos": ["Comida", "Cena"]}}
]"""

    @staticmethod
    def _extraer_json(texto: str):
        texto = re.sub(r"```(?:json)?", "", texto or "").strip()
        for intento in (texto, *(m.group() for m in (re.search(r"\[.*\]", texto, re.DOTALL),
                                                      re.search(r"\{.*\}", texto, re.DOTALL)) if m)):
            try:
                return json.loads(intento)
            except json.JSONDecodeError:
                continue
        return []

    # ------------------------------------------------------------------ recetas IA validadas
    def generar_recetas_validadas(self, datos: Dict, prohibidos: List[Prohibido], estructura: List[Dict],
                                  cantidad: int = 14, max_intentos: int = 3,
                                  objetivos: Optional[Dict] = None) -> Tuple[List[Dict], List]:
        """
        Pide recetas a DeepSeek y SOLO acepta las que pasan validador_ia.validar_receta
        (estructura, macros numéricos y coherentes, momentos válidos, sin ingredientes prohibidos).
        Reintenta hasta `max_intentos` incluyendo los motivos del rechazo en el prompt.
        -> (recetas válidas, [(nombre, [errores])] rechazadas)
        """
        comidas = [e["nombre"] for e in estructura]
        validas: Dict[str, Dict] = {}
        rechazos: List = []
        motivos = ""
        for intento in range(max_intentos):
            faltan = cantidad - len(validas)
            sin_cob = momentos_sin_cobertura(list(validas.values()), comidas)
            if faltan <= 0 and not sin_cob:
                break
            prompt = self._prompt_recetas(datos, prohibidos, max(faltan, 4), comidas, sin_cob, objetivos, motivos)
            respuesta = self.generar_con_deepseek(prompt, temperatura=0.8 if intento == 0 else 0.5)
            if not respuesta:
                continue
            ok, rech = validar_lista_recetas(self._extraer_json(respuesta), prohibidos, comidas)
            for r in ok:
                validas.setdefault(r["id_api"], r)
            rechazos.extend(rech)
            motivos = "\n".join(f"  - {n}: {'; '.join(e)}" for n, e in rech[:6])
        return list(validas.values()), rechazos

    def generar_recetas_desde_cero(self, datos_usuario: Dict, cantidad: int = 14) -> List[Dict]:
        """Compatibilidad: misma firma que antes, ahora validada y filtrada."""
        recetas, _ = self.generar_recetas_validadas(
            datos_usuario, construir_prohibidos(datos_usuario), estructura_comidas(datos_usuario), cantidad)
        return recetas

    def _recetas_fallback(self) -> List[Dict]:
        """Recetas de respaldo si DeepSeek falla (siempre se filtran antes de usarse)."""
        return recetas_respaldo()

import numpy as np
from typing import List, Dict

def calcular_balance(recetas: List[Dict], objetivos_usuario: Dict) -> List[Dict]:
    """Puntúa cada receta según balance nutricional y objetivos"""
    
    if not recetas:
        return []
    
    tmb = 10 * objetivos_usuario["peso"] + 6.25 * objetivos_usuario["altura"] - 5 * objetivos_usuario["edad"]
    if objetivos_usuario["sexo"] == "Masculino":
        tmb += 5
    else:
        tmb -= 161
    
    factores_actividad = {
        "Sedentario": 1.2,
        "Ligero": 1.375,
        "Moderado": 1.55,
        "Activo": 1.725,
        "Muy activo": 1.9
    }
    
    calorias_diarias = tmb * factores_actividad.get(objetivos_usuario["actividad"], 1.5)
    
    ajustes = {
        "Perder peso": 0.85,
        "Mantener peso": 1.0,
        "Ganar masa muscular": 1.15,
        "Mejorar salud general": 1.0
    }
    calorias_diarias *= ajustes.get(objetivos_usuario["objetivo"], 1.0)
    
    if objetivos_usuario["objetivo"] == "Ganar masa muscular":
        proteinas_ideal_porc = 0.30
        grasas_ideal_porc = 0.25
        carbos_ideal_porc = 0.45
    elif objetivos_usuario["objetivo"] == "Perder peso":
        proteinas_ideal_porc = 0.35
        grasas_ideal_porc = 0.25
        carbos_ideal_porc = 0.40
    else:
        proteinas_ideal_porc = 0.25
        grasas_ideal_porc = 0.30
        carbos_ideal_porc = 0.45
    
    comidas_por_dia = objetivos_usuario.get("comidas_dia", 4)
    calorias_por_comida = calorias_diarias / comidas_por_dia
    
    proteinas_por_comida = (calorias_diarias * proteinas_ideal_porc / 4) / comidas_por_dia
    grasas_por_comida = (calorias_diarias * grasas_ideal_porc / 9) / comidas_por_dia
    carbos_por_comida = (calorias_diarias * carbos_ideal_porc / 4) / comidas_por_dia
    
    for receta in recetas:
        score = 0
        
        diff_calorias = abs(receta.get("calorias", 300) - calorias_por_comida)
        score_calorias = max(0, 1 - (diff_calorias / max(calorias_por_comida, 1)))
        score += score_calorias * 0.3
        
        diff_proteinas = abs(receta.get("proteinas", 15) - proteinas_por_comida)
        score_proteinas = max(0, 1 - (diff_proteinas / max(proteinas_por_comida, 1)))
        score += score_proteinas * 0.25
        
        diff_grasas = abs(receta.get("grasas", 15) - grasas_por_comida)
        score_grasas = max(0, 1 - (diff_grasas / max(grasas_por_comida, 1)))
        score += score_grasas * 0.20
        
        diff_carbos = abs(receta.get("carbos", 40) - carbos_por_comida)
        score_carbos = max(0, 1 - (diff_carbos / max(carbos_por_comida, 1)))
        score += score_carbos * 0.15
        
        score_salud = receta.get("puntuacion_salud", 50) / 100
        score += score_salud * 0.10
        
        receta["balance_score"] = round(score * 100, 2)
        receta["calorias_objetivo"] = round(calorias_por_comida)
    
    return sorted(recetas, key=lambda x: x["balance_score"], reverse=True)
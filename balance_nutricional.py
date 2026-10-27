from typing import List, Dict
from nutricion import objetivos_diarios


def calcular_balance(recetas: List[Dict], objetivos_usuario: Dict) -> List[Dict]:
    """
    Puntúa cada receta (0-100) por cercanía a la comida media del día y por puntuación de salud.
    Los objetivos diarios ahora vienen de nutricion.objetivos_diarios (Mifflin-St Jeor + actividad +
    objetivo + ritmo + patrón/condiciones) en vez de la fórmula duplicada que había aquí.
    """
    if not recetas:
        return []
    obj = objetivos_diarios(objetivos_usuario)
    n = max(1, int(objetivos_usuario.get("comidas_dia", 4)))
    kcal_c, prot_c, gras_c, carb_c = obj["kcal"] / n, obj["proteinas"] / n, obj["grasas"] / n, obj["carbos"] / n

    def cercania(valor, objetivo):
        return max(0.0, 1 - abs(valor - objetivo) / max(objetivo, 1))

    for r in recetas:
        score = (cercania(r.get("calorias") or 300, kcal_c) * 0.30
                 + cercania(r.get("proteinas") or 15, prot_c) * 0.25
                 + cercania(r.get("grasas") or 15, gras_c) * 0.20
                 + cercania(r.get("carbos") or 40, carb_c) * 0.15
                 + (r.get("puntuacion_salud") or 50) / 100 * 0.10)
        r["balance_score"] = round(score * 100, 2)
        r["calorias_objetivo"] = round(kcal_c)
    return sorted(recetas, key=lambda x: x["balance_score"], reverse=True)

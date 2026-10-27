"""
Validación de la salida de la IA (bugs 6, 7, 8) y del plan final.

Una receta de la IA se ACEPTA solo si:
  1. tiene nombre, ingredientes (lista de textos no vacía) e instrucciones;
  2. calorias, proteinas, grasas y carbos son números finitos >= 0 (strings numéricos se convierten);
  3. los macros son coherentes con las kcal (|kcal − (4P+4C+9G)| ≤ 35 %) y plausibles (20–2.500 kcal);
  4. NINGÚN ingrediente (ni el nombre) coincide con alérgenos, intolerancias, vetados o patrón dietético;
  5. los `momentos` declarados (si los hay) son nombres de comida válidos para el menú del usuario.
Si falla, se rechaza y el generador reintenta (con los motivos en el prompt) y, al final, cae a respaldo.
"""
import hashlib
import math
from typing import Dict, List, Optional, Tuple

from filtros import Prohibido, normalizar, receta_segura

CAMPOS_MACRO = ("calorias", "proteinas", "grasas", "carbos")


def _num(valor) -> Optional[float]:
    if isinstance(valor, bool):
        return None
    try:
        x = float(str(valor).replace(",", ".").strip()) if isinstance(valor, str) else float(valor)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and x >= 0 else None


def validar_receta(r, prohibidos: List[Prohibido], momentos_validos: Optional[List[str]] = None
                   ) -> Tuple[Optional[dict], List[str]]:
    """-> (receta normalizada | None, errores)."""
    if not isinstance(r, dict):
        return None, ["no es un objeto JSON"]
    errores: List[str] = []
    nombre = str(r.get("nombre", "")).strip()
    if not nombre:
        errores.append("falta 'nombre'")
    ings = r.get("ingredientes")
    if not isinstance(ings, list) or not ings or not all(isinstance(i, str) and i.strip() for i in ings):
        errores.append("'ingredientes' debe ser una lista de textos no vacía")
        ings = []
    ins = r.get("instrucciones")
    if isinstance(ins, list):
        ins = " ".join(str(x) for x in ins)
    if not isinstance(ins, str) or not ins.strip():
        errores.append("faltan 'instrucciones'")

    macros = {}
    for c in CAMPOS_MACRO:
        v = _num(r.get(c))
        if v is None:
            errores.append(f"'{c}' falta o no es numérico")
        else:
            macros[c] = v
    if len(macros) == 4:
        k, p, g, cb = (macros[c] for c in CAMPOS_MACRO)
        if not 20 <= k <= 2500:
            errores.append(f"calorías fuera de rango plausible ({k:.0f})")
        calc = 4 * p + 4 * cb + 9 * g
        if calc > 0 and abs(k - calc) / calc > 0.35:
            errores.append(f"macros incoherentes con las kcal ({k:.0f} vs {calc:.0f} calculadas)")

    if not errores:
        seguro, motivos = receta_segura({"nombre": nombre, "ingredientes": ings}, prohibidos)
        if not seguro:
            errores.extend(f"ingrediente prohibido: {m}" for m in motivos)

    momentos = r.get("momentos") or []
    if momentos_validos and momentos:
        if not isinstance(momentos, list):
            errores.append("'momentos' debe ser una lista")
        else:
            validos = {normalizar(m): m for m in momentos_validos}
            fallo = [m for m in momentos if normalizar(m) not in validos]
            if fallo:
                errores.append(f"momentos no válidos: {fallo}")
            momentos = [validos[normalizar(m)] for m in momentos if normalizar(m) in validos]

    if errores:
        return None, errores
    tiempo = _num(r.get("tiempo_preparacion"))
    return {
        "id_api": "ia_" + hashlib.md5(normalizar(nombre).encode()).hexdigest()[:10],
        "nombre": nombre, "ingredientes": [i.strip() for i in ings], "instrucciones": ins.strip(),
        "tiempo_preparacion": int(tiempo) if tiempo else 30,
        "calorias": macros["calorias"], "proteinas": macros["proteinas"],
        "grasas": macros["grasas"], "carbos": macros["carbos"],
        "racion": str(r.get("racion", "1 ración")), "momentos": momentos,
        "fuente": "DeepSeek", "url_imagen": "",
    }, []


def validar_lista_recetas(lista, prohibidos, momentos_validos=None):
    """-> (validas, rechazadas[(nombre, errores)])"""
    validas, rechazadas, vistos = [], [], set()
    if isinstance(lista, dict):
        lista = lista.get("recetas", [])
    for r in lista if isinstance(lista, list) else []:
        ok, err = validar_receta(r, prohibidos, momentos_validos)
        if ok and ok["id_api"] not in vistos:
            vistos.add(ok["id_api"]); validas.append(ok)
        elif not ok:
            rechazadas.append((r.get("nombre", "?") if isinstance(r, dict) else "?", err))
    return validas, rechazadas


def momentos_sin_cobertura(recetas: List[dict], nombres_comidas: List[str], minimo: int = 2) -> List[str]:
    """Comidas del día que no tienen al menos `minimo` recetas etiquetadas para ellas."""
    return [n for n in nombres_comidas
            if sum(1 for r in recetas if n in (r.get("momentos") or [])) < minimo]


def validar_plan(plan: dict, nombres_comidas: List[str], prohibidos: List[Prohibido]) -> List[str]:
    """Red de seguridad final: 7 días, todas las comidas, macros presentes y nada prohibido."""
    errores = []
    menu = plan.get("menu", {})
    if len(menu) != 7:
        errores.append(f"el menú tiene {len(menu)} días en lugar de 7")
    for dia, comidas in menu.items():
        faltan = [n for n in nombres_comidas if n not in comidas]
        if faltan:
            errores.append(f"{dia}: faltan comidas {faltan}")
        for nombre, slot in comidas.items():
            if slot.get("fuera"):
                continue
            if any(_num(slot.get(c)) is None for c in CAMPOS_MACRO):
                errores.append(f"{dia}/{nombre}: macros ausentes o no numéricos")
            ok, motivos = receta_segura(slot, prohibidos)
            if not ok:
                errores.extend(f"{dia}/{nombre}: {m}" for m in motivos)
    return errores

"""
Orquestación de la generación del plan:
  Spoonacular (si hay puntos) + BD local  ->  FILTRO DURO  ->  (si faltan) IA validada  ->  respaldo filtrado
  ->  planificador (n comidas, macros)  ->  validar_plan  ->  guardar.
"""
import math
from collections import Counter
from typing import Callable, Dict, Optional

from apis_recetas import APIRecetas
from balance_nutricional import calcular_balance
from database import guardar_menu_db, guardar_receta_db, marcar_recetas_usadas, obtener_recetas_db
from filtros import construir_prohibidos, filtrar_recetas, parametros_spoonacular
from generar_menu import GeneradorMenuIA
from nutricion import estructura_comidas, objetivos_diarios
from planificador import construir_menu, menu_a_markdown
from validador_ia import validar_plan

COCINA_EN = {"Mediterránea": "mediterranean", "Asiática": "asian", "Mexicana": "mexican", "Italiana": "italian",
             "Española": "spanish", "Árabe": "middle eastern", "India": "indian", "Nórdica": "nordic",
             "Americana": "american"}


class PlanError(Exception):
    pass


def _filtro_macro_patron(recetas, datos):
    patrones = [p for p in datos.get("restricciones", [])]
    tope = 20 if "Cetogénica" in patrones else (40 if "Bajo en carbohidratos" in patrones else None)
    return [r for r in recetas if (r.get("carbos") or 0) <= tope] if tope else recetas


def generar_plan(datos: Dict, api: APIRecetas, ia: GeneradorMenuIA, usar_spoonacular: bool, hay_puntos: bool,
                 progreso: Optional[Callable[[int, str], None]] = None, semilla: Optional[int] = None) -> Dict:
    def avanzar(p, msg):
        if progreso:
            progreso(p, msg)

    prohibidos = construir_prohibidos(datos)
    objetivos = objetivos_diarios(datos)
    estructura = estructura_comidas(datos)
    n_comidas_semana = int(datos.get("comidas_semana", 14))
    necesarias = max(10, min(n_comidas_semana, 14))

    pool: Dict[str, dict] = {}
    descartadas = 0
    notas = []

    def incorporar(lista):
        nonlocal descartadas
        lista = _filtro_macro_patron(lista, datos)
        seguras, malas = filtrar_recetas(lista, prohibidos)
        descartadas += malas
        for r in seguras:
            pool.setdefault(r["nombre"], r)

    # 1) Spoonacular
    if usar_spoonacular and hay_puntos:
        avanzar(10, "🔍 Buscando recetas en Spoonacular…")
        try:
            intol, excluir = parametros_spoonacular(prohibidos)
            query = " ".join([COCINA_EN[c] for c in datos.get("cocina_preferida", []) if c in COCINA_EN] + ["healthy"])
            dietas = [r for r in datos.get("restricciones", []) if r != "Ninguna"]
            if datos.get("sin_gluten"):
                dietas.append("Sin gluten")
            incorporar(api.buscar_recetas(query=query, dietas=dietas, intolerancias_api=intol,
                                          excluir_ingredientes=excluir, max_recetas=40,
                                          max_minutos=datos.get("tiempo_coccion")))
        except Exception as e:  # noqa: BLE001
            notas.append(f"Spoonacular no respondió ({e}).")

    # 2) BD local
    avanzar(30, "💾 Buscando en la base local…")
    incorporar(obtener_recetas_db(1000))

    # 3) IA validada si faltan recetas
    if len(pool) < necesarias:
        avanzar(50, "🤖 Generando recetas con IA (validadas)…")
        nuevas, rechazos = ia.generar_recetas_validadas(datos, prohibidos, estructura, cantidad=necesarias - len(pool) + 6,
                                                         objetivos=objetivos)
        for r in nuevas:
            guardar_receta_db(r)
        incorporar(nuevas)
        if rechazos:
            notas.append(f"{len(rechazos)} receta(s) de la IA fueron rechazadas por la validación (macros o ingredientes).")

    # 4) Respaldo filtrado
    if len(pool) < 6:
        avanzar(60, "🛟 Usando recetas de respaldo seguras…")
        incorporar(ia._recetas_fallback())

    if len(pool) < 3:
        raise PlanError(
            "Con tus alergias, vetos y restricciones no hay suficientes recetas seguras "
            f"({len(pool)} disponibles, {descartadas} descartadas). Prueba a relajar algún veto o activar la IA/Spoonacular.")

    avanzar(70, "⚖️ Calculando balance nutricional…")
    recetas = calcular_balance(list(pool.values()), datos)

    avanzar(85, f"📅 Construyendo menú de {len(estructura)} comidas al día…")
    plan = construir_menu(recetas, datos, objetivos, estructura, prohibidos, semilla)

    errores = validar_plan(plan, [e["nombre"] for e in estructura], prohibidos)
    if errores:
        raise PlanError("El plan no superó la validación final: " + "; ".join(errores[:5]))

    plan["avisos"] = notas + plan["avisos"]
    plan["descartadas"] = descartadas
    plan["fuentes"] = dict(Counter(r.get("fuente", "?") for r in plan["recetas_usadas"]))
    plan["menu_markdown"] = menu_a_markdown(plan, bool(datos.get("macros_por_comida", True)))
    plan["datos"] = datos

    ids = [r["id_api"] for r in plan["recetas_usadas"] if not str(r.get("id_api", "")).startswith(("respaldo_", "extra_"))]
    try:
        guardar_menu_db(datos, plan["menu_markdown"], ids)
        marcar_recetas_usadas(ids)
    except Exception as e:  # noqa: BLE001  (no bloquear al usuario por un fallo de persistencia)
        plan["avisos"].append(f"No se pudo guardar el menú en la base de datos: {e}")
    avanzar(100, "✅ Menú generado")
    return plan

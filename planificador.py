"""
Planificador determinista del menú semanal (bugs 6 y 8).

Construye {día: {comida: receta}} a partir de las recetas YA filtradas, respetando:
  * nº y nombres de comidas del día (estructura_comidas),
  * kcal/proteína objetivo de cada comida (escalando la ración en pasos de 0,25 entre ×0,5 y ×1,75),
  * tiempo máximo (global y por comida), nº de platos únicos/semana, sobras y batch cooking,
  * ingredientes obligatorios / a aprovechar / favoritos,
  * comidas fuera de casa, postres y bebidas opcionales.
Devuelve además totales diarios y semanales con semáforo frente a los objetivos.
"""
import html
import random
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from filtros import Prohibido, normalizar, receta_segura, tokens, _contiene

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
ORDEN_FUERA = ["Sábado", "Domingo", "Viernes", "Miércoles", "Lunes", "Jueves", "Martes"]
MACROS = ("calorias", "proteinas", "grasas", "carbos")

EXTRAS_POSTRE = [
    {"nombre": "Yogur natural con fruta", "ingredientes": ["yogur natural", "fruta de temporada"],
     "calorias": 130, "proteinas": 7, "grasas": 4, "carbos": 17},
    {"nombre": "Fruta de temporada", "ingredientes": ["fruta de temporada"],
     "calorias": 80, "proteinas": 1, "grasas": 0.3, "carbos": 19},
]
EXTRAS_BEBIDA = [
    {"nombre": "Infusión sin azúcar", "ingredientes": ["infusión"],
     "calorias": 0, "proteinas": 0, "grasas": 0, "carbos": 0},
]

CATEGORIAS_COMPRA = {
    "Verduras y hortalizas": "tomate cebolla ajo pimiento zanahoria calabacin calabaza brocoli espinaca lechuga pepino berenjena "
                             "champinon seta puerro coliflor esparrago apio remolacha repollo rucula col judia verde patata boniato "
                             "onion garlic pepper carrot zucchini broccoli spinach lettuce cucumber potato mushroom",
    "Frutas": "manzana pera platano fresa naranja limon lima kiwi mango pina granada arandano frutos rojos uva fruta "
              "apple banana strawberry orange lemon lime pineapple berry",
    "Carnes, pescados y huevos": "pollo pavo ternera cerdo jamon chorizo panceta carne salmon atun merluza bacalao gamba huevo "
                                 "pescado chicken turkey beef pork fish shrimp egg",
    "Lácteos y alternativas": "leche queso yogur mantequilla requeson nata milk cheese yogurt butter tofu tempeh seitan",
    "Cereales, legumbres y frutos secos": "arroz pasta pan avena quinoa cuscus lenteja garbanzo alubia guisante edamame harina "
                                         "tortilla almendra nuez cacahuete semilla fideo rice bread oat lentil chickpea bean nut seed",
}
_CAT_TOK = {c: {tokens(w)[0] for w in ws.split()} for c, ws in CATEGORIAS_COMPRA.items()}


def _f(x, d=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _id(r: dict) -> str:
    return str(r.get("id_api") or normalizar(r.get("nombre", "")))


def _cumple(r: dict, terminos: List[tuple]) -> List[tuple]:
    seq = tokens(" ".join([r.get("nombre", "")] + [str(i) for i in r.get("ingredientes", [])]))
    return [t for t in terminos if _contiene(seq, t)]


def _slots_fuera(datos: dict, nombres: List[str]) -> set:
    veces = int(datos.get("comer_fuera_veces") or 0)
    tipos = [t for t in (datos.get("comer_fuera_tipos") or []) if t in nombres]
    if veces <= 0 or not tipos:
        return set()
    out = set()
    for i in range(veces):
        out.add((ORDEN_FUERA[(i // len(tipos)) % 7], tipos[i % len(tipos)]))
    return out


def _tiempo_max(datos: dict, comida: str) -> int:
    por_comida = datos.get("tiempo_por_comida") or {}
    return int(por_comida.get(comida) or datos.get("tiempo_coccion") or 120)


def _slot_vacio(motivo="Comes fuera de casa"):
    return {"nombre": motivo, "fuera": True, "ingredientes": [], "calorias": 0, "proteinas": 0, "grasas": 0, "carbos": 0}


def _slot_desde(r: dict, factor: float) -> dict:
    s = {k: v for k, v in r.items() if k not in MACROS}
    for m in MACROS:
        s[m] = round(_f(r.get(m)) * factor, 1)
    s["calorias"] = round(s["calorias"])
    s["factor"] = factor
    return s


def _elegir_extra(catalogo, prohibidos):
    for e in catalogo:
        if receta_segura(e, prohibidos)[0]:
            return dict(e, id_api="extra_" + normalizar(e["nombre"]).replace(" ", "_"), factor=1.0, fuente="Catálogo")
    return None


def estado_semaforo(valor: float, objetivo: float, kcal: bool = True) -> str:
    if objetivo <= 0:
        return "⚪"
    d = abs(valor - objetivo) / objetivo
    verde, amarillo = (0.07, 0.15) if kcal else (0.12, 0.25)
    return "🟢" if d <= verde else ("🟡" if d <= amarillo else "🔴")


def construir_menu(recetas: List[dict], datos: dict, objetivos: dict, estructura: List[dict],
                   prohibidos: List[Prohibido], semilla: Optional[int] = None) -> Dict:
    rnd = random.Random(semilla)
    avisos: List[str] = []
    nombres = [e["nombre"] for e in estructura]
    n_unicos = int(datos.get("comidas_semana", 14))
    sobras, batch = bool(datos.get("repetir_sobras")), bool(datos.get("batch_cooking"))
    obligatorios = [tokens(x) for x in datos.get("ingredientes_obligatorios") or []]
    aprovechar = [tokens(x) for x in datos.get("ingredientes_aprovechar") or []]
    favoritos = [tokens(x) for x in datos.get("alimentos_favoritos") or []]
    fuera = _slots_fuera(datos, nombres)
    if not recetas:
        raise ValueError("No hay recetas seguras con las que construir el menú.")

    extras_cfg = []
    if datos.get("incluir_postres"):
        e = _elegir_extra(EXTRAS_POSTRE, prohibidos)
        if e: extras_cfg.append(("Postre", e))
    if datos.get("incluir_bebidas"):
        e = _elegir_extra(EXTRAS_BEBIDA, prohibidos)
        if e: extras_cfg.append(("Bebida", e))
    kcal_extras = sum(e["calorias"] for _, e in extras_cfg)

    usados: Dict[str, List[int]] = defaultdict(list)
    por_id: Dict[str, dict] = {}
    cubiertos: set = set()
    relajado = False
    menu: Dict[str, Dict[str, dict]] = {}

    for di, dia in enumerate(DIAS):
        menu[dia] = {}
        hoy = set()
        for sl in estructura:
            nombre = sl["nombre"]
            if (dia, nombre) in fuera:
                menu[dia][nombre] = _slot_vacio()
                continue
            obj_k = max(1.0, (objetivos["kcal"] - kcal_extras) * sl["fraccion"])
            obj_p = objetivos["proteinas"] * sl["fraccion"]
            cand = [r for r in recetas if _id(r) not in hoy and _f(r.get("tiempo_preparacion"), 30) <= _tiempo_max(datos, nombre)]
            if not cand:
                cand = [r for r in recetas if _id(r) not in hoy]
                relajado = True
            if len(usados) >= n_unicos:
                pend = [t for t in obligatorios if t not in cubiertos]
                restringido = [r for r in cand if _id(r) in usados or (pend and _cumple(r, pend))]
                cand = restringido or cand

            mejor, mejor_s, mejor_f = None, -9e9, 1.0
            for r in cand:
                kc = max(_f(r.get("calorias")), 1.0)
                f = round(min(1.75, max(0.5, obj_k / kc)) * 4) / 4
                fit = 1 - min(1.0, abs(kc * f - obj_k) / obj_k)
                pfit = 1 - min(1.0, abs(_f(r.get("proteinas")) * f - obj_p) / max(obj_p, 1))
                s = 0.55 * fit + 0.25 * pfit - 0.12 * abs(f - 1)
                mom = r.get("momentos")
                if mom and nombre not in mom:
                    s -= 0.5
                rid = _id(r)
                veces = len(usados[rid]) if rid in usados else 0
                s -= (0.10 if batch else 0.35) * veces
                if not sobras and not batch and rid in usados and any(di - d <= 2 for d in usados[rid]):
                    s -= 0.4
                s += 0.35 * len(_cumple(r, [t for t in obligatorios if t not in cubiertos]))
                s += 0.12 * len(_cumple(r, aprovechar)) + 0.08 * len(_cumple(r, favoritos))
                s += 0.10 * _f(r.get("balance_score")) / 100 + rnd.random() * 0.02
                if s > mejor_s:
                    mejor, mejor_s, mejor_f = r, s, f
            rid = _id(mejor)
            usados[rid].append(di); hoy.add(rid); por_id[rid] = mejor
            cubiertos.update(_cumple(mejor, obligatorios))
            menu[dia][nombre] = _slot_desde(mejor, mejor_f)

        for etiqueta, e in extras_cfg:
            if etiqueta == "Postre" and menu[dia].get("Comida", {}).get("fuera"):
                continue
            menu[dia][etiqueta] = _slot_desde(e, 1.0)

    if relajado:
        avisos.append("Algunas comidas superan tu tiempo máximo de preparación porque no había suficientes recetas rápidas y seguras.")
    sin_cubrir = [t for t in obligatorios if t not in cubiertos]
    if sin_cubrir:
        avisos.append("No se encontró ninguna receta segura (y dentro de tu tiempo máximo) que incluya: " + ", ".join(" ".join(t) for t in sin_cubrir) + ".")
    if len(usados) < min(n_unicos, 5):
        avisos.append(f"Solo hay {len(usados)} platos distintos disponibles con tus restricciones; habrá repeticiones.")
    if fuera:
        avisos.append("Los días con comidas fuera de casa no suman esas tomas; sus objetivos se reducen proporcionalmente.")

    plan = {
        "menu": menu, "estructura": estructura,
        "columnas": nombres + [e for e, _ in extras_cfg],
        "avisos": avisos, "objetivos": objetivos,
    }
    plan.update(_totales(menu, objetivos, estructura, fuera))
    plan["recetas_usadas"] = [dict(por_id[i], veces=len(v)) for i, v in sorted(usados.items(), key=lambda kv: -len(kv[1]))]
    plan["lista_compra"] = lista_compra(plan["recetas_usadas"], usados)
    plan["platos_unicos"] = len(usados)
    return plan


def _totales(menu, objetivos, estructura, fuera) -> Dict:
    frac = {e["nombre"]: e["fraccion"] for e in estructura}
    por_dia, sem = {}, Counter()
    for dia, comidas in menu.items():
        t = Counter()
        for nombre, s in comidas.items():
            if s.get("fuera"):
                continue
            for m in MACROS:
                t[m] += _f(s.get(m))
        pct = sum(frac[n] for n in frac if (dia, n) not in fuera) or 1.0
        obj = {"calorias": objetivos["kcal"] * pct, "proteinas": objetivos["proteinas"] * pct,
               "grasas": objetivos["grasas"] * pct, "carbos": objetivos["carbos"] * pct}
        por_dia[dia] = {
            "total": {m: round(t[m], 1) for m in MACROS}, "objetivo": {m: round(v) for m, v in obj.items()},
            "semaforo": {m: estado_semaforo(t[m], obj[m], m == "calorias") for m in MACROS},
        }
        sem.update(t)
    semana = {m: round(sem[m], 1) for m in MACROS}
    prom = {m: round(semana[m] / 7, 1) for m in MACROS}
    obj_sem = {"calorias": objetivos["kcal"] * 7, "proteinas": objetivos["proteinas"] * 7,
               "grasas": objetivos["grasas"] * 7, "carbos": objetivos["carbos"] * 7}
    return {
        "totales_dia": por_dia, "totales_semana": semana, "promedio_diario": prom,
        "objetivo_semana": {m: round(v) for m, v in obj_sem.items()},
        "semaforo_semana": {m: estado_semaforo(semana[m], sum(por_dia[d]["objetivo"][m] for d in DIAS), m == "calorias")
                            for m in MACROS},
    }


def lista_compra(recetas_usadas: List[dict], usados: Dict[str, List[int]]) -> Dict[str, List[str]]:
    cuenta: Counter = Counter()
    nombre_vis: Dict[str, str] = {}
    for r in recetas_usadas:
        for ing in r.get("ingredientes", []):
            k = normalizar(ing)
            nombre_vis.setdefault(k, ing.strip())
            cuenta[k] += len(usados.get(_id(r), [])) or 1
    out: Dict[str, List[str]] = {c: [] for c in CATEGORIAS_COMPRA}
    out["Despensa y otros"] = []
    for k, n in sorted(cuenta.items()):
        toks = set(tokens(k))
        cat = next((c for c, vocab in _CAT_TOK.items() if toks & vocab), "Despensa y otros")
        out[cat].append(f"{nombre_vis[k]} (en {n} comida{'s' if n != 1 else ''})")
    return {c: v for c, v in out.items() if v}


def menu_a_markdown(plan: dict, macros: bool = True) -> str:
    cols = plan["columnas"]
    cab = "| Día | " + " | ".join(cols) + (" | kcal |" if macros else " |")
    sep = "|" + "---|" * (len(cols) + 1 + (1 if macros else 0))
    filas = []
    for dia in DIAS:
        celdas = []
        for c in cols:
            s = plan["menu"][dia].get(c)
            if not s:
                celdas.append("—")
            elif s.get("fuera"):
                celdas.append("🍽️ Fuera de casa")
            else:
                x = f" ×{s['factor']:g}" if s.get("factor", 1) != 1 else ""
                m = f"<br>*{s['calorias']:.0f} kcal · P{s['proteinas']:.0f} G{s['grasas']:.0f} C{s['carbos']:.0f}*" if macros else ""
                nom = html.escape(str(s["nombre"]).replace("|", "/"))
                celdas.append(f"{nom}{x}{m}")
        fin = f" {plan['totales_dia'][dia]['total']['calorias']:.0f} |" if macros else ""
        filas.append(f"| **{dia}** | " + " | ".join(celdas) + " |" + fin)
    return "\n".join([cab, sep] + filas)

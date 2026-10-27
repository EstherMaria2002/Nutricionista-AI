"""pytest -q  ·  Demuestra bugs 6, 7, 8, 9 (sin red ni claves de API)."""
import sqlite3, json
import pytest
from filtros import construir_prohibidos, ingrediente_prohibido, receta_segura, filtrar_recetas
from nutricion import objetivos_diarios, estructura_comidas
from validador_ia import validar_receta, validar_plan
from planificador import construir_menu
from recetas_respaldo import recetas_respaldo
from exportador import Exportador

BASE = dict(edad=30, sexo="Masculino", peso=70, altura=170, actividad="Moderado", objetivo="Mantener peso",
            restricciones=["Ninguna"], comidas_dia=4, comidas_semana=10, tiempo_coccion=60, cocina_preferida=["Sin preferencia"])


def locales():
    c = sqlite3.connect("recetas.db")
    return [dict(nombre=n, ingredientes=json.loads(i), calorias=k, proteinas=p, grasas=g, carbos=cb, instrucciones="x",
                 tiempo_preparacion=t, id_api=a, fuente="Local")
            for a, n, i, k, p, g, cb, t in c.execute("select id_api,nombre,ingredientes,calorias,proteinas,grasas,carbos,tiempo_preparacion from recetas")]


@pytest.mark.parametrize("ing,esperado", [("gambas", True), ("panga", False), ("pan integral", False), ("salsa de ostras", True),
                                           ("leche de coco", False), ("mejillones en escabeche", True)])
def test_marisco_por_termino(ing, esperado):
    p = construir_prohibidos({"alergias": ["marisco"]})
    assert bool(ingrediente_prohibido(ing, p)) == esperado


def test_pan_no_es_substring():
    p = construir_prohibidos({"alergias": ["gluten"]})
    assert ingrediente_prohibido("pan integral", p) and not ingrediente_prohibido("panga", p) and not ingrediente_prohibido("harina de arroz", p)


def test_lacteos_excepciones():
    p = construir_prohibidos({"alergias": ["lactosa"]})
    assert ingrediente_prohibido("queso feta", p)
    assert not ingrediente_prohibido("leche de avena", p) and not ingrediente_prohibido("yogur de soja", p)


@pytest.mark.parametrize("datos,prohibidas", [
    ({"alergias": ["marisco"]}, ["gamba", "ostra", "mejill"]),
    ({"restricciones": ["Vegano"]}, ["pollo", "ternera", "salm", "huevo", "queso", "yogur", "leche entera", "jam", "atún", "gambas"]),
    ({"alergias": ["Espinacas"], "vetados": ["tahini"]}, ["espinaca", "tahini"]),
])
def test_bd_local_nunca_contiene_prohibidos(datos, prohibidas):
    p = construir_prohibidos(datos)
    seguras, _ = filtrar_recetas(locales(), p)
    assert seguras
    texto = " ".join(i.lower() for r in seguras for i in r["ingredientes"] + [r["nombre"]])
    import re
    texto = texto.replace("leche de", "").replace("yogur de soja", "")
    assert not [w for w in prohibidas if re.search(r"\b" + w, texto)]   # por inicio de palabra: "repollo" != "pollo"


def test_receta_sin_ingredientes_no_verificable():
    assert not receta_segura({"nombre": "x", "ingredientes": []}, construir_prohibidos({"alergias": ["huevo"]}))[0]


def test_validador_rechaza_macros_y_alergenos():
    p = construir_prohibidos({"alergias": ["marisco"]})
    ok = dict(nombre="Pollo", ingredientes=["pollo"], instrucciones="a", calorias=400, proteinas=40, grasas=10, carbos=37)
    assert validar_receta(ok, p)[0]
    assert not validar_receta({**ok, "calorias": "mucho"}, p)[0]
    assert not validar_receta({k: v for k, v in ok.items() if k != "grasas"}, p)[0]
    assert not validar_receta({**ok, "calorias": 1500}, p)[0]                       # incoherente
    assert not validar_receta({**ok, "ingredientes": ["200 g gambas"]}, p)[0]       # alérgeno


@pytest.mark.parametrize("n", [3, 4, 5, 6])
def test_numero_de_comidas(n):
    d = {**BASE, "comidas_dia": n, "alergias": ["marisco"], "incluir_postres": True}
    p = construir_prohibidos(d); est = estructura_comidas(d); o = objetivos_diarios(d)
    seguras, _ = filtrar_recetas(locales(), p)
    plan = construir_menu(seguras, d, o, est, p, semilla=1)
    assert len(est) == n and abs(sum(e["fraccion"] for e in est) - 1) < 1e-9
    assert all(len([c for c in dia if c in [e["nombre"] for e in est]]) == n for dia in plan["menu"].values())
    assert validar_plan(plan, [e["nombre"] for e in est], p) == []


def test_macros_y_totales_reproducibles():
    o = objetivos_diarios({**BASE, "objetivo": "Perder peso", "ritmo": "Moderado (0,5 kg/sem)"})
    assert o["tmb"] == 1618 and o["tdee"] == 2507 and o["kcal"] == 1960
    assert abs(4 * o["proteinas"] + 4 * o["carbos"] + 9 * o["grasas"] - o["kcal"]) < 15


def test_sin_deficit_en_embarazo_y_tca():
    base = {**BASE, "sexo": "Femenino", "objetivo": "Perder peso", "ritmo": "Rápido (0,75 kg/sem)"}
    assert objetivos_diarios({**base, "embarazo_lactancia": True})["ajuste_kcal"] == 0
    assert objetivos_diarios({**base, "tca": "Sí"})["ajuste_kcal"] == 0


def test_pdf_real():
    d = {**BASE, "alergias": ["marisco"]}
    p = construir_prohibidos(d); est = estructura_comidas(d)
    plan = construir_menu(recetas_respaldo(), d, objetivos_diarios(d), est, p, semilla=1)
    plan["objetivos"] = objetivos_diarios(d)
    for fmt in ("Tabla semanal", "Lista de recetas", "Solo lista de compra"):
        b = Exportador().exportar_plan_pdf(plan, {**d, "formato_menu": fmt})
        assert b[:5] == b"%PDF-" and len(b) > 2000

"""Recetas de respaldo (último recurso, siempre pasan por el filtro duro). Macros por ración."""
_D = ["Desayuno", "Media mañana", "Merienda", "Recena"]
_C = ["Comida", "Cena"]
_T = ["Desayuno", "Comida", "Cena"]

# (nombre, ingredientes, instrucciones, minutos, kcal, proteínas, grasas, carbos, momentos)
_DATOS = [
    ("Avena cremosa con plátano y canela", ["copos de avena", "plátano", "canela", "semillas de chía", "leche de avena"],
     "Calienta la bebida con la avena 5 min, añade el plátano en rodajas, la canela y las semillas.", 10, 350, 12, 9, 55, _D),
    ("Tostada de aguacate y tomate", ["pan integral", "aguacate", "tomate", "aceite de oliva"],
     "Tuesta el pan, aplasta el aguacate, extiende y cubre con tomate y un hilo de aceite.", 8, 350, 9, 18, 38, _D),
    ("Yogur natural con frutos rojos y nueces", ["yogur natural", "frutos rojos", "nueces"],
     "Sirve el yogur con los frutos rojos y las nueces troceadas.", 5, 245, 12, 12, 22, _D),
    ("Tortilla de espinacas y champiñones", ["huevos", "espinacas", "champiñones", "cebolla", "aceite de oliva"],
     "Saltea las verduras, bate los huevos, mezcla y cuaja en sartén antiadherente.", 15, 285, 20, 20, 6, _T),
    ("Ensalada templada de quinoa y verduras", ["quinoa", "pepino", "tomate cherry", "aguacate", "limón", "aceite de oliva"],
     "Cuece la quinoa, trocea las verduras, mezcla y aliña con limón y aceite.", 20, 385, 12, 16, 48, _C),
    ("Pollo a la plancha con brócoli y arroz integral", ["pechuga de pollo", "brócoli", "arroz integral", "ajo", "aceite de oliva"],
     "Cuece el arroz, cocina el pollo a la plancha y el brócoli al vapor; sirve junto.", 30, 460, 42, 11, 48, _C),
    ("Lentejas estofadas con verduras", ["lentejas", "zanahoria", "cebolla", "puerro", "pimentón dulce", "aceite de oliva"],
     "Sofríe las verduras, añade las lentejas, el pimentón y agua; cuece 30-35 min.", 45, 400, 22, 9, 58, _C),
    ("Salmón al horno con patata y espárragos", ["salmón", "patata", "espárragos", "limón", "aceite de oliva"],
     "Hornea la patata en rodajas 15 min, añade salmón y espárragos 15 min más con limón.", 35, 480, 36, 22, 34, _C),
    ("Garbanzos salteados con espinacas", ["garbanzos", "espinacas", "ajo", "comino", "pimentón dulce", "aceite de oliva"],
     "Dora el ajo, añade garbanzos y especias, incorpora las espinacas hasta que se reduzcan.", 20, 355, 17, 14, 40, _C),
    ("Pasta integral con verduras y atún", ["pasta integral", "atún", "calabacín", "tomate triturado", "cebolla", "aceite de oliva"],
     "Cuece la pasta, sofríe cebolla y calabacín, añade tomate y atún y mezcla.", 25, 500, 30, 12, 68, ["Comida"]),
    ("Salteado de tofu con verduras y arroz", ["tofu", "arroz integral", "pimiento rojo", "zanahoria", "brócoli", "salsa de soja", "jengibre"],
     "Dora el tofu, añade verduras y jengibre, sazona con soja y sirve sobre el arroz.", 25, 440, 24, 15, 52, _C),
    ("Crema de calabaza y zanahoria", ["calabaza", "zanahoria", "cebolla", "jengibre", "aceite de oliva"],
     "Cuece las verduras con agua, tritura con el jengibre y un hilo de aceite.", 30, 205, 5, 8, 28, ["Cena", "Merienda", "Recena"]),
    ("Pavo con calabacín y arroz integral", ["pechuga de pavo", "calabacín", "arroz integral", "cebolla", "aceite de oliva"],
     "Saltea el pavo en tiras con cebolla y calabacín; sirve con el arroz cocido.", 30, 440, 38, 10, 50, _C),
    ("Hummus con crudités", ["garbanzos", "tahini", "zanahoria", "pepino", "limón", "aceite de oliva"],
     "Tritura garbanzos, tahini, limón y aceite; sirve con bastones de verdura.", 10, 290, 10, 16, 26, ["Media mañana", "Merienda"]),
    ("Merluza al horno con verduras", ["merluza", "calabacín", "pimiento rojo", "patata", "ajo", "aceite de oliva"],
     "Hornea las verduras 20 min, coloca la merluza encima y hornea 10 min más.", 30, 370, 34, 12, 32, _C),
    ("Fruta de temporada con almendras", ["manzana", "almendras"],
     "Trocea la fruta y acompaña con un puñado de almendras.", 3, 230, 5, 11, 28, ["Media mañana", "Merienda", "Recena"]),
]


def recetas_respaldo():
    return [{
        "id_api": f"respaldo_{i:02d}", "nombre": n, "ingredientes": list(ing), "instrucciones": ins,
        "tiempo_preparacion": t, "calorias": k, "proteinas": p, "grasas": g, "carbos": c,
        "momentos": list(m), "fuente": "Respaldo", "url_imagen": "",
    } for i, (n, ing, ins, t, k, p, g, c, m) in enumerate(_DATOS, 1)]

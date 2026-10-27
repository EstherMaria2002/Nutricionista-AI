"""
Filtro duro de alérgenos / intolerancias / alimentos vetados / patrones dietéticos.

Principios (bug 7):
  * Normaliza (minúsculas, sin tildes, sin signos) y aplica un stemming de plural muy simple.
  * La coincidencia es POR TÉRMINO (secuencia de tokens), nunca por substring:
    "pan" NO coincide con "panga" ni con "panceta".
  * Cada grupo (marisco, lácteos, gluten…) lleva sinónimos ES+EN y excepciones
    ("leche de coco" no es lácteo, "harina de arroz" no es gluten).
  * Fail-closed: una receta sin lista de ingredientes NO se puede verificar -> se descarta.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# Normalización
# ----------------------------------------------------------------------------
def normalizar(texto) -> str:
    t = unicodedata.normalize("NFKD", str(texto).lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


_PLURAL_ES = ("ones", "ares", "ores", "ales", "eles", "ules", "ures")


def _stem(tok: str) -> str:
    if len(tok) <= 3 or tok.isdigit():
        return tok
    if tok.endswith(_PLURAL_ES):
        return tok[:-2]                      # mejillones->mejillon, yogures->yogur
    if tok.endswith("ces"):
        return tok[:-3] + "z"                # nueces->nuez, peces->pez
    if tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]                      # gambas->gamba, tomates->tomate
    return tok


def tokens(texto) -> Tuple[str, ...]:
    return tuple(_stem(t) for t in normalizar(texto).split())


def _contiene(seq: Tuple[str, ...], sub: Tuple[str, ...]) -> bool:
    n = len(sub)
    return n > 0 and any(seq[i:i + n] == sub for i in range(len(seq) - n + 1))


# ----------------------------------------------------------------------------
# Grupos de alimentos  (términos ES + EN: Spoonacular devuelve ingredientes en inglés)
# ----------------------------------------------------------------------------
def _l(s: str) -> List[str]:
    return [x.strip() for x in s.split(",") if x.strip()]


GRUPOS: Dict[str, dict] = {
    "marisco": {
        "nombre": "marisco",
        "terminos": _l("marisco,gamba,langostino,camaron,cangrejo,langosta,bogavante,cigala,percebe,mejillon,almeja,"
                       "berberecho,ostra,vieira,calamar,pulpo,sepia,chipiron,navaja,coquina,shellfish,seafood,shrimp,"
                       "prawn,crab,lobster,crayfish,mussel,clam,oyster,scallop,squid,octopus,cuttlefish,calamari"),
        "excepciones": [],
    },
    "pescado": {
        "nombre": "pescado",
        "terminos": _l("pescado,atun,salmon,merluza,bacalao,lubina,dorada,sardina,anchoa,caballa,trucha,rape,lenguado,"
                       "boqueron,rodaballo,pez espada,emperador,panga,tilapia,surimi,bonito,caviar,fish,tuna,cod,"
                       "anchovy,sardine,mackerel,trout,haddock,halibut,mahi mahi,salsa de pescado,fish sauce"),
        "excepciones": [],
    },
    "huevo": {
        "nombre": "huevo",
        "terminos": _l("huevo,yema,mayonesa,merengue,egg,mayonnaise,meringue,albumina"),
        "excepciones": _l("huevo vegano,vegan egg,eggplant"),
    },
    "lacteos": {
        "nombre": "lácteos / lactosa",
        "terminos": _l("leche,queso,yogur,yogurt,yoghurt,mantequilla,nata,requeson,cuajada,kefir,ghee,lactosa,helado,"
                       "mascarpone,mozzarella,parmesano,ricotta,feta,cheddar,cream cheese,milk,cheese,butter,cream,"
                       "whey,suero de leche,caseina,casein,buttermilk,sour cream,parmesan,creme fraiche,cottage"),
        "excepciones": _l("leche de coco,leche de almendra,leche de avena,leche de soja,leche de arroz,leche de anacardo,"
                          "bebida vegetal,bebida de soja,bebida de avena,bebida de almendra,mantequilla de cacahuete,"
                          "mantequilla de almendra,mantequilla de anacardo,mantequilla de frutos secos,mantequilla de cacao,"
                          "manteca de cacao,crema de coco,nata de coco,queso vegano,yogur de soja,yogur de coco,"
                          "yogur vegetal,coconut milk,almond milk,oat milk,soy milk,rice milk,cashew milk,coconut cream,"
                          "cream of tartar,peanut butter,almond butter,cashew butter,nut butter,cocoa butter,vegan cheese,"
                          "coconut yogurt,soy yogurt,coconut butter,shea butter"),
    },
    "gluten": {
        "nombre": "gluten",
        "terminos": _l("gluten,trigo,espelta,centeno,cebada,avena,seitan,pan,pasta,espagueti,macarron,fideo,cuscus,"
                       "bulgur,semola,harina,galleta,cerveza,malta,salsa de soja,wheat,flour,bread,spaghetti,noodle,"
                       "couscous,barley,rye,oat,semolina,cracker,breadcrumb,macaroni,soy sauce,beer,pan rallado,"
                       "empanado,tortilla de trigo,tortillas de trigo"),
        "excepciones": _l("harina de arroz,harina de maiz,harina de garbanzo,harina de almendra,harina de coco,"
                          "harina de quinoa,harina de trigo sarraceno,rice flour,corn flour,almond flour,coconut flour,"
                          "chickpea flour,pasta de tomate,pasta de curry,pasta de miso,pasta de ajo,pasta de sesamo,"
                          "tomato paste,curry paste,miso paste,fideos de arroz,rice noodle,sin gluten,gluten free,"
                          "gluten-free,tamari,pan sin gluten"),
    },
    "frutos_secos": {
        "nombre": "frutos secos",
        "terminos": _l("frutos secos,fruto seco,almendra,nuez,avellana,anacardo,pistacho,pecana,macadamia,nuez de brasil,"
                       "pinon,turron,praline,mazapan,marzapan,cacahuete,mani,almond,walnut,hazelnut,cashew,pistachio,"
                       "pecan,brazil nut,pine nut,peanut,nut,mixed nuts,marzipan,nutella"),
        "excepciones": _l("nuez moscada,nutmeg,butternut"),
    },
    "cacahuete": {
        "nombre": "cacahuete",
        "terminos": _l("cacahuete,mani,peanut"),
        "excepciones": [],
    },
    "soja": {
        "nombre": "soja",
        "terminos": _l("soja,tofu,tempeh,edamame,miso,tamari,soy,soya,soybean,salsa de soja,soy sauce,lecitina de soja"),
        "excepciones": [],
    },
    "sesamo": {
        "nombre": "sésamo",
        "terminos": _l("sesamo,tahini,tahin,ajonjoli,hummus,humus,zaatar,sesame"),
        "excepciones": [],
    },
    "carne": {
        "nombre": "carne",
        "terminos": _l("carne,pollo,pavo,ternera,cerdo,cordero,conejo,pato,buey,vaca,jamon,chorizo,salchicha,bacon,"
                       "panceta,tocino,lomo,solomillo,chuleta,hamburguesa,albondiga,morcilla,fuet,salchichon,mortadela,"
                       "foie,beef,chicken,turkey,pork,lamb,duck,ham,sausage,steak,meat,veal,rabbit,meatball,pepperoni,"
                       "salami,prosciutto,brisket,ribs,caldo de pollo,caldo de carne,chicken broth,beef broth,lard,"
                       "manteca de cerdo,muslo,pechuga"),
        "excepciones": _l("pechuga de coco"),
    },
    "gelatina": {"nombre": "gelatina animal", "terminos": _l("gelatina,gelatin"), "excepciones": []},
    "miel": {"nombre": "miel", "terminos": _l("miel,honey,jalea real,propolis"), "excepciones": []},
    "cereales": {
        "nombre": "cereales",
        "terminos": _l("arroz,maiz,avena,cebada,centeno,trigo,pan,pasta,cuscus,fideo,tortilla de maiz,tortillas de maiz,"
                       "tortillas de trigo,pita,rice,corn,oat,bread,couscous,noodle,quinoa"),
        "excepciones": [],
    },
    "legumbres": {
        "nombre": "legumbres",
        "terminos": _l("lenteja,garbanzo,alubia,haba,guisante,judia blanca,judia pinta,frijol,soja,cacahuete,edamame,"
                       "tofu,tempeh,lentil,chickpea,bean,pea,hummus,humus,proteina de guisante"),
        "excepciones": _l("judia verde,green bean,judias verdes"),
    },
    "fodmap": {
        "nombre": "alto en FODMAP",
        "terminos": _l("ajo,cebolla,puerro,cebolleta,alcachofa,esparrago,coliflor,champinon,seta,remolacha,manzana,pera,"
                       "mango,sandia,melocoton,ciruela,cereza,miel,lenteja,garbanzo,alubia,judia blanca,haba,trigo,"
                       "centeno,agave,garlic,onion,leek,shallot,artichoke,asparagus,cauliflower,mushroom,apple,pear,"
                       "watermelon,peach,plum,honey,lentil,chickpea,bean,wheat,rye"),
        "excepciones": _l("judia verde,green bean,aceite de ajo,garlic oil"),
    },
    "fructosa": {
        "nombre": "fructosa",
        "terminos": _l("miel,manzana,pera,mango,sandia,uva,cereza,datil,higo,agave,jarabe de maiz,fructosa,honey,apple,"
                       "pear,watermelon,grape,cherry,date,fig,high fructose"),
        "excepciones": [],
    },
    "histamina": {
        "nombre": "alta en histamina",
        "terminos": _l("tomate,espinaca,berenjena,aguacate,fresa,vinagre,atun,sardina,caballa,anchoa,queso,jamon,chorizo,"
                       "salami,vino,cerveza,chocolate,cacao,salsa de soja,miso,chucrut,yogur,kefir,platano,tomato,"
                       "spinach,eggplant,aubergine,avocado,strawberry,vinegar,tuna,sardine,mackerel,anchovy,cheese,"
                       "ham,sausage,wine,beer,chocolate,cocoa,soy sauce,sauerkraut,yogurt,banana"),
        "excepciones": _l("tomate seco,sun dried tomato"),
    },
}

# Alias de lo que escribe el usuario -> grupos
ALIAS: Dict[str, List[str]] = {
    "frutos secos": ["frutos_secos"], "fruto seco": ["frutos_secos"], "nueces": ["frutos_secos"],
    "tree nut": ["frutos_secos"], "nuts": ["frutos_secos"],
    "marisco": ["marisco"], "mariscos": ["marisco"], "crustaceos": ["marisco"], "moluscos": ["marisco"],
    "shellfish": ["marisco"], "huevo": ["huevo"], "huevos": ["huevo"], "egg": ["huevo"],
    "lactosa": ["lacteos"], "lacteos": ["lacteos"], "lacteo": ["lacteos"], "leche": ["lacteos"],
    "derivados lacteos": ["lacteos"], "dairy": ["lacteos"], "lactose": ["lacteos"],
    "gluten": ["gluten"], "trigo": ["gluten"], "celiaquia": ["gluten"], "celiaco": ["gluten"],
    "soja": ["soja"], "soya": ["soja"], "soy": ["soja"], "pescado": ["pescado"], "fish": ["pescado"],
    "sesamo": ["sesamo"], "sesame": ["sesamo"], "cacahuete": ["cacahuete"], "cacahuetes": ["cacahuete"],
    "mani": ["cacahuete"], "peanut": ["cacahuete"], "fodmap": ["fodmap"], "fodmaps": ["fodmap"],
    "fructosa": ["fructosa"], "histamina": ["histamina"], "carne": ["carne"], "carnes": ["carne"],
}
_ALIAS_STEM = {" ".join(tokens(k)): v for k, v in ALIAS.items()}

# Patrones dietéticos -> grupos prohibidos
PATRONES: Dict[str, List[str]] = {
    "vegano": ["carne", "pescado", "marisco", "lacteos", "huevo", "miel", "gelatina"],
    "vegetariano": ["carne", "pescado", "marisco", "gelatina"],
    "pescetariano": ["carne", "gelatina"],
    "paleo": ["lacteos", "cereales", "legumbres"],
}
CHECKS = {  # checkboxes del Bloque 3.1 -> grupos
    "sin_gluten": ["gluten"], "sin_lactosa": ["lacteos"], "sin_frutos_secos": ["frutos_secos"],
    "sin_huevo": ["huevo"], "sin_soja": ["soja"], "sin_marisco": ["marisco"],
}
LEGACY = {"sin gluten": ["gluten"], "sin lactosa": ["lacteos"]}  # valores del formulario antiguo

# Traducción mínima ES->EN para términos libres del usuario (la API de Spoonacular está en inglés)
TRADUCCIONES = {
    "coliflor": "cauliflower", "brocoli": "broccoli", "espinaca": "spinach", "acelga": "chard", "cebolla": "onion",
    "ajo": "garlic", "tomate": "tomato", "pimiento": "pepper", "zanahoria": "carrot", "calabacin": "zucchini",
    "calabaza": "pumpkin", "berenjena": "eggplant", "champinon": "mushroom", "seta": "mushroom", "pepino": "cucumber",
    "lechuga": "lettuce", "patata": "potato", "boniato": "sweet potato", "aguacate": "avocado", "limon": "lemon",
    "naranja": "orange", "platano": "banana", "fresa": "strawberry", "manzana": "apple", "pera": "pear",
    "pollo": "chicken", "ternera": "beef", "cerdo": "pork", "cordero": "lamb", "pavo": "turkey", "atun": "tuna",
    "salmon": "salmon", "bacalao": "cod", "gamba": "shrimp", "arroz": "rice", "lenteja": "lentil",
    "garbanzo": "chickpea", "cilantro": "cilantro", "perejil": "parsley", "picante": "chili", "coco": "coconut",
    "queso": "cheese", "yogur": "yogurt", "mantequilla": "butter", "hongo": "mushroom", "apio": "celery",
    "remolacha": "beet", "esparrago": "asparagus", "guisante": "pea", "maiz": "corn", "cerveza": "beer",
}


@dataclass
class Prohibido:
    clave: str                          # grupo o término libre
    etiqueta: str                       # lo que ve el usuario
    terminos: List[Tuple[str, ...]]     # términos tokenizados
    originales: List[str]               # términos tal cual (para prompts)
    excepciones: List[Tuple[str, ...]] = field(default_factory=list)
    origenes: set = field(default_factory=set)   # alergia, vetado, patrón vegano…


def _desde_grupo(g: str, origen: str, acumulado: Dict[str, Prohibido]):
    if g not in acumulado:
        d = GRUPOS[g]
        acumulado[g] = Prohibido(
            clave=g, etiqueta=d["nombre"],
            terminos=[tokens(t) for t in d["terminos"]], originales=list(d["terminos"]),
            excepciones=[tokens(e) for e in d["excepciones"]],
        )
    acumulado[g].origenes.add(origen)


def _desde_texto(texto: str, origen: str, acumulado: Dict[str, Prohibido]):
    texto = (texto or "").strip()
    if not texto or normalizar(texto) in ("ninguna", "ninguno", "no", "nada"):
        return
    clave = " ".join(tokens(texto))
    if clave in _ALIAS_STEM:
        for g in _ALIAS_STEM[clave]:
            _desde_grupo(g, origen, acumulado)
        return
    k = f"lit:{clave}"
    if k not in acumulado:
        terms = [tokens(texto)]
        orig = [texto]
        en = TRADUCCIONES.get(normalizar(texto))
        if en:
            terms.append(tokens(en)); orig.append(en)
        acumulado[k] = Prohibido(clave=k, etiqueta=texto.strip(), terminos=terms, originales=orig)
    acumulado[k].origenes.add(origen)


def construir_prohibidos(datos: dict) -> List[Prohibido]:
    """Une alergias, intolerancias, vetados, checkboxes y patrones en una lista de Prohibido."""
    acc: Dict[str, Prohibido] = {}
    for campo, grupos in CHECKS.items():
        if datos.get(campo):
            for g in grupos:
                _desde_grupo(g, "restricción", acc)
    for t in datos.get("alergias") or []:
        _desde_texto(t, "alergia", acc)
    for t in datos.get("intolerancias") or []:
        _desde_texto(t, "intolerancia", acc)
    for t in datos.get("vetados") or []:
        _desde_texto(t, "no quiero verlo", acc)
    for p in datos.get("restricciones") or []:
        pn = normalizar(p)
        for g in PATRONES.get(pn, []):
            _desde_grupo(g, f"patrón {pn}", acc)
        for g in LEGACY.get(pn, []):
            _desde_grupo(g, "restricción", acc)
    return list(acc.values())


def ingrediente_prohibido(ingrediente: str, prohibidos: List[Prohibido]) -> Optional[str]:
    """Devuelve el motivo si el ingrediente está prohibido, o None."""
    seq = tokens(ingrediente)
    for p in prohibidos:
        if any(_contiene(seq, e) for e in p.excepciones):
            continue
        for term, orig in zip(p.terminos, p.originales):
            if _contiene(seq, term):
                return f"«{ingrediente}» contiene «{orig}» ({p.etiqueta}; {', '.join(sorted(p.origenes))})"
    return None


def receta_segura(receta: dict, prohibidos: List[Prohibido]) -> Tuple[bool, List[str]]:
    """Comprueba nombre + ingredientes. Sin ingredientes no se puede verificar -> no segura."""
    if not prohibidos:
        return True, []
    ings = [str(i) for i in (receta.get("ingredientes") or [])]
    if not ings:
        return False, ["sin lista de ingredientes: no verificable"]
    motivos = []
    for texto in [receta.get("nombre", "")] + ings:
        m = ingrediente_prohibido(texto, prohibidos)
        if m:
            motivos.append(m)
    return (not motivos), motivos


def filtrar_recetas(recetas: List[dict], prohibidos: List[Prohibido]) -> Tuple[List[dict], int]:
    seguras = [r for r in recetas if receta_segura(r, prohibidos)[0]]
    return seguras, len(recetas) - len(seguras)


def resumen_para_prompt(prohibidos: List[Prohibido], max_terminos: int = 25) -> List[str]:
    return [f"{p.etiqueta} ({', '.join(sorted(p.origenes))}): " + ", ".join(p.originales[:max_terminos])
            for p in prohibidos]


# ----------------------------------------------------------------------------
# Mapeo a parámetros de Spoonacular
# ----------------------------------------------------------------------------
_INTOL_SPOON = {"gluten": "gluten", "lacteos": "dairy", "huevo": "egg", "frutos_secos": "tree nut",
                "cacahuete": "peanut", "soja": "soy", "sesamo": "sesame", "marisco": "seafood"}


def parametros_spoonacular(prohibidos: List[Prohibido]) -> Tuple[List[str], List[str]]:
    """(intolerances, excludeIngredients) para complexSearch."""
    intol, excluir = [], []
    for p in prohibidos:
        if p.clave in _INTOL_SPOON:
            intol.append(_INTOL_SPOON[p.clave])
        elif p.clave.startswith("lit:"):
            excluir.extend(p.originales[1:])        # [1:] = traducción al inglés, si existe
    return sorted(set(intol)), sorted(set(excluir))

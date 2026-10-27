import sqlite3
from typing import List, Dict
import json
from datetime import datetime

DB_NAME = "recetas.db"


def _conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db():
    """Crea las tablas necesarias (y migra columnas nuevas sin tocar los datos existentes)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recetas (
            id_api TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            ingredientes TEXT,
            instrucciones TEXT,
            calorias REAL,
            proteinas REAL,
            grasas REAL,
            carbos REAL,
            tiempo_preparacion INTEGER,
            url_imagen TEXT,
            fuente TEXT,
            fecha_agregado TIMESTAMP,
            veces_usada INTEGER DEFAULT 0
        )
    ''')
    # NUEVO: momentos de comida aptos (JSON) para recetas generadas por IA
    columnas = [r[1] for r in cursor.execute("PRAGMA table_info(recetas)")]
    if "momentos" not in columnas:
        cursor.execute("ALTER TABLE recetas ADD COLUMN momentos TEXT")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_generacion TIMESTAMP,
            datos_usuario TEXT,
            menu_semanal TEXT,
            recetas_seleccionadas TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferencias (
            usuario_id TEXT,
            receta_id TEXT,
            puntuacion INTEGER,
            FOREIGN KEY (receta_id) REFERENCES recetas(id_api)
        )
    ''')
    conn.commit()
    conn.close()


def guardar_receta_db(receta: Dict):
    """Guarda o actualiza una receta (conserva veces_usada si ya existía)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO recetas
        (id_api, nombre, ingredientes, instrucciones, calorias, proteinas,
         grasas, carbos, tiempo_preparacion, url_imagen, fuente, fecha_agregado, momentos)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_api) DO UPDATE SET
            nombre=excluded.nombre, ingredientes=excluded.ingredientes, instrucciones=excluded.instrucciones,
            calorias=excluded.calorias, proteinas=excluded.proteinas, grasas=excluded.grasas,
            carbos=excluded.carbos, tiempo_preparacion=excluded.tiempo_preparacion,
            url_imagen=excluded.url_imagen, fuente=excluded.fuente, fecha_agregado=excluded.fecha_agregado,
            momentos=excluded.momentos
    ''', (
        receta['id_api'], receta['nombre'], json.dumps(receta['ingredientes'], ensure_ascii=False),
        receta['instrucciones'], receta['calorias'], receta['proteinas'], receta['grasas'], receta['carbos'],
        receta.get('tiempo_preparacion', 30), receta.get('url_imagen', ''), receta['fuente'],
        datetime.now(), json.dumps(receta.get('momentos') or [], ensure_ascii=False),
    ))
    conn.commit()
    conn.close()


def obtener_recetas_db(limite: int = 100) -> List[Dict]:
    """Obtiene recetas de la base local (las menos usadas primero)."""
    conn = _conn()
    filas = conn.execute('''
        SELECT * FROM recetas ORDER BY veces_usada ASC, fecha_agregado DESC LIMIT ?
    ''', (limite,)).fetchall()
    recetas = []
    for row in filas:
        try:
            ingredientes = json.loads(row["ingredientes"] or "[]")
        except json.JSONDecodeError:
            ingredientes = []
        recetas.append({
            "id_api": row["id_api"], "nombre": row["nombre"], "ingredientes": ingredientes,
            "instrucciones": row["instrucciones"], "calorias": row["calorias"], "proteinas": row["proteinas"],
            "grasas": row["grasas"], "carbos": row["carbos"], "tiempo_preparacion": row["tiempo_preparacion"],
            "url_imagen": row["url_imagen"], "fuente": row["fuente"],
            "momentos": json.loads(row["momentos"]) if row["momentos"] else [],
        })
    conn.close()
    return recetas


def marcar_recetas_usadas(ids: List[str]):
    """Incrementa veces_usada (rota las recetas en próximas generaciones)."""
    conn = sqlite3.connect(DB_NAME)
    conn.executemany("UPDATE recetas SET veces_usada = veces_usada + 1 WHERE id_api = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()


def guardar_menu_db(datos_usuario: Dict, menu: str, recetas_ids: List[str]):
    """Guarda el menú generado en la base de datos"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO menus (fecha_generacion, datos_usuario, menu_semanal, recetas_seleccionadas)
        VALUES (?, ?, ?, ?)
    ''', (datetime.now(), json.dumps(datos_usuario, ensure_ascii=False, default=str), menu, json.dumps(recetas_ids)))
    conn.commit()
    conn.close()

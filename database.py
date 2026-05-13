import sqlite3
from typing import List, Dict
import json
from datetime import datetime

DB_NAME = "recetas.db"

def inicializar_db():
    """Crea las tablas necesarias"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de recetas
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
    
    # Tabla de menús generados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_generacion TIMESTAMP,
            datos_usuario TEXT,
            menu_semanal TEXT,
            recetas_seleccionadas TEXT
        )
    ''')
    
    # Tabla de las preferencias del usuario
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
    """Guarda o actualiza una receta en la base de datos"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO recetas 
        (id_api, nombre, ingredientes, instrucciones, calorias, proteinas, 
         grasas, carbos, tiempo_preparacion, url_imagen, fuente, fecha_agregado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        receta['id_api'],
        receta['nombre'],
        json.dumps(receta['ingredientes']),
        receta['instrucciones'],
        receta['calorias'],
        receta['proteinas'],
        receta['grasas'],
        receta['carbos'],
        receta.get('tiempo_preparacion', 30),
        receta.get('url_imagen', ''),
        receta['fuente'],
        datetime.now()
    ))
    
    conn.commit()
    conn.close()

def obtener_recetas_db(limite: int = 100) -> List[Dict]:
    """Obtiene recetas de la base de datos local"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM recetas 
        ORDER BY veces_usada ASC, fecha_agregado DESC 
        LIMIT ?
    ''', (limite,))
    
    recetas = []
    for row in cursor.fetchall():
        receta = {
            "id_api": row[0],
            "nombre": row[1],
            "ingredientes": json.loads(row[2]),
            "instrucciones": row[3],
            "calorias": row[4],
            "proteinas": row[5],
            "grasas": row[6],
            "carbos": row[7],
            "tiempo_preparacion": row[8],
            "url_imagen": row[9],
            "fuente": row[10]
        }
        recetas.append(receta)
    
    conn.close()
    return recetas

def guardar_menu_db(datos_usuario: Dict, menu: str, recetas_ids: List[str]):
    """Guarda el menú generado en la base de datos"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO menus (fecha_generacion, datos_usuario, menu_semanal, recetas_seleccionadas)
        VALUES (?, ?, ?, ?)
    ''', (
        datetime.now(),
        json.dumps(datos_usuario),
        menu,
        json.dumps(recetas_ids)
    ))
    
    conn.commit()
    conn.close()
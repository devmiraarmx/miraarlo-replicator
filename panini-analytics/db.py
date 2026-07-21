"""
db.py — Conexión SQLite, esquema y funciones de carga.

Fase 1 del sistema de análisis de ventas Panini.
Responsabilidades:
  - Crear/abrir la base SQLite persistente (data/ventas.db)
  - Definir el esquema (tabla `ventas` + `cargas_log`)
  - Ingestar Excel mensual con INSERT OR IGNORE (sin duplicados)
"""

import os
import sqlite3
from datetime import datetime

import pandas as pd

# Ruta de la base configurable por entorno; default acorde a la guía.
DB_PATH = os.getenv("DB_PATH", os.path.join("data", "ventas.db"))

# Columnas requeridas en el Excel de origen (deben existir todas).
COLUMNAS_REQUERIDAS = [
    "ID_Venta", "Fecha", "Clave", "Titulo", "Proveedor", "Tipo",
    "Cantidad", "Precio_Unitario", "Costo_Unitario",
    "Importe_Venta", "Importe_Costo", "Utilidad",
]


def get_connection():
    """Devuelve una conexión SQLite, creando el directorio de la base si hace falta."""
    directorio = os.path.dirname(DB_PATH)
    if directorio:
        os.makedirs(directorio, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Respetar claves foráneas / integridad si en el futuro se agregan.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Crea las tablas e índices si no existen. Idempotente."""
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS ventas (
            id_venta TEXT PRIMARY KEY,
            fecha DATE NOT NULL,
            clave TEXT,
            titulo TEXT,
            proveedor TEXT,
            tipo TEXT,
            cantidad INTEGER,
            precio_unitario REAL,
            costo_unitario REAL,
            importe_venta REAL,
            importe_costo REAL,
            utilidad REAL,
            mes_carga TEXT NOT NULL,
            fecha_insercion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_fecha ON ventas(fecha);
        CREATE INDEX IF NOT EXISTS idx_proveedor ON ventas(proveedor);
        CREATE INDEX IF NOT EXISTS idx_tipo ON ventas(tipo);

        CREATE TABLE IF NOT EXISTS cargas_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT,
            mes_carga TEXT,
            filas_recibidas INTEGER,
            filas_insertadas INTEGER,
            filas_duplicadas INTEGER,
            fecha_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()


def _to_fecha(valor):
    """Normaliza cualquier representación de fecha a 'YYYY-MM-DD'.

    pandas puede entregar Timestamp, datetime, o string según el Excel;
    to_datetime cubre los tres casos y lanza si es basura irrecuperable.
    """
    ts = pd.to_datetime(valor, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"Fecha inválida: {valor!r}")
    return ts.strftime("%Y-%m-%d")


def _to_int(valor):
    if pd.isna(valor):
        return 0
    return int(valor)


def _to_float(valor):
    if pd.isna(valor):
        return 0.0
    return float(valor)


def cargar_excel(filepath, nombre_archivo):
    """Lee un Excel, valida columnas e inserta filas nuevas en `ventas`.

    Usa INSERT OR IGNORE con id_venta como PRIMARY KEY, de modo que subir
    el mismo archivo dos veces no duplica registros. Registra el resultado
    en `cargas_log`.

    Devuelve un dict con filas_recibidas / filas_insertadas / filas_duplicadas.
    """
    df = pd.read_excel(filepath)

    # 1. Validar columnas requeridas.
    faltantes = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas: {faltantes}")

    mes_carga = datetime.now().strftime("%Y-%m")
    filas_recibidas = len(df)
    filas_insertadas = 0

    conn = get_connection()
    cur = conn.cursor()
    try:
        for _, row in df.iterrows():
            cur.execute(
                """
                INSERT OR IGNORE INTO ventas
                (id_venta, fecha, clave, titulo, proveedor, tipo, cantidad,
                 precio_unitario, costo_unitario, importe_venta, importe_costo,
                 utilidad, mes_carga)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row["ID_Venta"]),
                    _to_fecha(row["Fecha"]),
                    row["Clave"],
                    row["Titulo"],
                    row["Proveedor"],
                    row["Tipo"],
                    _to_int(row["Cantidad"]),
                    _to_float(row["Precio_Unitario"]),
                    _to_float(row["Costo_Unitario"]),
                    _to_float(row["Importe_Venta"]),
                    _to_float(row["Importe_Costo"]),
                    _to_float(row["Utilidad"]),
                    mes_carga,
                ),
            )
            if cur.rowcount > 0:
                filas_insertadas += 1

        filas_duplicadas = filas_recibidas - filas_insertadas

        cur.execute(
            """
            INSERT INTO cargas_log (nombre_archivo, mes_carga, filas_recibidas,
                                    filas_insertadas, filas_duplicadas)
            VALUES (?, ?, ?, ?, ?)
            """,
            (nombre_archivo, mes_carga, filas_recibidas, filas_insertadas, filas_duplicadas),
        )

        conn.commit()
    finally:
        conn.close()

    return {
        "filas_recibidas": filas_recibidas,
        "filas_insertadas": filas_insertadas,
        "filas_duplicadas": filas_duplicadas,
    }


def contar_ventas():
    """Total de filas actualmente en la tabla `ventas` (útil para verificación)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ventas")
    total = cur.fetchone()[0]
    conn.close()
    return total


def historial_cargas(limite=20):
    """Últimas cargas registradas, más recientes primero."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM cargas_log ORDER BY fecha_carga DESC, id DESC LIMIT ?",
        (limite,),
    )
    filas = [dict(row) for row in cur.fetchall()]
    conn.close()
    return filas

"""
test_ingesta.py — Verificación de Fase 1.

Genera un Excel de ejemplo, lo carga DOS veces contra una base temporal y
confirma que:
  - La primera carga inserta todas las filas.
  - La segunda carga inserta 0 (todas duplicadas) => id_venta como PK funciona.
  - El total en la tabla no crece tras la segunda carga.

Ejecutar:  python test_ingesta.py
"""

import os
import tempfile

import pandas as pd

# Aísla la base en un archivo temporal ANTES de importar db.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DB_PATH"] = _tmp_db.name

import db  # noqa: E402  (import tras fijar DB_PATH a propósito)


def _excel_ejemplo(path):
    filas = [
        ("V005327", "2025-07-01", "MAN0383", "Gachiakuta 08", "Ivrea Argentina",
         "COMICS", 1, 271.88, 157.77, 271.88, 157.77, 114.11),
        ("V005328", "2025-07-02", "MAN0384", "Chainsaw Man 15", "Panini",
         "MARVEL", 2, 199.00, 120.00, 398.00, 240.00, 158.00),
        ("V005329", "2025-07-03", "COL0012", "Figura Batman", "DC Direct",
         "COLECCIONABLE", 1, 899.00, 540.00, 899.00, 540.00, 359.00),
    ]
    cols = ["ID_Venta", "Fecha", "Clave", "Titulo", "Proveedor", "Tipo",
            "Cantidad", "Precio_Unitario", "Costo_Unitario",
            "Importe_Venta", "Importe_Costo", "Utilidad"]
    df = pd.DataFrame(filas, columns=cols)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df.to_excel(path, index=False)


def main():
    db.init_db()

    with tempfile.TemporaryDirectory() as d:
        xlsx = os.path.join(d, "BASE_EJEMPLO_PANI.xlsx")
        _excel_ejemplo(xlsx)

        print("== Primera carga ==")
        r1 = db.cargar_excel(xlsx, "BASE_EJEMPLO_PANI.xlsx")
        print(r1)
        total_1 = db.contar_ventas()
        print("total en tabla:", total_1)

        print("\n== Segunda carga (mismo archivo) ==")
        r2 = db.cargar_excel(xlsx, "BASE_EJEMPLO_PANI.xlsx")
        print(r2)
        total_2 = db.contar_ventas()
        print("total en tabla:", total_2)

        # Aserciones
        assert r1["filas_recibidas"] == 3, "esperaba 3 filas recibidas"
        assert r1["filas_insertadas"] == 3, "la primera carga debe insertar las 3"
        assert r1["filas_duplicadas"] == 0, "la primera carga no debe tener duplicados"
        assert r2["filas_insertadas"] == 0, "la segunda carga NO debe insertar nada"
        assert r2["filas_duplicadas"] == 3, "la segunda carga debe marcar 3 duplicadas"
        assert total_1 == total_2 == 3, "el total no debe crecer tras recargar"

        print("\nHistorial de cargas:")
        for c in db.historial_cargas():
            print(" ", c["nombre_archivo"], c["filas_recibidas"],
                  c["filas_insertadas"], c["filas_duplicadas"])

    print("\n✅ Fase 1 OK — sin duplicados al recargar el mismo archivo.")


if __name__ == "__main__":
    try:
        main()
    finally:
        if os.path.exists(_tmp_db.name):
            os.remove(_tmp_db.name)

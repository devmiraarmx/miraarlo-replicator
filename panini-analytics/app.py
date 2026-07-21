"""
app.py — App Flask principal (Fase 1).

Expone la carga de Excel mensual:
  GET  /          → formulario simple de carga + historial
  POST /upload    → recibe el Excel, valida, inserta, regresa resumen de carga

Fases posteriores (KPIs, chat NL→SQL, auth) se agregan encima de esto.
"""

import os
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename

import db

load_dotenv()

UPLOAD_DIR = "uploads_temp"
EXTENSIONES_PERMITIDAS = {".xlsx", ".xls"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-solo-para-fase-1")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB tope de subida

# Asegura esquema y carpeta temporal al arrancar.
db.init_db()
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _extension_valida(nombre):
    return os.path.splitext(nombre)[1].lower() in EXTENSIONES_PERMITIDAS


@app.route("/")
def index():
    return render_template(
        "upload.html",
        total_ventas=db.contar_ventas(),
        historial=db.historial_cargas(),
    )


@app.route("/upload", methods=["POST"])
def upload():
    """Recibe un .xlsx, lo ingesta y devuelve el resumen de carga.

    Responde JSON si el cliente lo pide (fetch), o redirige con flash si es
    un submit de formulario clásico.
    """
    quiere_json = request.accept_mimetypes.best == "application/json" or \
        request.headers.get("X-Requested-With") == "fetch"

    archivo = request.files.get("archivo")
    if archivo is None or archivo.filename == "":
        return _responder(quiere_json, error="No se recibió ningún archivo.", codigo=400)

    if not _extension_valida(archivo.filename):
        return _responder(
            quiere_json,
            error="Formato no soportado. Sube un archivo .xlsx.",
            codigo=400,
        )

    nombre_original = secure_filename(archivo.filename)
    # Nombre temporal único para evitar colisiones entre cargas concurrentes.
    ruta_temp = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{nombre_original}")
    archivo.save(ruta_temp)

    try:
        resumen = db.cargar_excel(ruta_temp, nombre_original)
    except ValueError as e:
        return _responder(quiere_json, error=str(e), codigo=400)
    except Exception as e:  # noqa: BLE001 - superficie amplia para Fase 1
        return _responder(quiere_json, error=f"Error al procesar el archivo: {e}", codigo=500)
    finally:
        if os.path.exists(ruta_temp):
            os.remove(ruta_temp)

    mensaje = (
        f"Se recibieron {resumen['filas_recibidas']} filas, "
        f"se insertaron {resumen['filas_insertadas']} nuevas, "
        f"{resumen['filas_duplicadas']} duplicadas."
    )

    if quiere_json:
        return jsonify({"ok": True, "mensaje": mensaje, **resumen})

    flash(mensaje, "success")
    return redirect(url_for("index"))


def _responder(quiere_json, error=None, codigo=200):
    if quiere_json:
        return jsonify({"ok": error is None, "error": error}), codigo
    if error:
        flash(error, "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))

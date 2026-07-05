#!/usr/bin/env python3
"""Genera y fija una FERNET_KEY estable en el .env local.

Uso:
    python scripts/set_fernet_key.py          # crea la clave solo si no existe
    python scripts/set_fernet_key.py --force   # regenera aunque ya exista (¡cuidado!)

Por qué existe: la FERNET_KEY cifra los tokens de Mercado Libre guardados en la
base. Si cambia entre arranques, los tokens ya guardados dejan de descifrarse y
la cuenta aparece como "no conectada". Este script deja una clave FIJA en .env,
y NO la sobrescribe si ya hay una válida (salvo --force).

Multiplataforma (Windows / macOS / Linux). Solo depende de `cryptography`,
que ya está en requirements.txt.
"""

import sys
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:
    sys.exit("Falta 'cryptography'. Instala dependencias primero:  pip install -r requirements.txt")

# .env vive en la raíz del proyecto (un nivel arriba de scripts/).
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
KEY_NAME = "FERNET_KEY"


def _read_lines():
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _current_key(lines):
    """Devuelve el valor actual de FERNET_KEY en .env, o '' si no hay."""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{KEY_NAME}=") and not stripped.startswith("#"):
            return stripped.split("=", 1)[1].strip()
    return ""


def _is_valid_fernet(key):
    try:
        Fernet(key.encode())
        return True
    except (ValueError, TypeError):
        return False


def _write_key(lines, key):
    """Reescribe .env preservando el resto de líneas; reemplaza o añade FERNET_KEY."""
    new_line = f"{KEY_NAME}={key}"
    replaced = False
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{KEY_NAME}=") and not stripped.startswith("#"):
            out.append(new_line)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(new_line)
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    force = "--force" in sys.argv[1:]
    lines = _read_lines()
    existing = _current_key(lines)

    if existing and _is_valid_fernet(existing) and not force:
        print(f"✓ Ya existe una FERNET_KEY válida en {ENV_PATH.name}; no se toca.")
        print("  (Usa --force para regenerarla, pero eso invalidará los tokens ML ya guardados.)")
        return

    if existing and force:
        print("⚠ --force: regenerando la FERNET_KEY. Los tokens ML cifrados con la clave")
        print("  anterior dejarán de funcionar; habrá que reconectar la cuenta de ML.")

    key = Fernet.generate_key().decode()
    _write_key(lines, key)
    action = "creado" if not ENV_PATH.exists() else "actualizado"
    print(f"✓ FERNET_KEY escrita en {ENV_PATH}")
    print(f"  {KEY_NAME}={key}")


if __name__ == "__main__":
    main()

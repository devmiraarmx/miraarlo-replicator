import logging
import os
from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)

_fernet = None

# Los tokens Fernet son base64 y empiezan siempre con 'gAAAAA' (byte de versión 0x80).
# Sirve para distinguir un token cifrado (que debería descifrar) de un token legacy
# guardado en texto plano durante el prototipo.
_FERNET_PREFIX = 'gAAAAA'


def _get_fernet():
    global _fernet
    if _fernet is None:
        key = os.getenv('FERNET_KEY', '')
        if key:
            _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Cifra un token con Fernet. Sin FERNET_KEY devuelve el texto tal cual (dev)."""
    if not plaintext:
        return ''
    f = _get_fernet()
    if not f:
        log.warning("FERNET_KEY no configurada: el token ML se guardará SIN cifrar.")
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Descifra un token Fernet.

    - Sin FERNET_KEY: si el valor parece cifrado, avisa (no se podrá usar);
      si es texto plano legacy, lo devuelve tal cual.
    - Con FERNET_KEY: si el valor es un token Fernet que NO descifra, es señal de
      clave equivocada/rotada → lo registra en ERROR (antes se ocultaba en silencio,
      devolviendo basura que ML rechazaba con 401).
    - Token legacy en texto plano: se devuelve tal cual (migración del prototipo).
    """
    if not ciphertext:
        return ''

    looks_encrypted = ciphertext.startswith(_FERNET_PREFIX)
    f = _get_fernet()

    if not f:
        if looks_encrypted:
            log.error("Token ML cifrado pero FERNET_KEY no está configurada: "
                      "no se puede descifrar. Configura FERNET_KEY en el entorno.")
        return ciphertext

    try:
        return f.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        if looks_encrypted:
            # Token Fernet válido en forma, pero la clave no lo abre → clave incorrecta/rotada.
            log.error("No se pudo descifrar un token ML con la FERNET_KEY actual "
                      "(clave equivocada o rotada). La cuenta deberá reconectarse.")
            return ''
        # No parece cifrado: token legacy guardado en texto plano (prototipo).
        return ciphertext
    except Exception:
        log.exception("Error inesperado al descifrar un token ML.")
        return ciphertext if not looks_encrypted else ''


def generate_fernet_key() -> str:
    """Utilidad para generar una clave Fernet nueva. Usar una sola vez."""
    return Fernet.generate_key().decode()

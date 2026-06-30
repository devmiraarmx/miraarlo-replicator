import os
from cryptography.fernet import Fernet, InvalidToken

_fernet = None


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
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Descifra un token Fernet. Si no hay clave o el texto no está cifrado, lo devuelve tal cual."""
    if not ciphertext:
        return ''
    f = _get_fernet()
    if not f:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        # Token guardado sin cifrar (migración desde prototipo)
        return ciphertext


def generate_fernet_key() -> str:
    """Utilidad para generar una clave Fernet nueva. Usar una sola vez."""
    return Fernet.generate_key().decode()

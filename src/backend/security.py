import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# RNF-01: las contraseñas se guardan cifradas con hash (Argon2), nunca en claro.
# También están aquí las funciones puras de los tokens de sesión y de recuperación. Los permisos por rol
# dependen de la base de datos, por eso están en main.py y services.py.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def generar_token() -> tuple[str, str]:
    """Token aleatorio para la sesión o el enlace de recuperación.
    Devuelve (token en claro, hash). Solo el hash se guarda en la base de datos."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()  # 64 caracteres, como token_hash en models.py

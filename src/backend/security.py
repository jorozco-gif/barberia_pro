from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# RNF-01: las contraseñas se guardan cifradas con hash (Argon2), nunca en claro.
# Por ahora solo están las funciones de hash. En la autenticación se agregan el token y los permisos por rol.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
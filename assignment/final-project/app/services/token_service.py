from cryptography.fernet import Fernet, InvalidToken


class TokenEncryptionError(RuntimeError):
    pass


class TokenCipher:
    def __init__(self, key: str):
        if not key:
            raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY 未配置")
        try:
            self.fernet = Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY 格式无效") from exc

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise TokenEncryptionError("无法解密已保存的 Google Token") from exc


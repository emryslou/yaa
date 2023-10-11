import hashlib

try:
    hashlib.md5(b"data", usedforsecurity=True)

    def md5_hexdigest(data: bytes, *, usedforsecurity: bool = True) -> str:
        return hashlib.md5(data, usedforsecurity=usedforsecurity).hexdigest()

except TypeError:

    def md5_hexdigest(data: bytes, *, usedforsecurity: bool = True) -> str:
        return hashlib.md5(data).hexdigest()

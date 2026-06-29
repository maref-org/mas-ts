import hashlib
import hmac
import os


class HMACKeyManager:
    def __init__(self, initial_key: bytes | None = None) -> None:
        if initial_key is None:
            env_key = os.environ.get("MAS_HMAC_KEY")
            if env_key is not None:
                initial_key = env_key.encode("utf-8")
            else:
                msg = (
                    "HMAC key is required. "
                    "Pass initial_key explicitly or set MAS_HMAC_KEY env var."
                )
                raise ValueError(msg)
        self._current_key = initial_key
        self._current_key_id = hashlib.sha256(initial_key).hexdigest()[:16]
        self._previous_keys: dict[str, bytes] = {}

    @property
    def key_id(self) -> str:
        return self._current_key_id

    def rotate(self, new_key: bytes) -> str:
        old_key_id = self._current_key_id
        self._previous_keys[old_key_id] = self._current_key
        self._current_key = new_key
        self._current_key_id = hashlib.sha256(new_key).hexdigest()[:16]
        return old_key_id

    def sign(self, data: bytes) -> tuple[str, str]:
        h = hmac.new(self._current_key, digestmod=hashlib.sha256)
        h.update(data)
        return (self._current_key_id, h.hexdigest())

    def verify(self, data: bytes, signature: str, key_id: str | None = None) -> bool:
        if key_id is None or key_id == self._current_key_id:
            candidate_key = self._current_key
        elif key_id in self._previous_keys:
            candidate_key = self._previous_keys[key_id]
        else:
            return False
        h = hmac.new(candidate_key, digestmod=hashlib.sha256)
        h.update(data)
        return hmac.compare_digest(h.hexdigest(), signature)

    def derive_key(self, seed: str) -> bytes:
        h = hashlib.sha256(self._current_key)
        h.update(seed.encode("utf-8"))
        return h.digest()

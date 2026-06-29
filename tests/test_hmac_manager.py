import pytest

from mas_eval.security.hmac_manager import HMACKeyManager


class TestHMACKeyManager:
    def test_requires_explicit_key_or_env(self, monkeypatch):
        monkeypatch.delenv("MAS_HMAC_KEY", raising=False)
        with pytest.raises(ValueError, match="HMAC key is required"):
            HMACKeyManager()

    def test_accepts_explicit_key(self):
        mgr = HMACKeyManager(initial_key=b"test-key-32bytes-long-for-hmac!")
        assert mgr.key_id is not None
        assert len(mgr.key_id) == 16

    def test_reads_from_env_var(self, monkeypatch):
        monkeypatch.setenv("MAS_HMAC_KEY", "env-based-key-value")
        mgr = HMACKeyManager()
        assert mgr.key_id is not None

    def test_sign_and_verify(self):
        mgr = HMACKeyManager(initial_key=b"test-sign-key-12345678")
        data = b"important audit entry"
        key_id, signature = mgr.sign(data)
        assert mgr.verify(data, signature, key_id)

    def test_verify_wrong_signature(self):
        mgr = HMACKeyManager(initial_key=b"test-verify-key-12345")
        data = b"authentic entry"
        _, sig = mgr.sign(data)
        assert not mgr.verify(b"tampered entry", sig, mgr.key_id)

    def test_verify_unknown_key_id(self):
        mgr = HMACKeyManager(initial_key=b"test-unknown-key-123")
        data = b"some entry"
        _, sig = mgr.sign(data)
        assert not mgr.verify(data, sig, key_id="deadbeef12345678")

    def test_verify_with_rotated_key(self):
        mgr = HMACKeyManager(initial_key=b"original-key-12345678")
        data = b"entry signed with old key"
        old_key_id, old_sig = mgr.sign(data)
        mgr.rotate(b"new-key-value-for-rotation")
        assert mgr.verify(data, old_sig, key_id=old_key_id)

    def test_rotate_changes_key_id(self):
        mgr = HMACKeyManager(initial_key=b"pre-rotate-key-12345")
        old_id = mgr.key_id
        mgr.rotate(b"post-rotate-key-67890")
        assert mgr.key_id != old_id

    def test_rotate_returns_old_key_id(self):
        mgr = HMACKeyManager(initial_key=b"rotate-return-key-12")
        old_id = mgr.key_id
        returned_id = mgr.rotate(b"new-key-for-rotation-test")
        assert returned_id == old_id

    def test_derive_key_produces_deterministic_result(self):
        mgr = HMACKeyManager(initial_key=b"derive-seed-key-12345")
        k1 = mgr.derive_key("agent-alpha")
        k2 = mgr.derive_key("agent-alpha")
        assert k1 == k2

    def test_derive_key_different_seeds_differ(self):
        mgr = HMACKeyManager(initial_key=b"derive-diff-key-12345")
        k1 = mgr.derive_key("agent-alpha")
        k2 = mgr.derive_key("agent-beta")
        assert k1 != k2

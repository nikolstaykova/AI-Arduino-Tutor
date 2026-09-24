"""Encrypt a learner's Claude API key before it goes into the database.

Standard library only: a keystream from HMAC-SHA256 in counter mode (a PRF
used as a stream cipher) and encrypt-then-MAC with a separate HMAC key, so a
database row can't be read or altered without CQ_SECRET_KEY — which lives
only in the server's environment (Render), never in the database or git.

    token = seal("sk-ant-…")      → "v1.<nonce>.<ciphertext>.<tag>" (url-safe base64)
    open_(token)                  → "sk-ant-…"   (ValueError if tampered / wrong secret)
"""
import base64
import hashlib
import hmac
import os
import secrets


class NoSecret(RuntimeError):
    """CQ_SECRET_KEY isn't set — keys can't be stored safely."""


def _keys():
    secret = os.environ.get("CQ_SECRET_KEY", "")
    if len(secret) < 32:
        raise NoSecret("Set CQ_SECRET_KEY (at least 32 random characters) to store Claude keys.")
    root = secret.encode()
    return (hmac.new(root, b"circuitquest enc v1", hashlib.sha256).digest(),
            hmac.new(root, b"circuitquest mac v1", hashlib.sha256).digest())


def available():
    try:
        _keys()
        return True
    except NoSecret:
        return False


def _stream(key, nonce, n):
    out, counter = b"", 0
    while len(out) < n:
        out += hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return out[:n]


b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def seal(plaintext):
    enc, mac = _keys()
    nonce, data = secrets.token_bytes(16), plaintext.encode()
    ct = bytes(a ^ b for a, b in zip(data, _stream(enc, nonce, len(data))))
    tag = hmac.new(mac, b"v1" + nonce + ct, hashlib.sha256).digest()
    return ".".join(["v1", b64(nonce), b64(ct), b64(tag)])


def open_(token):
    enc, mac = _keys()
    try:
        version, nonce, ct, tag = token.split(".")
        nonce, ct, tag = unb64(nonce), unb64(ct), unb64(tag)
    except (ValueError, AttributeError):
        raise ValueError("not a sealed value")
    if version != "v1" or not hmac.compare_digest(tag, hmac.new(mac, b"v1" + nonce + ct, hashlib.sha256).digest()):
        raise ValueError("tampered, or sealed with another secret")
    return bytes(a ^ b for a, b in zip(ct, _stream(enc, nonce, len(ct)))).decode()

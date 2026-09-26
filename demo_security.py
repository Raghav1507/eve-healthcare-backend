"""Demo: watch hashing + JWT behave (and misbehave) in real time.

Run: python demo_security.py
"""
from app.security import create_access_token, decode_access_token, hash_password, verify_password

print("=== 1. HASHING ===")
h1 = hash_password("my_secret_123")
h2 = hash_password("my_secret_123")  # SAME password again
print("hash 1:", h1)
print("hash 2:", h2)
print("identical?", h1 == h2, " <-- must be False (random salt!)")
print("correct password verifies?", verify_password("my_secret_123", h1))
print("wrong password verifies?  ", verify_password("WRONG", h1))

print("\n=== 2. JWT ===")
token = create_access_token(subject="42")
print("token:", token)
print("decoded sub:", decode_access_token(token))

print("\n=== 3. TAMPERING ===")
head, body, sig = token.split(".")
# Attacker changes payload: user 42 -> user 1, keeps old signature
evil = head + "." + body + "." + ("A" * len(sig))
print("tampered token decoded:", decode_access_token(evil), "<-- must be None")

print("\n=== 4. EXPIRED-STYLE GARBAGE ===")
print("garbage token decoded:", decode_access_token("not.a.jwt"), "<-- must be None")

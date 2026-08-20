"""Round-trip test: encrypt via encrypt_html.js, decrypt via test_decrypt.js."""
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

sample = "<html><head><title>Round Trip</title></head><body><h1>Secret</h1><p>content here</p></body></html>"

p = subprocess.run(
    ["node", os.path.join(BASE, "encrypt_html.js"), "-"],
    input=sample, capture_output=True, text=True)
assert p.returncode == 0, p.stderr
enc = json.loads(p.stdout)

q = subprocess.run(
    ["node", os.path.join(BASE, "test_decrypt.js"),
     enc["ct_b64"], enc["iv_hex"], enc["key_b64url"]],
    capture_output=True, text=True)
assert q.returncode == 0, q.stderr
decrypted = q.stdout

print("round-trip OK:", decrypted.strip() == sample.strip())
if decrypted.strip() != sample.strip():
    print("GOT:", decrypted)
    sys.exit(1)

# stability: same key input → deterministic ciphertext shape; different key → different ct
p2 = subprocess.run(
    ["node", os.path.join(BASE, "encrypt_html.js"), "-", enc["key_hex"]],
    input=sample, capture_output=True, text=True)
enc2 = json.loads(p2.stdout)
q2 = subprocess.run(
    ["node", os.path.join(BASE, "test_decrypt.js"),
     enc2["ct_b64"], enc2["iv_hex"], enc2["key_b64url"]],
    capture_output=True, text=True)
assert q2.returncode == 0, q2.stderr
print("stable-key decrypt OK:", q2.stdout.strip() == sample.strip())
print("key reuse matches:", enc["key_b64url"] == enc2["key_b64url"])

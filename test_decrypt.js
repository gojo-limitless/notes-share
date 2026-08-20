// test_decrypt.js — verify AES-256-GCM round-trip (simulates browser WebCrypto path)
// Usage: node test_decrypt.js <ct_b64> <iv_hex> <key_b64url>
const crypto = require("crypto");
const [ct_b64, iv_hex, key_b64url] = process.argv.slice(2);
const key = Buffer.from(key_b64url, "base64url");
const iv = Buffer.from(iv_hex, "hex");
const data = Buffer.from(ct_b64, "base64");
const tag = data.subarray(data.length - 16);
const ct = data.subarray(0, data.length - 16);
const de = crypto.createDecipheriv("aes-256-gcm", key, iv);
de.setAuthTag(tag);
const out = Buffer.concat([de.update(ct), de.final()]);
console.log(out.toString("utf8"));

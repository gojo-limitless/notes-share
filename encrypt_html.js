#!/usr/bin/env node
// encrypt_html.js — AES-256-GCM encrypt a file for client-side decryption.
// Usage: node encrypt_html.js <file> <key-hex> [--iv-hex <hex>]
//   <key-hex>: 64 hex chars (32 bytes). If omitted, a random key is generated.
//   Prints JSON: {"key_hex", "iv_hex", "ct_b64", "key_b64url"}
// The key is printed so the caller can build the URL fragment (#key=<key_b64url>).
const crypto = require("crypto");
const fs = require("fs");

const file = process.argv[2];
if (!file) { console.error("usage: encrypt_html.js <file|-for-stdin> [key-hex]"); process.exit(1); }

const keyHex = process.argv[3];
const key = keyHex ? Buffer.from(keyHex, "hex") : crypto.randomBytes(32);
const iv = crypto.randomBytes(12);

let html;
if (file === "-") {
  html = fs.readFileSync(0, "utf8"); // stdin
} else {
  html = fs.readFileSync(file, "utf8");
}

const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
const ct = Buffer.concat([cipher.update(html, "utf8"), cipher.final()]);
const tag = cipher.getAuthTag();

console.log(JSON.stringify({
  key_hex: key.toString("hex"),
  iv_hex: iv.toString("hex"),
  ct_b64: Buffer.concat([ct, tag]).toString("base64"),
  key_b64url: key.toString("base64url"),
}));

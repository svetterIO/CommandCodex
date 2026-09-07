const CURRENT_AAD = new TextEncoder().encode('security-reference:source:v1');
const LEGACY_AADS = [new TextEncoder().encode('nmap-cheatsheet:source:v1')];
const DEFAULT_ITERATIONS = 600000;

function bytesToBase64(bytes) {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) out[i] = binary.charCodeAt(i);
  return out;
}

function equalBytes(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

function supportedAad(aad) {
  if (equalBytes(aad, CURRENT_AAD)) return true;
  return LEGACY_AADS.some(candidate => equalBytes(aad, candidate));
}

async function deriveKey(password, salt, iterations) {
  const keyMaterial = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

export function validatePayload(payload) {
  if (!payload || typeof payload !== 'object') throw new Error('Not a JSON object.');
  if (payload.version !== 1) throw new Error('Unsupported encrypted payload version.');
  if (payload.cipher !== 'AES-256-GCM') throw new Error('Unsupported cipher.');
  if (payload.kdf !== 'PBKDF2-HMAC-SHA256') throw new Error('Unsupported KDF.');
  if (!Number.isInteger(payload.iterations) || payload.iterations < 100000) {
    throw new Error('Invalid PBKDF2 iteration count.');
  }
  for (const field of ['salt', 'iv', 'aad', 'ciphertext']) {
    if (typeof payload[field] !== 'string' || !payload[field]) throw new Error(`Missing ${field}.`);
  }
  const aad = base64ToBytes(payload.aad);
  if (!supportedAad(aad)) throw new Error('Unexpected encrypted-source label.');
  return true;
}

export async function decryptPayload(payload, password) {
  validatePayload(payload);
  const salt = base64ToBytes(payload.salt);
  const iv = base64ToBytes(payload.iv);
  const aad = base64ToBytes(payload.aad);
  const ciphertext = base64ToBytes(payload.ciphertext);
  const key = await deriveKey(password, salt, payload.iterations);
  try {
    const clear = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv, additionalData: aad, tagLength: 128 }, key, ciphertext
    );
    return new TextDecoder('utf-8', { fatal: true }).decode(clear);
  } catch {
    throw new Error('Incorrect password or damaged encrypted source.');
  }
}

export async function encryptMarkdown(markdown, password, iterations = DEFAULT_ITERATIONS) {
  if (!password) throw new Error('Encryption password must not be empty.');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(password, salt, iterations);
  const plaintext = new TextEncoder().encode(markdown);
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv, additionalData: CURRENT_AAD, tagLength: 128 }, key, plaintext
  );
  return {
    version: 1,
    cipher: 'AES-256-GCM',
    kdf: 'PBKDF2-HMAC-SHA256',
    iterations,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    aad: bytesToBase64(CURRENT_AAD),
    ciphertext: bytesToBase64(new Uint8Array(encrypted))
  };
}

export function serializePayload(payload) {
  validatePayload(payload);
  return JSON.stringify(payload) + '\n';
}

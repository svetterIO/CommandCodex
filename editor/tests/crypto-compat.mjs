if (!globalThis.atob) globalThis.atob = value => Buffer.from(value, 'base64').toString('binary');
if (!globalThis.btoa) globalThis.btoa = value => Buffer.from(value, 'binary').toString('base64');
import fs from 'node:fs/promises';
const { encryptMarkdown, decryptPayload, serializePayload } = await import('../app/crypto.js');
const source = '# Compatibility test\n\n```text\nexample-tool --target {{IP}}\n```\n';
const payload = await encryptMarkdown(source, 'passw0rd');
const roundtrip = await decryptPayload(JSON.parse(serializePayload(payload)), 'passw0rd');
if (roundtrip !== source) throw new Error('Browser crypto round-trip failed');
let bad = false;
try { await decryptPayload(payload, 'wrong-password'); } catch { bad = true; }
if (!bad) throw new Error('Wrong password unexpectedly decrypted');
const bundled = JSON.parse(await fs.readFile(new URL('../../content/cheatsheets/nmap.md.enc.json', import.meta.url), 'utf8'));
const bundledText = await decryptPayload(bundled, 'passw0rd');
if (!bundledText.startsWith('# Nmap')) throw new Error('Bundled encrypted source is not editor-compatible');
console.log('Browser crypto compatibility test passed.');

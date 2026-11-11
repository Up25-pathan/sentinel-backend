const express = require('express');
const rateLimit = require('express-rate-limit');
const crypto = require('crypto');
const { isUnset } = require('../env');
const { safeEqual } = require('../middleware/auth');
const store = require('../services/vault-store');
const { logAction } = require('../services/audit-log');

const router = express.Router();

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHA256_RE = /^[0-9a-f]{64}$/i;
const MIN_CHUNK_BYTES = 64 * 1024;
const MAX_CHUNK_BYTES = 2 * 1024 * 1024;
const MAX_META_BYTES = 64 * 1024;
const OWNER_ID = process.env.VAULT_OWNER_ID || 'vault';
const DEFAULT_KDF_PARAMS = {
    algo: 'argon2id',
    time_cost: 3,
    memory_cost: 65536,
    parallelism: 2,
    hash_len: 32,
};

const MAX_PASSKEY_FAILURES = 5;
const PASSKEY_LOCKOUT_MS = 15 * 60 * 1000;
const passkeyFailures = new Map();

function passkeyLockoutRemaining() {
    const entry = passkeyFailures.get(OWNER_ID);
    if (!entry) return 0;
    const remaining = entry.until - Date.now();
    if (remaining <= 0) {
        passkeyFailures.delete(OWNER_ID);
        return 0;
    }
    return remaining;
}

function recordPasskeyFailure() {
    const now = Date.now();
    const entry = passkeyFailures.get(OWNER_ID);
    if (!entry || now > entry.until) {
        passkeyFailures.set(OWNER_ID, { count: 1, until: now + PASSKEY_LOCKOUT_MS });
        return 1;
    }
    entry.count += 1;
    if (entry.count >= MAX_PASSKEY_FAILURES) {
        entry.until = now + PASSKEY_LOCKOUT_MS;
    }
    return entry.count;
}

function clearPasskeyFailures() {
    passkeyFailures.delete(OWNER_ID);
}

function httpError(status, message) {
    const err = new Error(message);
    err.status = status;
    return err;
}

function requirePasskey(req) {
    if (isUnset(process.env.VAULT_PASSKEY)) {
        throw httpError(503, 'Vault passkey is not configured on the server');
    }
    const locked = passkeyLockoutRemaining();
    if (locked > 0) {
        const minutes = Math.ceil(locked / 60000);
        throw httpError(429, `Vault passkey locked. Try again in ${minutes} minute${minutes === 1 ? '' : 's'}.`);
    }
    const passkey = req.headers['x-vault-passkey'];
    if (!passkey || !safeEqual(String(passkey), process.env.VAULT_PASSKEY)) {
        recordPasskeyFailure();
        throw httpError(401, 'Invalid vault passkey');
    }
    clearPasskeyFailures();
}

function readUuid(value, field) {
    if (typeof value !== 'string' || !UUID_RE.test(value)) {
        throw httpError(400, `${field} must be a UUID`);
    }
    return value;
}

function readBase64(value, field, minBytes, maxBytes) {
    if (typeof value !== 'string' || !value.trim()) {
        throw httpError(400, `${field} is required`);
    }
    const raw = Buffer.from(value, 'base64');
    if (!raw.length || raw.length < minBytes || raw.length > maxBytes) {
        throw httpError(400, `${field} has an invalid length`);
    }
    const canonical = raw.toString('base64').replace(/=+$/, '');
    if (canonical !== value.replace(/=+$/, '')) {
        throw httpError(400, `${field} is not valid base64`);
    }
    return value;
}

function readInteger(value, field, min, max) {
    if (!Number.isInteger(value) || value < min || value > max) {
        throw httpError(400, `${field} must be an integer between ${min} and ${max}`);
    }
    return value;
}

function serialiseFile(row) {
    return {
        id: row.id,
        encrypted_meta: row.encrypted_meta,
        size_plain: Number(row.size_plain),
        size_cipher: Number(row.size_cipher),
        chunk_size: row.chunk_size,
        chunk_count: row.chunk_count,
        sha256_cipher: row.sha256_cipher,
        created_at: row.created_at,
        updated_at: row.updated_at,
    };
}

const vaultAuthLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 30,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many vault unlock attempts, please retry shortly.' }
});

router.post('/auth', vaultAuthLimiter, async (req, res, next) => {
    try {
        const body = req.body || {};
        const passkey = String(body.passkey || '');
        if (isUnset(process.env.VAULT_PASSKEY)) {
            throw httpError(503, 'Vault passkey is not configured on the server');
        }
        if (passkey.length !== 6 || !/^\d{6}$/.test(passkey)) {
            throw httpError(400, 'Passkey must be exactly 6 digits');
        }
        if (!safeEqual(passkey, process.env.VAULT_PASSKEY)) {
            recordPasskeyFailure();
            const locked = passkeyLockoutRemaining();
            if (locked > 0) {
                const minutes = Math.ceil(locked / 60000);
                return res.status(429).json({
                    error: `Vault passkey locked. Try again in ${minutes} minute${minutes === 1 ? '' : 's'}.`
                });
            }
            return res.status(401).json({ error: 'Invalid vault passkey' });
        }
        clearPasskeyFailures();
        const kdfSalt = Buffer.from(crypto.randomBytes(16)).toString('base64');
        const vault = await store.ensureVault(OWNER_ID, {
            name: 'Vault',
            kdfSalt,
            kdfParams: DEFAULT_KDF_PARAMS,
            keyCheck: '',
        });
        logAction('VAULT_AUTH', 'Vault unlocked by passkey');
        res.json({
            authorized: true,
            vault: {
                id: vault.id,
                name: vault.name,
                kdf_salt: vault.kdf_salt,
                kdf_params: vault.kdf_params,
                key_check: vault.key_check,
                created_at: vault.created_at,
                updated_at: vault.updated_at,
                file_count: Number(vault.file_count),
                bytes_used: Number(vault.bytes_used),
                quota_bytes: store.quotaBytes(),
                max_file_bytes: store.maxFileBytes(),
            },
        });
    } catch (err) {
        next(err);
    }
});

router.use(requirePasskey);

router.get('/', async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        res.json({
            vault: {
                id: vault.id,
                name: vault.name,
                kdf_salt: vault.kdf_salt,
                kdf_params: vault.kdf_params,
                key_check: vault.key_check,
                created_at: vault.created_at,
                updated_at: vault.updated_at,
                file_count: Number(vault.file_count),
                bytes_used: Number(vault.bytes_used),
                quota_bytes: store.quotaBytes(),
                max_file_bytes: store.maxFileBytes(),
            },
        });
    } catch (err) {
        next(err);
    }
});

router.get('/files', async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        const files = await store.listFiles(vault.id);
        res.json({ files: files.map(serialiseFile) });
    } catch (err) {
        next(err);
    }
});

router.post('/files', async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        const body = req.body || {};
        const id = readUuid(body.id, 'id');
        const encryptedMeta = readBase64(body.encrypted_meta, 'encrypted_meta', 1, MAX_META_BYTES);
        const sizePlain = readInteger(body.size_plain, 'size_plain', 0, store.maxFileBytes());
        const chunkSize = readInteger(body.chunk_size, 'chunk_size', MIN_CHUNK_BYTES, MAX_CHUNK_BYTES);
        const chunkCount = readInteger(body.chunk_count, 'chunk_count', 1, 16384);
        await store.createFile(vault.id, {
            id,
            encryptedMeta,
            sizePlain,
            chunkSize,
            chunkCount,
        });
        logAction('VAULT_FILE_CREATE', `Started upload ${id}`);
        res.status(201).json({ id });
    } catch (err) {
        next(err);
    }
});

router.put('/files/:id/chunks/:index', express.raw({
    type: 'application/octet-stream',
    limit: MAX_CHUNK_BYTES,
}), async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        const fileId = readUuid(req.params.id, 'id');
        const index = Number.parseInt(req.params.index, 10);
        if (!Number.isInteger(index) || index < 0) throw httpError(400, 'Invalid chunk index');
        if (!Buffer.isBuffer(req.body)) throw httpError(415, 'Chunk must be application/octet-stream');
        await store.putChunk(vault.id, fileId, index, req.body);
        res.status(204).end();
    } catch (err) {
        next(err);
    }
});

router.post('/files/:id/finalize', async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        const fileId = readUuid(req.params.id, 'id');
        const body = req.body || {};
        let sha256Cipher = null;
        if (body.sha256_cipher !== undefined && body.sha256_cipher !== null && body.sha256_cipher !== '') {
            if (typeof body.sha256_cipher !== 'string' || !SHA256_RE.test(body.sha256_cipher)) {
                throw httpError(400, 'sha256_cipher must be a hex SHA-256 digest');
            }
            sha256Cipher = body.sha256_cipher.toLowerCase();
        }
        const file = await store.finalizeFile(vault.id, fileId, sha256Cipher);
        logAction('VAULT_FILE_FINALIZE', `Finalized upload ${fileId}`);
        res.json({ file: serialiseFile(file) });
    } catch (err) {
        next(err);
    }
});

router.get('/files/:id/chunks/:index', async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        const fileId = readUuid(req.params.id, 'id');
        const index = Number.parseInt(req.params.index, 10);
        if (!Number.isInteger(index) || index < 0) throw httpError(400, 'Invalid chunk index');
        const data = await store.getChunk(vault.id, fileId, index);
        if (!data) return res.status(404).json({ error: 'Chunk not found' });
        res.setHeader('Content-Type', 'application/octet-stream');
        res.setHeader('Cache-Control', 'no-store');
        res.send(data);
    } catch (err) {
        next(err);
    }
});

router.patch('/files/:id', async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        const fileId = readUuid(req.params.id, 'id');
        const body = req.body || {};
        const encryptedMeta = readBase64(body.encrypted_meta, 'encrypted_meta', 1, MAX_META_BYTES);
        const updated = await store.updateFileMeta(vault.id, fileId, encryptedMeta);
        if (!updated) return res.status(404).json({ error: 'File not found' });
        logAction('VAULT_FILE_UPDATE', `Updated metadata for ${fileId}`);
        res.json({ success: true });
    } catch (err) {
        next(err);
    }
});

router.delete('/files/:id', async (req, res, next) => {
    try {
        const vault = await store.getVault(OWNER_ID);
        if (!vault) return res.status(404).json({ error: 'No vault exists for this account' });
        const fileId = readUuid(req.params.id, 'id');
        const deleted = await store.deleteFile(vault.id, fileId);
        if (!deleted) return res.status(404).json({ error: 'File not found' });
        logAction('VAULT_FILE_DELETE', `Deleted ${fileId}`);
        res.json({ success: true });
    } catch (err) {
        next(err);
    }
});

module.exports = router;

const crypto = require('crypto');
const { Pool } = require('pg');

let pool = null;
let schemaPromise = null;

function intEnv(name, fallback, min, max) {
    const raw = process.env[name];
    const value = raw === undefined ? fallback : Number.parseInt(raw, 10);
    if (!Number.isInteger(value) || value < min || value > max) return fallback;
    return value;
}

function maxFileBytes() {
    return intEnv('VAULT_MAX_FILE_BYTES', 100 * 1024 * 1024, 1024, 512 * 1024 * 1024);
}

function quotaBytes() {
    return intEnv('VAULT_QUOTA_BYTES', 900 * 1024 * 1024, 1024 * 1024, 1024 * 1024 * 1024);
}

function isConfigured() {
    return Boolean(process.env.VAULT_DATABASE_URL && String(process.env.VAULT_DATABASE_URL).trim());
}

function httpError(status, message) {
    const err = new Error(message);
    err.status = status;
    return err;
}

function sslConfig() {
    const ca = process.env.VAULT_DB_SSL_CA;
    const ssl = { rejectUnauthorized: process.env.VAULT_DB_SSL_INSECURE !== '1' };
    if (ca && String(ca).trim()) {
        ssl.ca = String(ca).replace(/\\n/g, '\n');
    }
    return ssl;
}

function getPool() {
    if (!isConfigured()) {
        throw httpError(503, 'Vault storage is not configured on the server');
    }
    if (!pool) {
        pool = new Pool({
            connectionString: process.env.VAULT_DATABASE_URL,
            ssl: sslConfig(),
            max: 4,
            idleTimeoutMillis: 30_000,
            connectionTimeoutMillis: 10_000,
        });
        pool.on('error', (err) => {
            console.error('Vault PostgreSQL pool error:', err.message);
        });
    }
    return pool;
}

async function ensureSchema() {
    if (schemaPromise) return schemaPromise;
    schemaPromise = (async () => {
        const db = getPool();
        await db.query(`
            CREATE TABLE IF NOT EXISTS vaults (
                id UUID PRIMARY KEY,
                owner_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                kdf_salt TEXT NOT NULL,
                kdf_params JSONB NOT NULL,
                key_check TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        `);
        await db.query(`
            CREATE TABLE IF NOT EXISTS vault_files (
                id UUID PRIMARY KEY,
                vault_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
                encrypted_meta TEXT NOT NULL,
                size_plain BIGINT NOT NULL,
                size_cipher BIGINT NOT NULL DEFAULT 0,
                chunk_size INTEGER NOT NULL,
                chunk_count INTEGER NOT NULL,
                sha256_cipher TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        `);
        await db.query(`
            CREATE INDEX IF NOT EXISTS vault_files_vault_status_idx
            ON vault_files (vault_id, status, created_at DESC)
        `);
        await db.query(`
            CREATE TABLE IF NOT EXISTS vault_folders (
                id UUID PRIMARY KEY,
                vault_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
                encrypted_meta TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        `);
        await db.query(`
            CREATE INDEX IF NOT EXISTS vault_folders_vault_idx
            ON vault_folders (vault_id, created_at)
        `);
        await db.query(`
            CREATE TABLE IF NOT EXISTS vault_chunks (
                file_id UUID NOT NULL REFERENCES vault_files(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                data BYTEA NOT NULL,
                PRIMARY KEY (file_id, chunk_index)
            )
        `);
    })().catch((err) => {
        schemaPromise = null;
        throw err;
    });
    return schemaPromise;
}

async function getVault(ownerId) {
    await ensureSchema();
    const result = await getPool().query(
        `SELECT v.id, v.name, v.kdf_salt, v.kdf_params, v.key_check, v.created_at, v.updated_at,
                COALESCE(f.file_count, 0)::int AS file_count,
                COALESCE(f.bytes_used, 0)::bigint AS bytes_used
         FROM vaults v
         LEFT JOIN (
             SELECT vault_id, COUNT(*)::int AS file_count, COALESCE(SUM(size_plain), 0) AS bytes_used
             FROM vault_files WHERE status = 'ready' GROUP BY vault_id
         ) f ON f.vault_id = v.id
         WHERE v.owner_id = $1`,
        [ownerId]
    );
    return result.rows[0] || null;
}

async function ensureVault(ownerId, { name = 'Vault', kdfSalt, kdfParams, keyCheck = '' }) {
    await ensureSchema();
    const existing = await getVault(ownerId);
    if (existing) return existing;
    const id = crypto.randomUUID();
    const result = await getPool().query(
        `INSERT INTO vaults (id, owner_id, name, kdf_salt, kdf_params, key_check)
         VALUES ($1, $2, $3, $4, $5::jsonb, $6)
         RETURNING id, name, kdf_salt, kdf_params, key_check, created_at, updated_at`,
        [id, ownerId, name, kdfSalt, JSON.stringify(kdfParams), keyCheck]
    );
    return result.rows[0];
}

async function listFiles(vaultId) {
    await ensureSchema();
    const result = await getPool().query(
        `SELECT id, encrypted_meta, size_plain, size_cipher, chunk_size, chunk_count,
                sha256_cipher, created_at, updated_at
         FROM vault_files
         WHERE vault_id = $1 AND status = 'ready'
         ORDER BY created_at DESC`,
        [vaultId]
    );
    return result.rows;
}

async function listFolders(vaultId) {
    await ensureSchema();
    const result = await getPool().query(
        `SELECT id, encrypted_meta, created_at, updated_at
         FROM vault_folders
         WHERE vault_id = $1
         ORDER BY created_at ASC`,
        [vaultId]
    );
    return result.rows;
}

async function createFolder(vaultId, { id, encryptedMeta }) {
    await ensureSchema();
    const result = await getPool().query(
        `INSERT INTO vault_folders (id, vault_id, encrypted_meta)
         VALUES ($1, $2, $3)
         RETURNING id, encrypted_meta, created_at, updated_at`,
        [id, vaultId, encryptedMeta]
    );
    return result.rows[0];
}

async function updateFolderMeta(vaultId, folderId, encryptedMeta) {
    await ensureSchema();
    const result = await getPool().query(
        `UPDATE vault_folders
         SET encrypted_meta = $3, updated_at = now()
         WHERE id = $1 AND vault_id = $2
         RETURNING id`,
        [folderId, vaultId, encryptedMeta]
    );
    return result.rowCount > 0;
}

async function deleteFolder(vaultId, folderId) {
    await ensureSchema();
    const result = await getPool().query(
        'DELETE FROM vault_folders WHERE id = $1 AND vault_id = $2',
        [folderId, vaultId]
    );
    return result.rowCount > 0;
}

async function createFile(vaultId, { id, encryptedMeta, sizePlain, chunkSize, chunkCount }) {
    await ensureSchema();
    if (sizePlain > maxFileBytes()) {
        throw httpError(413, `File exceeds the ${Math.floor(maxFileBytes() / (1024 * 1024))} MB limit`);
    }
    const expectedChunks = Math.max(1, Math.ceil(sizePlain / chunkSize));
    if (chunkCount !== expectedChunks) throw httpError(400, 'Chunk count does not match file size');

    const db = getPool();
    const client = await db.connect();
    try {
        await client.query('BEGIN');
        const vault = await client.query('SELECT id FROM vaults WHERE id = $1 FOR UPDATE', [vaultId]);
        if (!vault.rowCount) throw httpError(404, 'Vault not found');

        await client.query(
            `DELETE FROM vault_files
             WHERE vault_id = $1 AND status = 'pending' AND created_at < now() - interval '1 day'`,
            [vaultId]
        );

        const used = await client.query(
            `SELECT COALESCE(SUM(size_plain), 0)::bigint AS used FROM vault_files WHERE vault_id = $1`,
            [vaultId]
        );
        if (BigInt(used.rows[0].used) + BigInt(sizePlain) > BigInt(quotaBytes())) {
            throw httpError(507, 'Vault storage quota exceeded');
        }

        await client.query(
            `INSERT INTO vault_files
                (id, vault_id, encrypted_meta, size_plain, chunk_size, chunk_count, status)
             VALUES ($1, $2, $3, $4, $5, $6, 'pending')`,
            [id, vaultId, encryptedMeta, sizePlain, chunkSize, chunkCount]
        );
        await client.query('COMMIT');
    } catch (err) {
        await client.query('ROLLBACK').catch(() => {});
        throw err;
    } finally {
        client.release();
    }
}

async function putChunk(vaultId, fileId, index, data) {
    await ensureSchema();
    const db = getPool();
    const file = await db.query(
        `SELECT f.chunk_count, f.chunk_size
         FROM vault_files f JOIN vaults v ON v.id = f.vault_id
         WHERE f.id = $1 AND f.vault_id = $2 AND v.id = $2 AND f.status = 'pending'`,
        [fileId, vaultId]
    );
    if (!file.rowCount) throw httpError(404, 'Pending file not found');
    const { chunk_count: chunkCount, chunk_size: chunkSize } = file.rows[0];
    if (index < 0 || index >= chunkCount) throw httpError(400, 'Chunk index out of range');
    if (!Buffer.isBuffer(data) || data.length > chunkSize) throw httpError(413, 'Chunk is too large');

    await db.query(
        `INSERT INTO vault_chunks (file_id, chunk_index, data)
         VALUES ($1, $2, $3)
         ON CONFLICT (file_id, chunk_index) DO UPDATE SET data = EXCLUDED.data`,
        [fileId, index, data]
    );
}

async function finalizeFile(vaultId, fileId, sha256Cipher) {
    await ensureSchema();
    const db = getPool();
    const client = await db.connect();
    try {
        await client.query('BEGIN');
        const file = await client.query(
            `SELECT f.chunk_count
             FROM vault_files f JOIN vaults v ON v.id = f.vault_id
             WHERE f.id = $1 AND f.vault_id = $2 AND f.status = 'pending'
             FOR UPDATE`,
            [fileId, vaultId]
        );
        if (!file.rowCount) throw httpError(404, 'Pending file not found');

        const stats = await client.query(
            `SELECT COUNT(*)::int AS count, COALESCE(SUM(octet_length(data)), 0)::bigint AS size
             FROM vault_chunks WHERE file_id = $1`,
            [fileId]
        );
        if (stats.rows[0].count !== file.rows[0].chunk_count) {
            throw httpError(400, 'File is missing chunks');
        }
        const result = await client.query(
            `UPDATE vault_files
             SET status = 'ready', size_cipher = $3, sha256_cipher = $4, updated_at = now()
             WHERE id = $1 AND vault_id = $2 AND status = 'pending'
             RETURNING id, size_plain, size_cipher, chunk_size, chunk_count, sha256_cipher, created_at`,
            [fileId, vaultId, stats.rows[0].size, sha256Cipher || null]
        );
        await client.query('COMMIT');
        return result.rows[0];
    } catch (err) {
        await client.query('ROLLBACK').catch(() => {});
        throw err;
    } finally {
        client.release();
    }
}

async function getFile(vaultId, fileId) {
    await ensureSchema();
    const result = await getPool().query(
        `SELECT f.id, f.encrypted_meta, f.size_plain, f.size_cipher, f.chunk_size,
                f.chunk_count, f.sha256_cipher, f.created_at
         FROM vault_files f JOIN vaults v ON v.id = f.vault_id
         WHERE f.id = $1 AND f.vault_id = $2 AND f.status = 'ready'`,
        [fileId, vaultId]
    );
    return result.rows[0] || null;
}

async function getChunk(vaultId, fileId, index) {
    await ensureSchema();
    const result = await getPool().query(
        `SELECT c.data
         FROM vault_chunks c
         JOIN vault_files f ON f.id = c.file_id
         JOIN vaults v ON v.id = f.vault_id
         WHERE c.file_id = $1 AND c.chunk_index = $2 AND f.vault_id = $3
           AND f.status = 'ready' AND v.id = $3`,
        [fileId, index, vaultId]
    );
    return result.rows[0]?.data || null;
}

async function updateFileMeta(vaultId, fileId, encryptedMeta) {
    await ensureSchema();
    const result = await getPool().query(
        `UPDATE vault_files SET encrypted_meta = $3, updated_at = now()
         WHERE id = $1 AND vault_id = $2 AND status = 'ready'`,
        [fileId, vaultId, encryptedMeta]
    );
    return result.rowCount > 0;
}

async function deleteFile(vaultId, fileId) {
    await ensureSchema();
    const result = await getPool().query(
        'DELETE FROM vault_files WHERE id = $1 AND vault_id = $2',
        [fileId, vaultId]
    );
    return result.rowCount > 0;
}

async function close() {
    if (pool) {
        const current = pool;
        pool = null;
        schemaPromise = null;
        await current.end().catch(() => {});
    }
}

module.exports = {
    isConfigured,
    maxFileBytes,
    quotaBytes,
    getVault,
    ensureVault,
    listFiles,
    listFolders,
    createFolder,
    updateFolderMeta,
    deleteFolder,
    createFile,
    putChunk,
    finalizeFile,
    getFile,
    getChunk,
    updateFileMeta,
    deleteFile,
    close,
};

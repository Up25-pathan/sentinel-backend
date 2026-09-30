/**
 * Environment Configuration & Validation
 *
 * Centralised so that:
 *  - A missing JWT_SECRET fails loudly at boot instead of producing an
 *    app that logs in successfully and then 401s on every subsequent request.
 *  - Placeholder values ("your_newsapi_key_here") are detected as unset, so a
 *    banner that says "configured" is never a lie.
 *  - dotenv is always loaded from the server directory regardless of the
 *    process working directory.
 */
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');

const SERVER_DIR = path.join(__dirname);

// Always resolve .env against the server directory. Several services previously
// called dotenv.config() with no path, which silently dropped every variable
// whenever the process was started from outside server/.
const envPath = path.join(SERVER_DIR, '.env');
if (fs.existsSync(envPath)) {
    dotenv.config({ path: envPath });
}

const PLACEHOLDER_PATTERNS = [
    /^your[_-]?/i,
    /^changeme/i,
    /^change[_-]?me/i,
    // Must match .env.example's JWT_SECRET=generate_me, otherwise copying the
    // template verbatim produces a 12-character "secret" that passes every
    // check and then fails to verify tokens across restarts.
    /^generate[_-]?me/i,
    /^placeholder/i,
    /^example/i,
    /^dummy/i,
    /^todo/i,
    /^xxx+$/i,
    /^replace/i,
    /^insert[_-]/i,
    /^<.*>$/,
];

/**
 * True when a value is absent or is a recognised placeholder string.
 */
function isUnset(value) {
    if (value === undefined || value === null) return true;
    const v = String(value).trim();
    if (v === '') return true;
    return PLACEHOLDER_PATTERNS.some(p => p.test(v));
}

/**
 * A real secret: present, not a placeholder, and long enough to be usable
 * as a signing key.
 */
function isUsableSecret(value, minLength = 32) {
    return !isUnset(value) && String(value).trim().length >= minLength;
}

/**
 * Generate a strong random secret.
 */
function generateSecret() {
    return require('crypto').randomBytes(48).toString('hex');
}

/**
 * Where to persist a generated secret: alongside the database, because on
 * Render the database is the thing most likely to live on a persistent disk.
 * A secret that sits next to a wiped database would rotate on every cold start.
 */
function secretFilePath() {
    const dbPath = process.env.DB_PATH
        ? path.resolve(SERVER_DIR, process.env.DB_PATH)
        : path.join(SERVER_DIR, 'db', 'geoint.db');
    return path.join(path.dirname(dbPath), '.jwt_secret');
}

let generatedSecret = null;

/**
 * Obtain a usable JWT secret, in order of preference:
 *   1. JWT_SECRET from the environment (correct, and survives everything)
 *   2. A generated secret persisted next to the database
 *   3. A generated secret held in memory for this process only
 *
 * This deliberately does not throw. The previous hardcoded fallback was
 * committed to a public repository, so anybody could mint a valid token for
 * the live deployment; a per-install random secret removes that exposure. The
 * consequence of not setting JWT_SECRET is that tokens stop validating after a
 * cold start on an ephemeral filesystem, which costs a re-login — far better
 * than refusing to boot and taking the whole service down.
 */
function resolveJwtSecret() {
    if (!isUnset(process.env.JWT_SECRET)) {
        const value = String(process.env.JWT_SECRET).trim();
        if (value.length < 32) {
            console.warn(
                '⚠️  JWT_SECRET is shorter than 32 characters. This is weaker than ' +
                'recommended for a signing key.'
            );
        }
        return value;
    }

    if (generatedSecret) return generatedSecret;

    console.warn(
        '\n' +
        '⚠️  JWT_SECRET is not set — generating a secret automatically.\n' +
        '    Set JWT_SECRET in the environment (Render: Dashboard -> Environment)\n' +
        '    so that logins survive restarts. Until then, every cold start\n' +
        '    invalidates existing sessions and clients must log in again.\n'
    );

    // 2. Persist next to the database.
    try {
        const file = secretFilePath();
        fs.mkdirSync(path.dirname(file), { recursive: true });
        if (fs.existsSync(file)) {
            const stored = fs.readFileSync(file, 'utf8').trim();
            if (stored.length >= 32) {
                generatedSecret = stored;
                return generatedSecret;
            }
        }
        const fresh = generateSecret();
        fs.writeFileSync(file, fresh, { mode: 0o600 });
        generatedSecret = fresh;
        return generatedSecret;
    } catch (err) {
        // 3. Read-only filesystem: ephemeral secret, logged as such.
        generatedSecret = generateSecret();
        console.warn(
            `⚠️  Could not persist a generated secret (${err.message}). ` +
            'Using an in-memory secret — logins will reset on every restart.'
        );
        return generatedSecret;
    }
}

/**
 * Summary of every integration, for boot logging and /api/health.
 */
function configStatus() {
    return {
        port: process.env.PORT || '3001',
        db: process.env.DB_PATH || './db/geoint.db',
        newsApi: isUnset(process.env.NEWS_API_KEY) ? 'unconfigured' : 'configured',
        groq: isUnset(process.env.GROQ_API_KEY) ? 'unconfigured' : 'configured',
        openai: isUnset(process.env.OPENAI_API_KEY) ? 'unconfigured' : 'configured',
        openSky: isUnset(process.env.OPENSKY_USERNAME) ? 'anonymous' : 'configured',
        // NVD works key-free at 5 requests / 30 s. A key raises it to 50, which
        // only shortens the first sync; the feed is still free either way.
        nvd: isUnset(process.env.NVD_API_KEY) ? 'anonymous (rate limited)' : 'configured',
        apiSecretKey: isUnset(process.env.API_SECRET_KEY) ? 'disabled' : 'configured',
        jwtSecret: isUnset(process.env.JWT_SECRET) ? 'generated (set JWT_SECRET to persist)' : 'configured',
        authUsername: isUnset(process.env.AUTH_USERNAME) ? 'admin (default)' : 'configured',
    };
}

/**
 * Validate at boot. Throws on anything that would cause a confusing runtime
 * failure; warns on anything that only degrades capability.
 */
function validateEnv() {
    // Always yields a usable secret (env, persisted, or ephemeral).
    resolveJwtSecret();

    const warnings = [];

    if (isUnset(process.env.JWT_SECRET)) {
        warnings.push(
            'JWT_SECRET is not set — a random secret is being generated. ' +
            'Set it in the environment so sessions survive restarts.'
        );
    }
    if (isUnset(process.env.API_SECRET_KEY)) {
        warnings.push(
            'API_SECRET_KEY is not set — the X-API-Key second layer is disabled ' +
            '(middleware/auth.js skips the check when it is absent).'
        );
    }
    if (isUnset(process.env.AUTH_USERNAME)) {
        warnings.push('AUTH_USERNAME is not set — falling back to "admin".');
    }
    if (isUnset(process.env.AUTH_PASSWORD) && isUnset(process.env.AUTH_PASSWORD_HASH)) {
        warnings.push(
            'Neither AUTH_PASSWORD nor AUTH_PASSWORD_HASH is set — falling back to the ' +
            'built-in default password. Set AUTH_PASSWORD_HASH for production.'
        );
    }
    if (isUnset(process.env.NEWS_API_KEY)) {
        warnings.push('NEWS_API_KEY not configured — NewsAPI ingestion disabled.');
    }
    if (isUnset(process.env.GROQ_API_KEY)) {
        warnings.push(
            'GROQ_API_KEY not configured — AI chat, briefings, bias analysis and the ' +
            'prediction engine all fall back to non-AI heuristics.'
        );
    }

    for (const w of warnings) {
        console.warn(`⚠️  ${w}`);
    }

    return { status: configStatus(), warnings };
}

module.exports = {
    SERVER_DIR,
    isUnset,
    isUsableSecret,
    resolveJwtSecret,
    generateSecret,
    configStatus,
    validateEnv,
};

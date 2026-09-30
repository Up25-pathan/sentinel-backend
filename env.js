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

const JWT_FALLBACK = 'default-dev-secret-change-in-production';

/**
 * Resolve the JWT secret, or throw.
 *
 * routes/auth.js signs with `JWT_SECRET || fallback` while middleware/auth.js
 * verifies with `JWT_SECRET` and no fallback. If JWT_SECRET is unset, login
 * succeeds and every authenticated request then fails. Failing here removes
 * that class of silent lockout entirely.
 */
function resolveJwtSecret() {
    if (isUnset(process.env.JWT_SECRET)) {
        throw new Error(
            '\n' +
            '='.repeat(63) + '\n' +
            'FATAL: JWT_SECRET is not configured — refusing to start.\n' +
            '='.repeat(63) + '\n' +
            'Without it, login would issue tokens that no request could verify,\n' +
            'producing an app that accepts credentials then 401s on everything.\n' +
            '\n' +
            'To fix:\n' +
            '  Local:   add JWT_SECRET=<random 64+ chars> to server/.env\n' +
            '  Render:  Dashboard -> your service -> Environment -> add\n' +
            '           JWT_SECRET, then redeploy.\n' +
            '\n' +
            'Generate one with:\n' +
            '  node -e "console.log(require(\'crypto\').randomBytes(48).toString(\'hex\'))"\n' +
            '='.repeat(63)
        );
    }
    if (!isUsableSecret(process.env.JWT_SECRET, 32)) {
        console.warn(
            '⚠️  JWT_SECRET is shorter than 32 characters. This is weaker than recommended ' +
            'for a signing key.'
        );
    }
    return String(process.env.JWT_SECRET).trim();
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
        apiSecretKey: isUnset(process.env.API_SECRET_KEY) ? 'disabled' : 'configured',
        jwtSecret: isUnset(process.env.JWT_SECRET) ? 'unconfigured' : 'configured',
        authUsername: isUnset(process.env.AUTH_USERNAME) ? 'admin (default)' : 'configured',
    };
}

/**
 * Validate at boot. Throws on anything that would cause a confusing runtime
 * failure; warns on anything that only degrades capability.
 */
function validateEnv() {
    // Hard requirement — throws.
    resolveJwtSecret();

    const warnings = [];

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
    JWT_FALLBACK,
    isUnset,
    isUsableSecret,
    resolveJwtSecret,
    configStatus,
    validateEnv,
};

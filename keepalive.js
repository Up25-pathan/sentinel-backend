/**
 * Keep-Alive Script for Render Deployment
 * Pings the server's health endpoint every 5 minutes to prevent
 * Render's free tier from spinning down after inactivity.
 *
 * Usage: node keepalive.js
 * Optional: HEARTBEAT_URL env var to override the target
 */
const https = require('https');
const http = require('http');

const TARGET_URL = process.env.HEARTBEAT_URL || 'https://sentinel-backend-oc7g.onrender.com/api/health';
const INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

function ping() {
    const url = new URL(TARGET_URL);
    const lib = url.protocol === 'https:' ? https : http;

    const req = lib.get(url, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
            const now = new Date().toISOString();
            console.log(`[${now}] Heartbeat ${res.statusCode} — ${TARGET_URL}`);
        });
    });

    req.on('error', (err) => {
        const now = new Date().toISOString();
        console.error(`[${now}] Heartbeat FAILED: ${err.message}`);
    });

    req.end();
}

console.log(`Heartbeat started — pinging ${TARGET_URL} every ${INTERVAL_MS / 1000}s`);
ping();
setInterval(ping, INTERVAL_MS);

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\nHeartbeat stopped.');
    process.exit(0);
});

process.on('SIGTERM', () => {
    process.exit(0);
});

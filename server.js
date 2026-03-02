/**
 * Geopolitical Intelligence System — Backend Server
 * Express API server with intelligence pipeline
 */
const express = require('express');
const cors = require('cors');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const { getDb, closeDb } = require('./db');
const { authMiddleware, apiKeyMiddleware, securityHeaders } = require('./middleware/auth');
const { startScheduler } = require('./scheduler');

// Route imports
const authRoutes = require('./routes/auth');
const eventRoutes = require('./routes/events');
const alertRoutes = require('./routes/alerts');
const mapRoutes = require('./routes/map');
const watchlistsRoutes = require('./routes/watchlists');
const intelligenceRoutes = require('./routes/intelligence');
const osintRoutes = require('./routes/osint');
const darkwebRoutes = require('./routes/darkweb');

const rateLimit = require('express-rate-limit');

const app = express();
const PORT = process.env.PORT || 3001;

// ─── Rate Limiting ─────────────────────────────────────────────
const generalLimiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100, // 100 requests per 15 min per IP
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests, please try again later.' }
});

const authLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 10, // 10 login attempts per 15 min
    message: { error: 'Too many login attempts. Try again in 15 minutes.' }
});

// ─── Middleware ─────────────────────────────────────────────────
app.use(cors());
app.use(express.json());
app.use(generalLimiter);
app.use(securityHeaders);
app.use(apiKeyMiddleware);

// ─── Health Check (no auth) ────────────────────────────────────
app.get('/api/health', (req, res) => {
    const db = getDb();
    const eventCount = db.prepare('SELECT COUNT(*) as count FROM events').get();
    const alertCount = db.prepare('SELECT COUNT(*) as count FROM alerts WHERE is_read = 0').get();

    res.json({
        status: 'ok',
        timestamp: new Date().toISOString(),
        events: eventCount.count,
        unread_alerts: alertCount.count,
        version: '1.0.0'
    });
});

// ─── Auth Routes (no auth middleware) ──────────────────────────
app.use('/api/auth', authLimiter, authRoutes);

// ─── Protected Routes ──────────────────────────────────────────
app.use('/api/events', authMiddleware, eventRoutes);
app.use('/api/alerts', authMiddleware, alertRoutes);
app.use('/api/map', authMiddleware, mapRoutes);
app.use('/api/watchlists', authMiddleware, watchlistsRoutes);
app.use('/api/intelligence', authMiddleware, intelligenceRoutes);
app.use('/api/osint', authMiddleware, osintRoutes);
app.use('/api/darkweb', authMiddleware, darkwebRoutes);

// ─── Export/Backup Route ───────────────────────────────────────
const { exportAll } = require('./services/export');
app.get('/api/export', authMiddleware, (req, res) => {
    try {
        const days = parseInt(req.query.days) || 30;
        const data = exportAll(days);
        res.json(data);
    } catch (err) {
        console.error('Export error:', err);
        res.status(500).json({ error: 'Export failed' });
    }
});

// ─── 404 Handler ───────────────────────────────────────────────
app.use((req, res) => {
    res.status(404).json({ error: 'Endpoint not found' });
});

// ─── Error Handler ─────────────────────────────────────────────
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({ error: 'Internal server error' });
});

// ─── Start Server ──────────────────────────────────────────────
function start() {
    // Initialize database
    getDb();

    app.listen(PORT, '0.0.0.0', () => {
        console.log(`\n${'═'.repeat(55)}`);
        console.log(`  🌍 Sentinel Intelligence Server`);
        console.log(`  📡 Running on http://localhost:${PORT}`);
        console.log(`  🔒 Auth: ${process.env.AUTH_USERNAME || 'admin'}`);
        console.log(`  💾 DB: ${process.env.DB_PATH || './db/geoint.db'}`);
        console.log(`  📰 NewsAPI: ${process.env.NEWS_API_KEY ? '✅ configured' : '❌ not set'}`);
        console.log(`  🧠 Groq AI: ${process.env.GROQ_API_KEY ? '✅ configured' : '❌ not set (using fallback)'}`);
        console.log(`${'═'.repeat(55)}\n`);

        // Start the intelligence scheduler
        startScheduler();
    });
}

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down...');
    closeDb();
    process.exit(0);
});

process.on('SIGTERM', () => {
    closeDb();
    process.exit(0);
});

start();

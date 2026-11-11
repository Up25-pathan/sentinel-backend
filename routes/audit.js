const express = require('express');
const { getLatestLogs, logAction } = require('../services/audit-log');
const { clampInt } = require('../lib/query');
const router = express.Router();

// GET /api/audit — Recent audit log entries (optionally POST to record actions)
router.get('/', (req, res) => {
    try {
        const limit = clampInt(req.query.limit, { min: 1, max: 500, fallback: 100 });
        const logs = getLatestLogs(limit);
        res.json({ logs });
    } catch (err) {
        console.error('Audit route error:', err);
        res.status(500).json({ error: 'Failed to load audit log' });
    }
});

// POST /api/audit — Record a user-initiated action into the shared audit log.
//
// `action` used to be an arbitrary caller-supplied string, truncated only by
// length. Any admin could therefore forge entries indistinguishable from real
// system records — including back-dated-looking AUTH_LOGIN or SYSTEM_START rows
// — inside the very table the product presents as a tamper-evident trail. Client
// reporting is now restricted to a closed set of user action types; genuine
// server-side events (AUTH_LOGIN, SYSTEM_START, INGEST, ...) are written by the
// server through logAction() directly and are not reachable over HTTP.
const CLIENT_REPORTABLE_ACTIONS = new Set([
    'USER_LOGIN',
    'USER_LOGOUT',
    'USER_EXPORT',
    'USER_VIEW_SENSITIVE_ASSET',
    'USER_UPDATE_VULNERABILITY_DB',
    'USER_SENTINEL_ACTION',
]);

router.post('/', (req, res) => {
    try {
        const action = req.body ? String(req.body.action || '').trim() : '';
        const details = req.body ? String(req.body.details || '').trim() : '';

        if (!action) {
            return res.status(400).json({ error: 'action is required' });
        }

        const upper = action.toUpperCase();
        if (!CLIENT_REPORTABLE_ACTIONS.has(upper)) {
            return res.status(400).json({
                error: 'Unsupported action type',
                allowed: [...CLIENT_REPORTABLE_ACTIONS],
            });
        }

        // Attribute the entry to the authenticated caller rather than trusting
        // whatever identity the request body claims.
        const actor = req.user?.username ? ` by '${req.user.username}'` : '';
        logAction(upper, `${details}${actor}`.trim());
        res.status(201).json({ success: true });
    } catch (err) {
        console.error('Audit insert error:', err);
        res.status(500).json({ error: 'Failed to record audit entry' });
    }
});

module.exports = router;
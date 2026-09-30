const express = require('express');
const { getDb } = require('../db');
const { logAction } = require('../services/audit-log');
const router = express.Router();

const ASSET_TYPES = ['Server', 'Domain', 'IP', 'Credential'];
const STATUSES = ['ACTIVE', 'MONITORING', 'COMPROMISED', 'RETIRED'];

// GET /api/assets?type=&search=
router.get('/', (req, res) => {
    try {
        const db = getDb();
        const conditions = [];
        const params = [];

        const type = (req.query.type || '').trim();
        if (type && type !== 'All') {
            conditions.push('type = ?');
            params.push(type);
        }

        const search = (req.query.search || '').trim();
        if (search) {
            conditions.push('(name LIKE ? OR value LIKE ? OR notes LIKE ? OR campaign LIKE ?)');
            const like = `%${search}%`;
            params.push(like, like, like, like);
        }

        const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
        const rows = db.prepare(
            `SELECT id, type, name, value, campaign, status, notes, created FROM assets ${where} ORDER BY created DESC`
        ).all(...params);

        const total = rows.length;
        const servers = rows.filter(r => r.type === 'Server').length;
        const domains = rows.filter(r => r.type === 'Domain').length;
        const creds = rows.filter(r => r.type === 'Credential').length;

        res.json({ assets: rows, stats: { total, servers, domains, creds } });
    } catch (err) {
        console.error('Assets list error:', err);
        res.status(500).json({ error: 'Failed to load assets' });
    }
});

// POST /api/assets
router.post('/', (req, res) => {
    try {
        const db = getDb();
        const body = req.body || {};
        const name = (body.name || '').trim();
        const value = (body.value || '').trim();

        if (!name || !value) {
            return res.status(400).json({ error: 'Name and value are required' });
        }

        const type = ASSET_TYPES.includes(body.type) ? body.type : 'Server';
        const status = STATUSES.includes(String(body.status || '').toUpperCase())
            ? String(body.status).toUpperCase()
            : 'ACTIVE';
        const campaign = (body.campaign || '').trim() || 'None';
        const notes = (body.notes || '').trim() || '';

        const result = db.prepare(
            'INSERT INTO assets (type, name, value, campaign, status, notes, created) VALUES (?, ?, ?, ?, ?, ?, datetime(\'now\'))'
        ).run(type, name, value, campaign, status, notes);

        logAction('ASSET_CREATE', `Added ${type} '${name}'`);
        res.status(201).json({ success: true, id: result.lastInsertRowid });
    } catch (err) {
        console.error('Asset create error:', err);
        res.status(500).json({ error: 'Failed to create asset' });
    }
});

// PUT /api/assets/:id
router.put('/:id', (req, res) => {
    try {
        const db = getDb();
        const id = parseInt(req.params.id);
        const body = req.body || {};
        const name = (body.name || '').trim();
        const value = (body.value || '').trim();

        if (!name || !value) {
            return res.status(400).json({ error: 'Name and value are required' });
        }

        const type = ASSET_TYPES.includes(body.type) ? body.type : 'Server';
        const status = STATUSES.includes(String(body.status || '').toUpperCase())
            ? String(body.status).toUpperCase()
            : 'ACTIVE';
        const campaign = (body.campaign || '').trim() || 'None';
        const notes = (body.notes || '').trim() || '';

        const result = db.prepare(
            'UPDATE assets SET type=?, name=?, value=?, campaign=?, status=?, notes=? WHERE id=?'
        ).run(type, name, value, campaign, status, notes, id);

        if (result.changes === 0) {
            return res.status(404).json({ error: 'Asset not found' });
        }

        logAction('ASSET_UPDATE', `Updated ${type} '${name}'`);
        res.json({ success: true });
    } catch (err) {
        console.error('Asset update error:', err);
        res.status(500).json({ error: 'Failed to update asset' });
    }
});

// DELETE /api/assets/:id
router.delete('/:id', (req, res) => {
    try {
        const db = getDb();
        const id = parseInt(req.params.id);
        const result = db.prepare('DELETE FROM assets WHERE id=?').run(id);
        if (result.changes === 0) {
            return res.status(404).json({ error: 'Asset not found' });
        }
        logAction('ASSET_DELETE', `Deleted asset #${id}`);
        res.json({ success: true });
    } catch (err) {
        console.error('Asset delete error:', err);
        res.status(500).json({ error: 'Failed to delete asset' });
    }
});

module.exports = router;
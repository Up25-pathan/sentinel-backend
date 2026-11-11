const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'geoint.db');

let db;

function getDb() {
    if (!db) {
        // Ensure directory exists
        const dir = path.dirname(DB_PATH.startsWith('./') ? path.join(__dirname, '..', DB_PATH) : DB_PATH);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }

        const resolvedPath = DB_PATH.startsWith('./') ? path.join(__dirname, '..', DB_PATH) : DB_PATH;
        db = new Database(resolvedPath);

        // Enable WAL mode for better concurrency
        db.pragma('journal_mode = WAL');
        db.pragma('foreign_keys = ON');

        // Run schema
        const schema = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf-8');
        db.exec(schema);

        // Run migrations
        try {
            db.exec('ALTER TABLE events ADD COLUMN images_json TEXT;');
        } catch (err) {
            // Column may already exist, ignore
        }

        console.log('✅ Database initialized at:', resolvedPath);
    }
    return db;
}

function closeDb() {
    if (db) {
        db.close();
        db = null;
        console.log('📦 Database connection closed.');
    }
}

module.exports = { getDb, closeDb };

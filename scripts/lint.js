#!/usr/bin/env node
/**
 * Syntax-check every server source file.
 *
 * The project has no ESLint configuration and no transpiler, so `node --check`
 * is the only automated static check available. It catches the class of mistake
 * that would otherwise only surface at boot time on Render — a typo in a cron
 * job or a feed module that is required lazily on first use.
 *
 *   node scripts/lint.js
 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SKIP = new Set(['node_modules', '.git', 'dist', 'build', 'coverage']);

function walk(dir, out = []) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (SKIP.has(entry.name)) continue;
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(full, out);
        else if (entry.name.endsWith('.js')) out.push(full);
    }
    return out;
}

const files = walk(ROOT);
let failed = 0;

for (const file of files) {
    try {
        execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' });
    } catch (err) {
        failed++;
        console.error(`\n✗ ${path.relative(ROOT, file)}`);
        console.error(String(err.stderr || err.message).trim());
    }
}

console.log(`\n${files.length} files checked, ${failed} failed.`);
process.exit(failed === 0 ? 0 : 1);
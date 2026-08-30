/**
 * Higala Express — Backend Server Entry Point
 * Express + REST API for multi-portal superapp
 */
const express = require('express');
const cors = require('cors');
const path = require('path');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
require('dotenv').config({ path: path.join(__dirname, 'higala-backend', '.env') });

const Database = require('./database/index.js');

const app = express();
const PORT = process.env.PORT || 3000;
const JWT_SECRET = process.env.JWT_SECRET || 'higala_express_secret_key_2026';

// Initialize database
const db = Database.init({ driver: 'memory' });

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'static')));

// Auth middleware
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'Access denied.' });
  try { req.user = jwt.verify(token, JWT_SECRET); next(); }
  catch (err) { return res.status(403).json({ error: 'Invalid token.' }); }
}

// ==================== AUTH ROUTES ====================
app.post('/api/auth/register', async (req, res) => {
  try {
    const { name, email, phone, password, role, barangay } = req.body;
    if (!name || !email || !password) return res.status(400).json({ error: 'Name, email, and password are required.' });
    const store = db.getStore();
    if (store.users.find(u => u.email === email)) return res.status(409).json({ error: 'Email already registered.' });
    const hashedPw = await bcrypt.hash(password, 10);
    const user = { id: `u_${Date.now()}_${Math.random().toString(36).slice(2,8)}`, name, email, phone: phone||'', password: hashedPw, role: role||'customer', barangay: barangay||'Carmen', avatar: '', verified: false, createdAt: new Date().toISOString() };
    store.users.push(user);
    const token = jwt.sign({ id: user.id, role: user.role, email: user.email }, JWT_SECRET, { expiresIn: '7d' });
    res.status(201).json({ ok: true, token, user: { id: user.id, name: user.name, email: user.email, role: user.role } });
  } catch (err) { res.status(500).json({ error: 'Registration failed.' }); }
});

app.post('/api/auth/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    const store = db.getStore();
    const user = store.users.find(u => u.email === email);
    if (!user || !(await bcrypt.compare(password, user.password))) return res.status(401).json({ error: 'Invalid email or password.' });
    const token = jwt.sign({ id: user.id, role: user.role, email: user.email }, JWT_SECRET, { expiresIn: '7d' });
    res.json({ ok: true, token, user: { id: user.id, name: user.name, email: user.email, role: user.role, barangay: user.barangay, phone: user.phone, avatar: user.avatar, vehicleType: user.vehicleType } });
  } catch (err) { res.status(500).json({ error: 'Login failed.' }); }
});

// ==================== USER ROUTES ====================
app.get('/api/user/profile', authenticateToken, (req, res) => {
  const store = db.getStore();
  const user = store.users.find(u => u.id === req.user.id);
  if (!user) return res.status(404).json({ error: 'User not found.' });
  res.json({ id: user.id, name: user.name, email: user.email, phone: user.phone, role: user.role, barangay: user.barangay, avatar: user.avatar, vehicleType: user.vehicleType, verified: user.verified });
});

app.put('/api/user/profile', authenticateToken, async (req, res) => {
  try {
    const store = db.getStore();
    const idx = store.users.findIndex(u => u.id === req.user.id);
    if (idx < 0) return res.status(404).json({ error: 'User not found.' });
    const allowedFields = ['name', 'phone', 'barangay', 'avatar', 'vehicleType'];
    allowedFields.forEach(field => { if (req.body[field] !== undefined) store.users[idx][field] = req.body[field]; });
    if (req.body.password) store.users[idx].password = await bcrypt.hash(req.body.password, 10);
    const user = store.users[idx];
    res.json({ ok: true, user: { id: user.id, name: user.name, email: user.email, phone: user.phone, role: user.role, barangay: user.barangay, avatar: user.avatar, vehicleType: user.vehicleType } });
  } catch (err) { res.status(500).json({ error: 'Profile update failed.' }); }
});

// ==================== DRIVER ROUTES ====================
app.post('/api/driver/apply', authenticateToken, (req, res) => {
  try {
    const store = db.getStore();
    const application = { id: `app_${Date.now()}`, userId: req.user.id, ...req.body, status: 'pending', submittedAt: new Date().toISOString() };
    store.applications.push(application);
    res.status(201).json({ ok: true, application });
  } catch (err) { res.status(500).json({ error: 'Application submission failed.' }); }
});

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), service: 'Higala Express API' });
});

app.listen(PORT, () => {
  console.log(`🚀 Higala Express server running on http://localhost:${PORT}`);
});

module.exports = app;

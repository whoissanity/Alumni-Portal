// Auth routes — register, login, me

const router = require('express').Router();
const bcrypt = require('bcryptjs');
const jwt    = require('jsonwebtoken');
const { User } = require('../models');
const { auth } = require('../middleware/auth');

function signToken(user) {
  return jwt.sign(
    { id: user.id, role: user.role },
    process.env.JWT_SECRET,
    { expiresIn: '7d' }
  );
}

// Sanitise user object for JSON responses (never leak password_hash)
function safeUser(u) {
  const obj = u.toJSON ? u.toJSON() : { ...u };
  delete obj.password_hash;
  return obj;
}

// POST /api/auth/register
router.post('/register', async (req, res) => {
  try {
    const { name, email, password, role } = req.body;

    if (!name || !email || !password) {
      return res.status(400).json({ error: 'All fields are required.' });
    }
    if (password.length < 6) {
      return res.status(400).json({ error: 'Password must be at least 6 characters.' });
    }
    if (!['student', 'alumni'].includes(role)) {
      return res.status(400).json({ error: 'Role must be student or alumni.' });
    }

    // Duplicate email check
    const existing = await User.findOne({ where: { email: email.toLowerCase() } });
    if (existing) {
      return res.status(409).json({ error: 'Email already registered.' });
    }

    const password_hash = await bcrypt.hash(password, 10);
    const is_verified = role === 'student'; // alumni pending by default

    const user = await User.create({
      username: name.trim(),
      email: email.trim().toLowerCase(),
      password_hash,
      role,
      is_verified,
    });

    return res.status(201).json({
      message: 'Registration successful! Please log in.',
      user: safeUser(user),
    });
  } catch (err) {
    console.error('Register error:', err);
    return res.status(500).json({ error: 'Server error during registration.' });
  }
});

// POST /api/auth/login
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Please enter both email and password.' });
    }

    const user = await User.findOne({ where: { email: email.trim().toLowerCase() } });
    if (!user) {
      return res.status(401).json({ error: 'Invalid email or password.' });
    }

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid email or password.' });
    }

    // Block banned users
    if (user.is_banned) {
      return res.status(403).json({ error: 'Your account has been banned.' });
    }

    // Block unverified alumni
    if (user.role === 'alumni' && !user.is_verified) {
      return res.status(403).json({
        error: 'Your account is pending admin verification. You cannot log in yet.',
      });
    }

    const token = signToken(user);
    return res.json({ token, user: safeUser(user) });
  } catch (err) {
    console.error('Login error:', err);
    return res.status(500).json({ error: 'Server error during login.' });
  }
});

// POST /api/auth/admin-login
router.post('/admin-login', async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ error: 'Please enter both email and password.' });
    }

    const user = await User.findOne({ where: { email: email.trim().toLowerCase() } });

    // Don't reveal whether email exists or role doesn't match
    if (!user || user.role !== 'admin') {
      return res.status(401).json({ error: 'Invalid admin credentials.' });
    }

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid admin credentials.' });
    }

    const token = signToken(user);
    return res.json({ token, user: safeUser(user) });
  } catch (err) {
    console.error('Admin login error:', err);
    return res.status(500).json({ error: 'Server error during login.' });
  }
});

// GET /api/auth/me — return current user from JWT
router.get('/me', auth, (req, res) => {
  return res.json({ user: safeUser(req.user) });
});

module.exports = router;

// JWT authentication middleware

const jwt = require('jsonwebtoken');
const { User } = require('../models');

// Verifies JWT and attaches req.user
async function auth(req, res, next) {
  const header = req.headers.authorization;
  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Authentication required.' });
  }
  try {
    const token = header.split(' ')[1];
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    const user = await User.findByPk(payload.id, {
      attributes: { exclude: ['password_hash'] }
    });
    if (!user) return res.status(401).json({ error: 'User not found.' });
    if (user.is_banned) return res.status(403).json({ error: 'Your account has been banned.' });
    if (user.role === 'alumni' && !user.is_verified) {
      return res.status(403).json({ error: 'Your account is pending admin verification.' });
    }
    req.user = user;
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid or expired token.' });
  }
}

// Requires user to be admin
function adminOnly(req, res, next) {
  if (!req.user || req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Access denied. Admins only.' });
  }
  next();
}

// Requires user to be a verified alumni
function verifiedAlumniOnly(req, res, next) {
  if (!req.user || req.user.role !== 'alumni' || !req.user.is_verified) {
    return res.status(403).json({ error: 'Only verified alumni can access this.' });
  }
  next();
}

module.exports = { auth, adminOnly, verifiedAlumniOnly };

// Admin routes — alumni verification, user management, job deletion

const router = require('express').Router();
const { auth, adminOnly } = require('../middleware/auth');
const { User, Job } = require('../models');

// All admin routes require auth + admin role
router.use(auth, adminOnly);

// GET /api/admin/pending-alumni
router.get('/pending-alumni', async (req, res) => {
  const pending = await User.findAll({
    where: { role: 'alumni', is_verified: false },
    attributes: { exclude: ['password_hash'] },
    order: [['created_at', 'DESC']],
  });
  res.json({ pending });
});

// POST /api/admin/alumni/:id/approve
router.post('/alumni/:id/approve', async (req, res) => {
  const user = await User.findByPk(req.params.id);
  if (!user || user.role !== 'alumni' || user.is_verified) {
    return res.status(404).json({ error: 'User not found or already verified.' });
  }
  user.is_verified = true;
  await user.save();
  res.json({ message: `Alumni ${user.username} has been verified.` });
});

// POST /api/admin/alumni/:id/reject
router.post('/alumni/:id/reject', async (req, res) => {
  const user = await User.findByPk(req.params.id);
  if (!user || user.role !== 'alumni' || user.is_verified) {
    return res.status(404).json({ error: 'User not found or not pending.' });
  }
  const name = user.username;
  await user.destroy();
  res.json({ message: `Alumni ${name} has been removed.` });
});

// GET /api/admin/users — list all non-admin users
router.get('/users', async (req, res) => {
  const users = await User.findAll({
    where: { role: ['student', 'alumni'] },
    attributes: { exclude: ['password_hash'] },
    order: [['created_at', 'DESC']],
  });
  res.json({ users });
});

// POST /api/admin/users/:id/ban
router.post('/users/:id/ban', async (req, res) => {
  const user = await User.findByPk(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found.' });
  if (user.role === 'admin') return res.status(400).json({ error: 'Cannot ban another admin.' });
  user.is_banned = true;
  await user.save();
  res.json({ message: `${user.username} has been banned.` });
});

// POST /api/admin/users/:id/unban
router.post('/users/:id/unban', async (req, res) => {
  const user = await User.findByPk(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found.' });
  user.is_banned = false;
  await user.save();
  res.json({ message: `${user.username} has been unbanned.` });
});

// DELETE /api/admin/jobs/:id
router.delete('/jobs/:id', async (req, res) => {
  const job = await Job.findByPk(req.params.id);
  if (!job) return res.status(404).json({ error: 'Job not found.' });
  const title = job.title;
  await job.destroy();
  res.json({ message: `Job posting '${title}' has been removed.` });
});

module.exports = router;

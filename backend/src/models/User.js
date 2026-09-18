const { DataTypes } = require('sequelize');
const sequelize = require('../db');

const User = sequelize.define('User', {
  id:            { type: DataTypes.INTEGER, primaryKey: true, autoIncrement: true },
  username:      { type: DataTypes.STRING(80), allowNull: false },
  email:         { type: DataTypes.STRING(120), allowNull: false, unique: true },
  password_hash: { type: DataTypes.STRING(256), allowNull: false },
  role:          { type: DataTypes.ENUM('student', 'alumni', 'admin'), allowNull: false, defaultValue: 'student' },
  is_verified:   { type: DataTypes.BOOLEAN, defaultValue: false },
  is_banned:     { type: DataTypes.BOOLEAN, defaultValue: false },
  bio:              { type: DataTypes.TEXT },
  department:       { type: DataTypes.STRING(120) },
  batch:            { type: DataTypes.STRING(20) },
  current_job_title:{ type: DataTypes.STRING(120) },
  company:          { type: DataTypes.STRING(120) },
  resume_filename:  { type: DataTypes.STRING(255) },
}, {
  tableName: 'users',
  timestamps: true,
  createdAt: 'created_at',
  updatedAt: false,
});

module.exports = User;

const { DataTypes } = require('sequelize');
const sequelize = require('../db');

const Job = sequelize.define('Job', {
  id:          { type: DataTypes.INTEGER, primaryKey: true, autoIncrement: true },
  title:       { type: DataTypes.STRING(120), allowNull: false },
  description: { type: DataTypes.TEXT, allowNull: false },
  job_type:    { type: DataTypes.ENUM('job', 'internship'), allowNull: false },
  location:    { type: DataTypes.STRING(120) },
  company:     { type: DataTypes.STRING(120) },
  posted_by:   { type: DataTypes.INTEGER, allowNull: false },
}, {
  tableName: 'jobs',
  timestamps: true,
  createdAt: 'created_at',
  updatedAt: false,
});

module.exports = Job;

const { DataTypes } = require('sequelize');
const sequelize = require('../db');

const MentorshipRequest = sequelize.define('MentorshipRequest', {
  id:         { type: DataTypes.INTEGER, primaryKey: true, autoIncrement: true },
  student_id: { type: DataTypes.INTEGER, allowNull: false },
  mentor_id:  { type: DataTypes.INTEGER, allowNull: false },
  message:    { type: DataTypes.TEXT, allowNull: false },
  status:     { type: DataTypes.ENUM('pending', 'accepted', 'rejected'), defaultValue: 'pending' },
}, {
  tableName: 'mentorship_requests',
  timestamps: true,
  createdAt: 'created_at',
  updatedAt: false,
});

module.exports = MentorshipRequest;

const { DataTypes } = require('sequelize');
const sequelize = require('../db');

const Message = sequelize.define('Message', {
  id:          { type: DataTypes.INTEGER, primaryKey: true, autoIncrement: true },
  sender_id:   { type: DataTypes.INTEGER, allowNull: false },
  receiver_id: { type: DataTypes.INTEGER, allowNull: false },
  body:        { type: DataTypes.TEXT, allowNull: false },
  is_read:     { type: DataTypes.BOOLEAN, defaultValue: false },
  sent_at:     { type: DataTypes.DATE, defaultValue: DataTypes.NOW },
}, {
  tableName: 'messages',
  timestamps: false,
});

module.exports = Message;

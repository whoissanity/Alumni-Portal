// Central model loader — sets up all associations

const User               = require('./User');
const Job                = require('./Job');
const MentorshipRequest  = require('./MentorshipRequest');
const Message            = require('./Message');

// --- Associations ---

// User ↔ Job
User.hasMany(Job, { foreignKey: 'posted_by', as: 'jobs' });
Job.belongsTo(User, { foreignKey: 'posted_by', as: 'author' });

// User ↔ MentorshipRequest
User.hasMany(MentorshipRequest, { foreignKey: 'student_id', as: 'mentorshipsSent' });
User.hasMany(MentorshipRequest, { foreignKey: 'mentor_id',  as: 'mentorshipsReceived' });
MentorshipRequest.belongsTo(User, { foreignKey: 'student_id', as: 'student' });
MentorshipRequest.belongsTo(User, { foreignKey: 'mentor_id',  as: 'mentor' });

// User ↔ Message
User.hasMany(Message, { foreignKey: 'sender_id',   as: 'messagesSent' });
User.hasMany(Message, { foreignKey: 'receiver_id', as: 'messagesReceived' });
Message.belongsTo(User, { foreignKey: 'sender_id',   as: 'sender' });
Message.belongsTo(User, { foreignKey: 'receiver_id', as: 'receiver' });

module.exports = { User, Job, MentorshipRequest, Message };

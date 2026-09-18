# SQLAlchemy database models for the Alumni Network & Career Portal
# Entities defined per Section 6.1 of the SRS.

from datetime import datetime, timezone

from flask_login import UserMixin
from .extensions import db, bcrypt


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(db.Model, UserMixin):
    """Platform user — student, alumni, or admin."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.Enum("student", "alumni", "admin", name="user_role"),
        nullable=False,
        default="student",
    )
    is_verified = db.Column(db.Boolean, default=False)  # alumni verification
    is_banned = db.Column(db.Boolean, default=False)    # admin ban flag
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Profile fields (FR-10)
    bio = db.Column(db.Text)
    department = db.Column(db.String(120))
    batch = db.Column(db.String(20)) # or graduation_year
    
    # Alumni specific fields
    current_job_title = db.Column(db.String(120))
    company = db.Column(db.String(120))
    
    # Student specific fields
    resume_filename = db.Column(db.String(255))

    # Relationships
    jobs_posted = db.relationship("Job", back_populates="author", lazy="dynamic")
    job_applications = db.relationship(
        "JobApplication", back_populates="student", lazy="dynamic"
    )
    mentorship_requests_sent = db.relationship(
        "MentorshipRequest",
        foreign_keys="MentorshipRequest.student_id",
        back_populates="student",
        lazy="dynamic",
    )
    mentorship_requests_received = db.relationship(
        "MentorshipRequest",
        foreign_keys="MentorshipRequest.mentor_id",
        back_populates="mentor",
        lazy="dynamic",
    )
    events_created = db.relationship(
        "Event", back_populates="creator", lazy="dynamic"
    )
    rsvps = db.relationship(
        "EventRSVP", back_populates="user", lazy="dynamic"
    )
    notifications = db.relationship(
        "Notification", back_populates="user", lazy="dynamic"
    )
    messages_sent = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        lazy="dynamic",
    )
    messages_received = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        lazy="dynamic",
    )
    success_stories = db.relationship(
        "SuccessStory", back_populates="author", lazy="dynamic"
    )
    resume_reviews = db.relationship(
        "ResumeReview", back_populates="student", lazy="dynamic"
    )

    # ---- Password helpers ----

    def set_password(self, password: str) -> None:
        """Hash *password* with bcrypt and store in password_hash."""
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """Return True if *password* matches the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    # Flask-Login compatibility
    def get_id(self):
        return str(self.id)

    # is_active: students and admins are always active;
    # alumni must be verified first. Banned users are never active.
    @property
    def is_active(self):
        if self.is_banned:
            return False
        if self.role == "alumni":
            return bool(self.is_verified)
        return True


# ---------------------------------------------------------------------------
# Job / Internship
# ---------------------------------------------------------------------------

class Job(db.Model):
    """Job or internship posting by a verified alumni."""

    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    job_type = db.Column(
        db.Enum("job", "internship", name="job_type"), nullable=False
    )
    location = db.Column(db.String(120))
    company = db.Column(db.String(120))
    posted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    author = db.relationship("User", back_populates="jobs_posted")
    applications = db.relationship(
        "JobApplication", back_populates="job", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Job {self.title}>"


# ---------------------------------------------------------------------------
# Mentorship
# ---------------------------------------------------------------------------

class MentorshipRequest(db.Model):
    """Mentorship request between a student and an alumni."""

    __tablename__ = "mentorship_requests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum("pending", "accepted", "rejected", name="mentorship_status"),
        default="pending",
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    student = db.relationship(
        "User", foreign_keys=[student_id], back_populates="mentorship_requests_sent"
    )
    mentor = db.relationship(
        "User", foreign_keys=[mentor_id], back_populates="mentorship_requests_received"
    )

    def __repr__(self):
        return f"<MentorshipRequest id={self.id} status={self.status}>"


# ---------------------------------------------------------------------------
# Event / RSVP
# ---------------------------------------------------------------------------

class Event(db.Model):
    """University event (webinar, meetup, etc.)."""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(120))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    creator = db.relationship("User", back_populates="events_created")
    rsvps = db.relationship(
        "EventRSVP", back_populates="event", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Event {self.title}>"


class EventRSVP(db.Model):
    """RSVP record for an event."""

    __tablename__ = "event_rsvps"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    event = db.relationship("Event", back_populates="rsvps")
    user = db.relationship("User", back_populates="rsvps")

    __table_args__ = (
        db.UniqueConstraint("event_id", "user_id", name="uq_event_user_rsvp"),
    )

    def __repr__(self):
        return f"<EventRSVP event={self.event_id} user={self.user_id}>"


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class Message(db.Model):
    """Direct message between two users."""

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    sent_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    sender = db.relationship(
        "User", foreign_keys=[sender_id], back_populates="messages_sent"
    )
    receiver = db.relationship(
        "User", foreign_keys=[receiver_id], back_populates="messages_received"
    )

    @property
    def content(self):
        return self.body

    @content.setter
    def content(self, value):
        self.body = value

    @property
    def timestamp(self):
        return self.sent_at

    def __repr__(self):
        return f"<Message id={self.id} from={self.sender_id} to={self.receiver_id}>"


# ---------------------------------------------------------------------------
# Success Story
# ---------------------------------------------------------------------------

class SuccessStory(db.Model):
    """Success story submitted by an alumni, moderated by admin."""

    __tablename__ = "success_stories"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_published = db.Column(db.Boolean, default=False)  # moderation flag
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    author = db.relationship("User", back_populates="success_stories")

    def __repr__(self):
        return f"<SuccessStory {self.title}>"


# ---------------------------------------------------------------------------
# Job Application
# ---------------------------------------------------------------------------

class JobApplication(db.Model):
    """Tracks a student's application to a job posting."""

    __tablename__ = "job_applications"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.Enum("applied", "reviewed", "rejected", "accepted",
                name="application_status"),
        default="applied",
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    job = db.relationship("Job", back_populates="applications")
    student = db.relationship("User", back_populates="job_applications")

    __table_args__ = (
        db.UniqueConstraint("job_id", "student_id", name="uq_job_student_app"),
    )

    def __repr__(self):
        return f"<JobApplication job={self.job_id} student={self.student_id} status={self.status}>"


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class Notification(db.Model):
    """In-app notification for a user."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    link = db.Column(db.String(500))  # optional URL to redirect on click
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification id={self.id} user={self.user_id} read={self.is_read}>"


# ---------------------------------------------------------------------------
# Resume Review
# ---------------------------------------------------------------------------

class ResumeReview(db.Model):
    """AI resume analysis for a student."""

    __tablename__ = "resume_reviews"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    feedback_json = db.Column(db.Text, nullable=False)  # JSON payload
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    student = db.relationship("User", back_populates="resume_reviews")

    def __repr__(self):
        return f"<ResumeReview id={self.id} student_id={self.student_id} score={self.score}>"

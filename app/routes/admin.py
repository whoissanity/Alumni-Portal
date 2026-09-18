# Admin blueprint — Dashboard, User Management, Reports, and Moderation (FR-34 to FR-37, FR-33)

from datetime import datetime, timedelta, timezone
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user
from sqlalchemy import or_

from app.extensions import db, bcrypt
from app.models import User, Job, MentorshipRequest, Event, SuccessStory, Notification

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator: only users with role='admin' may access the wrapped route."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Access denied. Admins only.", "danger")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)

    return decorated


@admin_bp.route("/")
def admin_root():
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("admin.login"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and current_user.role == 'admin':
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("admin_login.html")

        user = User.query.filter_by(email=email).first()

        if not user or user.role != 'admin' or not bcrypt.check_password_hash(user.password_hash, password):
            flash("Invalid admin credentials.", "danger")
            return render_template("admin_login.html")

        if user.is_banned:
            flash("This admin account is suspended.", "danger")
            return render_template("admin_login.html")

        if not login_user(user):
            flash("Unable to log in as admin.", "danger")
            return render_template("admin_login.html")

        flash("Welcome back, Admin!", "success")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin_login.html")


# ---------------------------------------------------------------------------
# FR-34, FR-35, FR-37: Admin Dashboard & Activity Reports
# ---------------------------------------------------------------------------

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """FR-34 & FR-35: Platform summary stats and FR-37 activity report."""
    # Summary counts
    students_count = User.query.filter_by(role="student").count()
    verified_alumni_count = User.query.filter_by(role="alumni", is_verified=True).count()
    pending_alumni_count = User.query.filter_by(role="alumni", is_verified=False).count()
    active_jobs_count = Job.query.count()
    pending_stories_count = SuccessStory.query.filter_by(is_published=False).count()

    # FR-37: Activity Report Date Range
    from_date_str = request.args.get("from_date", "").strip()
    to_date_str = request.args.get("to_date", "").strip()

    today = datetime.now(timezone.utc).date()
    default_start = today - timedelta(days=30)
    default_end = today

    try:
        start_date = datetime.strptime(from_date_str, "%Y-%m-%d").date() if from_date_str else default_start
    except ValueError:
        start_date = default_start
        from_date_str = start_date.strftime("%Y-%m-%d")

    try:
        end_date = datetime.strptime(to_date_str, "%Y-%m-%d").date() if to_date_str else default_end
    except ValueError:
        end_date = default_end
        to_date_str = end_date.strftime("%Y-%m-%d")

    # Start/End datetime objects for filtering created_at fields
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    # Activity metrics in range
    new_students = User.query.filter(User.role == "student", User.created_at >= start_dt, User.created_at <= end_dt).count()
    new_alumni = User.query.filter(User.role == "alumni", User.created_at >= start_dt, User.created_at <= end_dt).count()
    new_jobs = Job.query.filter(Job.created_at >= start_dt, Job.created_at <= end_dt).count()
    new_mentorship_requests = MentorshipRequest.query.filter(MentorshipRequest.created_at >= start_dt, MentorshipRequest.created_at <= end_dt).count()
    new_events = Event.query.filter(Event.created_at >= start_dt, Event.created_at <= end_dt).count()
    new_stories = SuccessStory.query.filter(SuccessStory.created_at >= start_dt, SuccessStory.created_at <= end_dt).count()

    report_data = {
        "new_students": new_students,
        "new_alumni": new_alumni,
        "new_jobs": new_jobs,
        "new_mentorship_requests": new_mentorship_requests,
        "new_events": new_events,
        "new_stories": new_stories,
        "total_activity": new_students + new_alumni + new_jobs + new_mentorship_requests + new_events + new_stories,
    }

    return render_template(
        "admin_dashboard.html",
        students_count=students_count,
        verified_alumni_count=verified_alumni_count,
        pending_alumni_count=pending_alumni_count,
        active_jobs_count=active_jobs_count,
        pending_stories_count=pending_stories_count,
        report_data=report_data,
        from_date=start_date.strftime("%Y-%m-%d"),
        to_date=end_date.strftime("%Y-%m-%d"),
    )


# ---------------------------------------------------------------------------
# Pending alumni list
# ---------------------------------------------------------------------------

@admin_bp.route("/pending-alumni")
@admin_required
def pending_alumni():
    """List all alumni whose accounts are waiting for verification."""
    pending = User.query.filter_by(role="alumni", is_verified=False).all()
    return render_template("admin_pending_alumni.html", pending=pending)


@admin_bp.route("/approve/<int:user_id>", methods=["POST"])
@admin_required
def approve(user_id):
    """Set is_verified=True on the given alumni account."""
    user = User.query.get(user_id)
    if user and user.role == "alumni" and not user.is_verified:
        user.is_verified = True
        db.session.commit()

        # Send notification to user
        notif = Notification(
            user_id=user.id,
            message="Congratulations! Your DUET Alumni account has been verified by the administrator.",
            link=url_for("profile.profile"),
        )
        db.session.add(notif)
        db.session.commit()

        flash(f"Alumni {user.username} has been verified.", "success")
    else:
        flash("User not found or already verified.", "warning")
    return redirect(request.referrer or url_for("admin.pending_alumni"))


@admin_bp.route("/reject/<int:user_id>", methods=["POST"])
@admin_required
def reject(user_id):
    """Delete the given alumni account."""
    user = User.query.get(user_id)
    if user and user.role == "alumni" and not user.is_verified:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        flash(f"Alumni {username} account request rejected.", "info")
    else:
        flash("User not found or not pending.", "warning")
    return redirect(request.referrer or url_for("admin.pending_alumni"))


# ---------------------------------------------------------------------------
# FR-36: User management — search, filter, pagination, suspend/reactivate, delete
# ---------------------------------------------------------------------------

@admin_bp.route("/users")
@admin_required
def user_list():
    """FR-36: Manage registered users with search, filtering, and pagination."""
    q = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)

    query = User.query.filter(User.role != "admin")

    if q:
        query = query.filter(
            or_(
                User.username.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
            )
        )

    if role_filter in ["student", "alumni"]:
        query = query.filter_by(role=role_filter)

    if status_filter == "verified":
        query = query.filter(User.role == "alumni", User.is_verified == True)
    elif status_filter == "pending":
        query = query.filter(User.role == "alumni", User.is_verified == False)
    elif status_filter == "banned":
        query = query.filter(User.is_banned == True)

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    users = pagination.items

    return render_template(
        "admin_users.html",
        users=users,
        pagination=pagination,
        q=q,
        role_filter=role_filter,
        status_filter=status_filter,
    )


@admin_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def ban_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        flash("Cannot ban another admin.", "danger")
        return redirect(url_for("admin.user_list"))
    user.is_banned = True
    db.session.commit()
    flash(f"{user.username} has been suspended.", "warning")
    return redirect(request.referrer or url_for("admin.user_list"))


@admin_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@admin_required
def unban_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_banned = False
    db.session.commit()
    flash(f"{user.username} has been reactivated.", "success")
    return redirect(request.referrer or url_for("admin.user_list"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    """FR-36: Permanently remove a user account."""
    user = User.query.get_or_404(user_id)
    if user.role == "admin":
        flash("Cannot delete another admin.", "danger")
        return redirect(url_for("admin.user_list"))
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"User account '{username}' has been deleted.", "info")
    return redirect(request.referrer or url_for("admin.user_list"))


# ---------------------------------------------------------------------------
# FR-33: Success Story Moderation
# ---------------------------------------------------------------------------

@admin_bp.route("/stories")
@admin_required
def pending_stories():
    """List all success stories pending admin approval."""
    stories = SuccessStory.query.filter_by(is_published=False).order_by(SuccessStory.created_at.desc()).all()
    published_stories = SuccessStory.query.filter_by(is_published=True).order_by(SuccessStory.created_at.desc()).all()
    return render_template("admin_stories.html", pending_stories=stories, published_stories=published_stories)


@admin_bp.route("/stories/<int:story_id>/approve", methods=["POST"])
@admin_required
def approve_story(story_id):
    story = SuccessStory.query.get_or_404(story_id)
    story.is_published = True
    db.session.commit()

    # Send notification to story author
    notif = Notification(
        user_id=story.author_id,
        message=f"Your success story '{story.title}' has been approved and published!",
        link=url_for("stories.story_detail", story_id=story.id),
    )
    db.session.add(notif)
    db.session.commit()

    flash(f"Story '{story.title}' has been approved and published.", "success")
    return redirect(url_for("admin.pending_stories"))


@admin_bp.route("/stories/<int:story_id>/reject", methods=["POST"])
@admin_required
def reject_story(story_id):
    story = SuccessStory.query.get_or_404(story_id)
    title = story.title
    author_id = story.author_id
    db.session.delete(story)
    db.session.commit()

    # Send notification to story author
    notif = Notification(
        user_id=author_id,
        message=f"Your submitted success story '{title}' was not approved.",
        link=None,
    )
    db.session.add(notif)
    db.session.commit()

    flash(f"Story '{title}' has been rejected and removed.", "info")
    return redirect(url_for("admin.pending_stories"))


# ---------------------------------------------------------------------------
# Student Directory — admin only
# ---------------------------------------------------------------------------

@admin_bp.route("/students")
@admin_required
def student_directory():
    """List all students with search and filter — admin only."""
    selected_dept = request.args.get("department", "").strip()
    selected_batch = request.args.get("batch", "").strip()
    search_name = request.args.get("name", "").strip()
    page = request.args.get("page", 1, type=int)

    query = User.query.filter_by(role="student")

    if selected_dept:
        query = query.filter_by(department=selected_dept)
    if selected_batch:
        query = query.filter_by(batch=selected_batch)
    if search_name:
        query = query.filter(User.username.ilike(f"%{search_name}%"))

    pagination = query.order_by(User.username.asc()).paginate(
        page=page, per_page=12, error_out=False
    )
    student_list = pagination.items

    departments = ["CSE", "CE", "MME", "TE", "EEE"]

    batches = [
        b[0] for b in db.session.query(User.batch)
        .filter(
            User.role == "student",
            User.batch != None,
            User.batch != "",
        )
        .distinct()
        .order_by(User.batch.desc())
        .all()
    ]

    return render_template(
        "admin_student_directory.html",
        student_list=student_list,
        pagination=pagination,
        departments=departments,
        batches=batches,
        selected_dept=selected_dept,
        selected_batch=selected_batch,
        search_name=search_name,
    )


# ---------------------------------------------------------------------------
# Delete a job posting (Admin only)
# ---------------------------------------------------------------------------

@admin_bp.route("/jobs/delete/<int:job_id>", methods=["POST"])
@admin_required
def delete_job(job_id):
    """Delete a job posting that violates guidelines."""
    job = Job.query.get_or_404(job_id)
    title = job.title
    db.session.delete(job)
    db.session.commit()
    flash(f"Job posting '{title}' has been removed by admin.", "info")
    return redirect(url_for("jobs.list_jobs"))

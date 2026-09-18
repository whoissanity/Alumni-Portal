# Mentorship blueprint — FR-21 to FR-24

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import MentorshipRequest, Notification, User
from app.email_utils import send_mentorship_confirmed_emails

mentorship_bp = Blueprint("mentorship", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_not_banned():
    if current_user.is_banned:
        flash("Your account has been banned.", "danger")
        return False
    return True


# ---------------------------------------------------------------------------
# Send a mentorship request (students only) — FR-21
# ---------------------------------------------------------------------------

@mentorship_bp.route("/alumni/<int:alumni_id>/request-mentorship", methods=["POST"])
@login_required
def send_request(alumni_id):
    if not _check_not_banned():
        return redirect(url_for("main.index"))

    if current_user.role != "student":
        flash("Only students can send mentorship requests.", "danger")
        return redirect(url_for("main.index"))

    mentor = User.query.get_or_404(alumni_id)
    if mentor.role != "alumni" or not mentor.is_verified:
        flash("That user is not an eligible mentor.", "danger")
        return redirect(url_for("jobs.list_jobs"))

    if mentor.is_banned:
        flash("This user is not available.", "danger")
        return redirect(url_for("jobs.list_jobs"))

    # Prevent duplicate pending requests
    existing = MentorshipRequest.query.filter_by(
        student_id=current_user.id,
        mentor_id=alumni_id,
        status="pending"
    ).first()
    if existing:
        flash("You already have a pending request with this mentor.", "warning")
        return redirect(url_for("mentorship.alumni_public_profile", alumni_id=alumni_id))

    message = request.form.get("message", "").strip()
    if not message:
        flash("Please include a message with your request.", "danger")
        return redirect(url_for("mentorship.alumni_public_profile", alumni_id=alumni_id))

    req = MentorshipRequest(
        student_id=current_user.id,
        mentor_id=alumni_id,
        message=message,
        status="pending"
    )
    db.session.add(req)
    db.session.commit()
    flash("Mentorship request sent successfully!", "success")
    return redirect(url_for("mentorship.alumni_public_profile", alumni_id=alumni_id))


# ---------------------------------------------------------------------------
# Community User Directory — open to all logged-in users (students, alumni, admins)
# with role filter (Students / Alumni / All), department, batch, and name search.
# ---------------------------------------------------------------------------

@mentorship_bp.route("/users")
@login_required
def user_directory():
    """List all non-admin users with search and role/department/batch filters."""
    if current_user.is_banned:
        flash("Your account has been banned.", "danger")
        return redirect(url_for("main.index"))

    selected_role = request.args.get("role", "").strip()
    selected_dept = request.args.get("department", "").strip()
    selected_batch = request.args.get("batch", "").strip()
    search_name = request.args.get("name", "").strip()
    page = request.args.get("page", 1, type=int)

    # Query non-admin users, active / verified
    query = User.query.filter(User.role != "admin", User.is_banned == False)

    if current_user.role != "admin":
        query = query.filter(
            db.or_(
                User.role == "student",
                db.and_(User.role == "alumni", User.is_verified == True)
            )
        )

    if selected_role in ["student", "alumni"]:
        query = query.filter_by(role=selected_role)

    if selected_dept:
        query = query.filter_by(department=selected_dept)
    if selected_batch:
        query = query.filter_by(batch=selected_batch)
    if search_name:
        query = query.filter(User.username.ilike(f"%{search_name}%"))

    pagination = query.order_by(User.username.asc()).paginate(page=page, per_page=12, error_out=False)
    user_list = pagination.items

    departments = ["CSE", "CE", "MME", "TE", "EEE"]

    batches = [
        b[0] for b in db.session.query(User.batch)
        .filter(User.role != "admin", User.batch != None, User.batch != "")
        .distinct().order_by(User.batch.desc()).all()
    ]

    return render_template(
        "mentorship/user_directory.html",
        user_list=user_list,
        pagination=pagination,
        departments=departments,
        batches=batches,
        selected_role=selected_role,
        selected_dept=selected_dept,
        selected_batch=selected_batch,
        search_name=search_name,
    )


# ---------------------------------------------------------------------------
# Public alumni profile — viewable by any logged-in user
# ---------------------------------------------------------------------------

@mentorship_bp.route("/alumni/<int:alumni_id>")
@login_required
def alumni_public_profile(alumni_id):
    alumni = User.query.get_or_404(alumni_id)
    if alumni.role != "alumni" or not alumni.is_verified:
        flash("Profile not found or alumni is not verified.", "danger")
        return redirect(url_for("mentorship.user_directory"))

    # Check if the current student already sent a pending request
    existing_request = None
    if current_user.role == "student":
        existing_request = MentorshipRequest.query.filter_by(
            student_id=current_user.id,
            mentor_id=alumni_id,
        ).order_by(MentorshipRequest.created_at.desc()).first()

    # Fetch jobs posted by this alumnus
    from app.models import Job
    jobs = Job.query.filter_by(posted_by=alumni_id).order_by(Job.created_at.desc()).all()

    return render_template(
        "mentorship/alumni_profile.html",
        alumni=alumni,
        existing_request=existing_request,
        jobs=jobs
    )


# ---------------------------------------------------------------------------
# My mentorship requests dashboard — FR-24
# ---------------------------------------------------------------------------

@mentorship_bp.route("/mentorship")
@login_required
def dashboard():
    if not _check_not_banned():
        return redirect(url_for("main.index"))

    if current_user.role == "student":
        # Student sees requests they have sent
        pending = MentorshipRequest.query.filter_by(
            student_id=current_user.id, status="pending"
        ).order_by(MentorshipRequest.created_at.desc()).all()
        accepted = MentorshipRequest.query.filter_by(
            student_id=current_user.id, status="accepted"
        ).order_by(MentorshipRequest.created_at.desc()).all()
        rejected = MentorshipRequest.query.filter_by(
            student_id=current_user.id, status="rejected"
        ).order_by(MentorshipRequest.created_at.desc()).all()
        return render_template(
            "mentorship/dashboard.html",
            pending=pending, accepted=accepted, rejected=rejected,
            view="student"
        )

    elif current_user.role == "alumni":
        # Alumni sees requests they have received
        pending = MentorshipRequest.query.filter_by(
            mentor_id=current_user.id, status="pending"
        ).order_by(MentorshipRequest.created_at.desc()).all()
        accepted = MentorshipRequest.query.filter_by(
            mentor_id=current_user.id, status="accepted"
        ).order_by(MentorshipRequest.created_at.desc()).all()
        rejected = MentorshipRequest.query.filter_by(
            mentor_id=current_user.id, status="rejected"
        ).order_by(MentorshipRequest.created_at.desc()).all()
        return render_template(
            "mentorship/dashboard.html",
            pending=pending, accepted=accepted, rejected=rejected,
            view="alumni"
        )

    else:
        flash("Mentorship dashboard is for students and alumni only.", "info")
        return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Accept / Decline a request (alumni only) — FR-22, FR-23
# Sends an in-app Notification to the student on status change.
# ---------------------------------------------------------------------------

@mentorship_bp.route("/mentorship/<int:req_id>/respond", methods=["POST"])
@login_required
def respond(req_id):
    if current_user.role != "alumni":
        flash("Only alumni can respond to mentorship requests.", "danger")
        return redirect(url_for("main.index"))

    req = MentorshipRequest.query.get_or_404(req_id)
    if req.mentor_id != current_user.id:
        flash("You are not authorised to respond to this request.", "danger")
        return redirect(url_for("mentorship.dashboard"))

    action = request.form.get("action")
    if action == "accept":
        req.status = "accepted"
        db.session.commit()
        # Notify student
        notif = Notification(
            user_id=req.student_id,
            message=f"{current_user.username} accepted your mentorship request!",
            link=url_for("mentorship.dashboard"),
        )
        db.session.add(notif)
        db.session.commit()

        send_mentorship_confirmed_emails(req)

        flash(
            f"You accepted {req.student.username}'s mentorship request! "
            "You can now message each other.",
            "success"
        )
    elif action == "decline":
        req.status = "rejected"
        db.session.commit()
        # Notify student
        notif = Notification(
            user_id=req.student_id,
            message=f"{current_user.username} declined your mentorship request.",
            link=url_for("mentorship.dashboard"),
        )
        db.session.add(notif)
        db.session.commit()
        flash(f"You declined {req.student.username}'s mentorship request.", "info")
    else:
        flash("Invalid action.", "danger")

    return redirect(url_for("mentorship.dashboard"))

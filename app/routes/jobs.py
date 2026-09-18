# Jobs blueprint — job/internship board + application tracking

from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Job, JobApplication, Notification
from app.email_utils import send_job_match_emails

jobs_bp = Blueprint("jobs", __name__)


# ---------------------------------------------------------------------------
# Helper to disable caching on HTTP responses
# ---------------------------------------------------------------------------

def _no_cache_response(rendered_template):
    resp = make_response(rendered_template)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ---------------------------------------------------------------------------
# List all jobs — search & filter
# ---------------------------------------------------------------------------

@jobs_bp.route("/jobs")
@login_required
def list_jobs():
    q = request.args.get("q", "").strip()
    job_type = request.args.get("type", "").strip()

    query = Job.query
    if q:
        query = query.filter(
            db.or_(
                Job.title.ilike(f"%{q}%"),
                Job.company.ilike(f"%{q}%"),
                Job.description.ilike(f"%{q}%"),
                Job.location.ilike(f"%{q}%")
            )
        )
    if job_type in ["job", "internship"]:
        query = query.filter_by(job_type=job_type)

    jobs = query.order_by(Job.created_at.desc()).all()
    return render_template("jobs/list.html", jobs=jobs, q=q, selected_type=job_type)


# ---------------------------------------------------------------------------
# Post a new job — verified alumni only
# ---------------------------------------------------------------------------

@jobs_bp.route("/jobs/new", methods=["GET", "POST"])
@login_required
def new_job():
    if current_user.role != "alumni" or not current_user.is_verified:
        flash("Only verified alumni can post jobs.", "danger")
        return redirect(url_for("jobs.list_jobs"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        job_type = request.form.get("job_type", "job").strip()
        location = request.form.get("location", "").strip()
        company = request.form.get("company", "").strip()

        if not title or not description or not job_type:
            flash("Title, description, and job type are required.", "danger")
            return render_template("jobs/new.html", title=title, description=description, job_type=job_type, location=location, company=company)

        job = Job(
            title=title,
            description=description,
            job_type=job_type,
            location=location,
            company=company,
            posted_by=current_user.id
        )
        db.session.add(job)
        db.session.commit()
        send_job_match_emails(job)

        flash("Job posted successfully.", "success")
        return redirect(url_for("jobs.list_jobs"))

    return render_template("jobs/new.html")


# ---------------------------------------------------------------------------
# View job detail — students see Apply, alumni poster sees applicants
# ---------------------------------------------------------------------------

@jobs_bp.route("/jobs/<int:job_id>")
@login_required
def view_job(job_id):
    db.session.expire_all()  # Force fresh data query
    job = Job.query.get_or_404(job_id)

    # Check if the current student already applied
    existing_application = None
    if current_user.role == "student":
        existing_application = JobApplication.query.filter_by(
            job_id=job_id, student_id=current_user.id
        ).first()

    # If the logged-in user is the alumni who posted this job, show applicants split by active vs rejected
    active_applicants = []
    rejected_applicants = []
    is_poster = (current_user.id == job.posted_by)
    if is_poster:
        all_applicants = JobApplication.query.filter_by(job_id=job_id)\
            .order_by(JobApplication.created_at.desc()).all()
        for app in all_applicants:
            if app.status == "rejected":
                rejected_applicants.append(app)
            else:
                active_applicants.append(app)

    rendered = render_template(
        "jobs/view.html",
        job=job,
        existing_application=existing_application,
        active_applicants=active_applicants,
        rejected_applicants=rejected_applicants,
        is_poster=is_poster,
    )
    return _no_cache_response(rendered)


# ---------------------------------------------------------------------------
# Apply to a job — students only, prevent duplicates
# ---------------------------------------------------------------------------

@jobs_bp.route("/jobs/<int:job_id>/apply", methods=["POST"])
@login_required
def apply_job(job_id):
    if current_user.role != "student":
        flash("Only students can apply to jobs.", "danger")
        return redirect(url_for("jobs.view_job", job_id=job_id))

    Job.query.get_or_404(job_id)

    existing = JobApplication.query.filter_by(
        job_id=job_id, student_id=current_user.id
    ).first()
    if existing:
        flash("You have already applied to this job.", "warning")
        return redirect(url_for("jobs.view_job", job_id=job_id))

    application = JobApplication(
        job_id=job_id,
        student_id=current_user.id,
        status="applied",
    )
    db.session.add(application)
    db.session.commit()

    flash("Application submitted successfully!", "success")
    return redirect(url_for("jobs.view_job", job_id=job_id))


# ---------------------------------------------------------------------------
# My Applications — student's own applications with status
# ---------------------------------------------------------------------------

@jobs_bp.route("/my-applications")
@login_required
def my_applications():
    if current_user.role != "student":
        flash("Only students can view their applications.", "danger")
        return redirect(url_for("jobs.list_jobs"))

    db.session.expire_all()  # Force fresh data from database

    all_applications = JobApplication.query.filter_by(student_id=current_user.id)\
        .order_by(JobApplication.created_at.desc()).all()

    active_applications = [a for a in all_applications if a.status != "rejected"]
    rejected_applications = [a for a in all_applications if a.status == "rejected"]

    rendered = render_template(
        "jobs/my_applications.html",
        active_applications=active_applications,
        rejected_applications=rejected_applications
    )
    return _no_cache_response(rendered)


# ---------------------------------------------------------------------------
# Update application status — alumni poster only
# ---------------------------------------------------------------------------

@jobs_bp.route("/jobs/<int:job_id>/applications/<int:app_id>/update", methods=["POST"])
@login_required
def update_application(job_id, app_id):
    job = Job.query.get_or_404(job_id)
    if job.posted_by != current_user.id:
        flash("You are not authorised to manage applicants for this job.", "danger")
        return redirect(url_for("jobs.view_job", job_id=job_id))

    application = JobApplication.query.get_or_404(app_id)
    if application.job_id != job_id:
        flash("Invalid application.", "danger")
        return redirect(url_for("jobs.view_job", job_id=job_id))

    new_status = request.form.get("status", "").strip()
    if new_status not in ("reviewed", "rejected", "accepted"):
        flash("Invalid status.", "danger")
        return redirect(url_for("jobs.view_job", job_id=job_id))

    application.status = new_status
    db.session.commit()

    # Create notification for the student
    status_labels = {
        "reviewed": "is being reviewed",
        "rejected": "has been rejected",
        "accepted": "has been accepted",
    }
    notif = Notification(
        user_id=application.student_id,
        message=f'Your application for "{job.title}" {status_labels[new_status]}.',
        link=url_for("jobs.my_applications"),
    )
    db.session.add(notif)
    db.session.commit()

    flash(f"Application status updated to {new_status}.", "success")
    return redirect(url_for("jobs.view_job", job_id=job_id))

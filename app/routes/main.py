# Main blueprint — root / test routes

from flask import Blueprint, render_template, jsonify, send_from_directory, current_app
from app.extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Home page — renders base template with a welcome message."""
    from app.models import User, Job

    verified_alumni_count = User.query.filter_by(role="alumni", is_verified=True).count()
    active_job_count = Job.query.count()
    batch_count = (
        db.session.query(User.batch)
        .filter(User.batch.isnot(None), User.batch != "")
        .distinct()
        .count()
    )

    return render_template(
        "index.html",
        verified_alumni_count=verified_alumni_count,
        active_job_count=active_job_count,
        batch_count=batch_count,
    )


@main_bp.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """Serve uploaded resume files."""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@main_bp.route("/health")
def health():
    """Test route — confirms the app runs and can talk to the database."""
    

    try:
        # Force a real DB query (not just a raw SELECT 1)
        from app.models import User
        User.query.count()
        db_ok = True
    except Exception:
        db_ok = False

    return jsonify({"status": "ok", "database": "connected" if db_ok else "disconnected"})

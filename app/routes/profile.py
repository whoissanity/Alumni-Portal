import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app.extensions import db


from app.utils import allowed_file

profile_bp = Blueprint("profile", __name__)

@profile_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.bio = request.form.get("bio", "").strip()
        current_user.department = request.form.get("department", "").strip()
        current_user.batch = request.form.get("batch", "").strip()
        
        if current_user.role == "alumni":
            current_user.current_job_title = request.form.get("current_job_title", "").strip()
            current_user.company = request.form.get("company", "").strip()
            
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Ensure filename is unique or append user ID
                    filename = f"{current_user.id}_{filename}"
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                    current_user.resume_filename = filename
                else:
                    flash("Invalid file type. Only PDF and DOCX are allowed.", "danger")
                    return redirect(url_for("profile.profile"))

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile.profile"))
        
    return render_template("profile.html")

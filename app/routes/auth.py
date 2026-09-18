# Authentication blueprint — register & login routes (FR-1 to FR-9)

import os
from werkzeug.utils import secure_filename
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from app.utils import allowed_file
from flask_login import login_user, logout_user, current_user

from app.extensions import bcrypt, db
from app.models import User

auth_bp = Blueprint("auth", __name__)


# ---------------------------------------------------------------------------
# Registration  (FR-1, FR-2, FR-3, FR-4, FR-7)
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    FR-1  Allow new user to register as Student or Alumni.
    FR-2  Registration requires name, email, password, and role.
    FR-3  Reject registration if email already in use.
    FR-4  Store passwords only as securely hashed values (bcrypt).
    FR-7  Mark newly registered alumni accounts as unverified by default.
    Note: Resume required for student role.
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")
        department = request.form.get("department", "").strip()

        allowed_depts = {"CSE", "CE", "MME", "TE", "EEE"}

        # --- Validation ---
        if not name or not email or not password or not department:
            flash("All fields are required.", "danger")
            return render_template("register.html", selected_role=role, name=name, email=email, selected_dept=department)

        if department not in allowed_depts:
            flash("Please select a valid department.", "danger")
            return render_template("register.html", selected_role=role, name=name, email=email, selected_dept=department)

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html", selected_role=role, name=name, email=email, selected_dept=department)

        # Check if email is already registered
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return render_template("register.html", selected_role=role, name=name, email=email, selected_dept=department)

        file = request.files.get("resume")
        if not file or file.filename == '' or not allowed_file(file.filename):
            flash("A resume (PDF or DOCX) is required for registration.", "danger")
            return render_template("register.html", selected_role=role, name=name, email=email, selected_dept=department)

        # FR-4: Hash password with bcrypt
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")

        # FR-7: alumni gets is_verified=False by default (already the DB default)
        is_verified = (role == "student")  # students auto-verified; alumni pending

        user = User(
            username=name,
            email=email,
            password_hash=hashed,
            role=role,
            department=department,
            is_verified=is_verified,
        )
        db.session.add(user)
        db.session.commit()

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filename = f"{user.id}_{filename}"
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            user.resume_filename = filename
            db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


# ---------------------------------------------------------------------------
# Login  (FR-5, FR-6, FR-9)
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    FR-5  Issue access token upon successful login (adapted: Flask-Login session).
    FR-6  Restrict access based on logged-in user's role.
    FR-9  Prevent unverified alumni from logging in.
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("login.html")

        user = User.query.filter_by(email=email).first()

        if user is None:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        # FR-4: Verify password against stored bcrypt hash
        if not bcrypt.check_password_hash(user.password_hash, password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        # Check if account is suspended/banned
        if user.is_banned:
            flash("Your account has been suspended by an administrator.", "danger")
            return render_template("login.html")

        # FR-9: Block unverified alumni
        if user.role == "alumni" and not user.is_verified:
            flash(
                "Your account is pending admin verification. "
                "You cannot log in yet.",
                "warning",
            )
            return render_template("login.html")

        # FR-5: Log the user in (Flask-Login sets session cookie)
        success = login_user(user)
        if not success:
            flash("Unable to log in. Account may be inactive or suspended.", "danger")
            return render_template("login.html")

        flash(f"Welcome back, {user.username}!", "success")
        return redirect(url_for("main.index"))

    return render_template("login.html")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))

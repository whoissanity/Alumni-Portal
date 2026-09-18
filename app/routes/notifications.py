# Notifications blueprint — in-app notifications

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Notification

notifications_bp = Blueprint("notifications", __name__)


# ---------------------------------------------------------------------------
# List notifications — newest first
# ---------------------------------------------------------------------------

@notifications_bp.route("/notifications")
@login_required
def list_notifications():
    if current_user.is_banned:
        flash("Your account has been banned.", "danger")
        return redirect(url_for("main.index"))

    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()

    return render_template("notifications/list.html", notifications=notifications)


# ---------------------------------------------------------------------------
# Mark notification as read on click and redirect to link
# ---------------------------------------------------------------------------

@notifications_bp.route("/notifications/<int:notif_id>/read")
@login_required
def read_notification(notif_id):
    notif = Notification.query.get_or_404(notif_id)

    if notif.user_id != current_user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for("notifications.list_notifications"))

    notif.is_read = True
    db.session.commit()

    if notif.link:
        return redirect(notif.link)
    return redirect(url_for("notifications.list_notifications"))


# ---------------------------------------------------------------------------
# Mark all notifications as read
# ---------------------------------------------------------------------------

@notifications_bp.route("/notifications/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False)\
        .update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications.list_notifications"))

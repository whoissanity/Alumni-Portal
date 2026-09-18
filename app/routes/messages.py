# Messaging blueprint — in-app text messages between users

from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Message, Notification, User, MentorshipRequest

messages_bp = Blueprint("messages", __name__)


# ---------------------------------------------------------------------------
# Inbox — list all conversations (grouped by user, ordered by newest message)
# ---------------------------------------------------------------------------

@messages_bp.route("/messages")
@login_required
def inbox():
    if current_user.is_banned:
        flash("Your account has been banned.", "danger")
        return redirect(url_for("main.index"))

    db.session.expire_all()

    # Get distinct conversation partner IDs
    sent_to = db.session.query(Message.receiver_id).filter_by(sender_id=current_user.id)
    received_from = db.session.query(Message.sender_id).filter_by(receiver_id=current_user.id)

    partner_ids = set()
    for row in sent_to:
        partner_ids.add(row[0])
    for row in received_from:
        partner_ids.add(row[0])

    # Fetch partner user objects
    partners = User.query.filter(User.id.in_(partner_ids)).all()

    # Build conversation meta list: (partner, last_message, unread_count)
    conversations = []
    for partner in partners:
        last_msg = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == partner.id)) |
            ((Message.sender_id == partner.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.sent_at.desc()).first()

        unread_count = Message.query.filter_by(
            sender_id=partner.id, receiver_id=current_user.id, is_read=False
        ).count()

        conversations.append({
            "partner": partner,
            "last_message": last_msg,
            "unread_count": unread_count,
            "last_timestamp": last_msg.sent_at if last_msg else None
        })

    # Sort conversations by last_timestamp descending (newest on top)
    conversations.sort(key=lambda c: c["last_timestamp"] if c["last_timestamp"] else datetime.min, reverse=True)

    return render_template("messages/inbox.html", conversations=conversations)


# ---------------------------------------------------------------------------
# Conversation thread with a specific user (GET)
# ---------------------------------------------------------------------------

@messages_bp.route("/messages/<int:other_id>", methods=["GET", "POST"])
@login_required
def conversation(other_id):
    if current_user.is_banned:
        flash("Your account has been banned.", "danger")
        return redirect(url_for("main.index"))

    other = User.query.get_or_404(other_id)
    if other.id == current_user.id:
        flash("You cannot message yourself.", "danger")
        return redirect(url_for("messages.inbox"))

    # Permission check for students
    if current_user.role == "student":
        has_mentorship = MentorshipRequest.query.filter_by(
            student_id=current_user.id,
            mentor_id=other_id,
            status="accepted"
        ).first()
        from app.models import Job, JobApplication
        has_job_app = JobApplication.query.join(Job).filter(
            JobApplication.student_id == current_user.id,
            Job.posted_by == other_id
        ).first()
        existing_msg = Message.query.filter(
            ((Message.sender_id == other_id) & (Message.receiver_id == current_user.id)) |
            ((Message.sender_id == current_user.id) & (Message.receiver_id == other_id))
        ).first()
        is_poster = Job.query.filter_by(posted_by=other_id).first() is not None

        if not has_mentorship and not has_job_app and not existing_msg and not is_poster:
            flash(
                "You can only message an alumnus after requesting mentorship, applying to their job, or receiving a message.",
                "warning"
            )
            return redirect(url_for("mentorship.alumni_public_profile", alumni_id=other_id))

    if request.method == "POST":
        return send_message(other_id)

    # Mark all unread incoming messages from this partner as read
    Message.query.filter_by(
        sender_id=other_id, receiver_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    # Load thread (oldest to newest)
    thread = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.sent_at.asc()).all()

    return render_template("messages/conversation.html", other=other, thread=thread)


# ---------------------------------------------------------------------------
# Send a message POST endpoint: /messages/<other_id>/send
# ---------------------------------------------------------------------------

@messages_bp.route("/messages/<int:other_id>/send", methods=["POST"])
@login_required
def send_message(other_id):
    if current_user.is_banned:
        flash("Your account has been banned.", "danger")
        return redirect(url_for("main.index"))

    other = User.query.get_or_404(other_id)
    if other.id == current_user.id:
        flash("You cannot message yourself.", "danger")
        return redirect(url_for("messages.inbox"))

    body = request.form.get("body", "").strip() or request.form.get("content", "").strip()
    if not body:
        flash("Message cannot be empty.", "danger")
        return redirect(url_for("messages.conversation", other_id=other_id))

    # Save message
    msg = Message(sender_id=current_user.id, receiver_id=other_id, body=body)
    db.session.add(msg)
    db.session.commit()

    # Create notification for receiver
    snippet = body[:40] + "..." if len(body) > 40 else body
    notif = Notification(
        user_id=other_id,
        message=f"New message from {current_user.username}: \"{snippet}\"",
        link=url_for("messages.conversation", other_id=current_user.id)
    )
    db.session.add(notif)
    db.session.commit()

    return redirect(url_for("messages.conversation", other_id=other_id))


# ---------------------------------------------------------------------------
# API endpoint for Inbox polling (returns JSON)
# ---------------------------------------------------------------------------

@messages_bp.route("/api/messages/inbox")
@login_required
def api_inbox():
    if current_user.is_banned:
        return jsonify({"error": "Banned"}), 403

    db.session.expire_all()
    sent_to = db.session.query(Message.receiver_id).filter_by(sender_id=current_user.id)
    received_from = db.session.query(Message.sender_id).filter_by(receiver_id=current_user.id)

    partner_ids = set()
    for row in sent_to:
        partner_ids.add(row[0])
    for row in received_from:
        partner_ids.add(row[0])

    partners = User.query.filter(User.id.in_(partner_ids)).all()

    convs = []
    for partner in partners:
        last_msg = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == partner.id)) |
            ((Message.sender_id == partner.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.sent_at.desc()).first()

        unread_count = Message.query.filter_by(
            sender_id=partner.id, receiver_id=current_user.id, is_read=False
        ).count()

        convs.append({
            "partner_id": partner.id,
            "username": partner.username,
            "role": partner.role,
            "batch": partner.batch or "",
            "initial": partner.username[0].upper() if partner.username else "?",
            "last_message": last_msg.body if last_msg else "",
            "last_sender_id": last_msg.sender_id if last_msg else None,
            "sent_at": last_msg.sent_at.strftime('%b %d, %H:%M') if last_msg else "",
            "timestamp_iso": last_msg.sent_at.isoformat() if last_msg else "",
            "unread_count": unread_count,
            "conversation_url": url_for("messages.conversation", other_id=partner.id)
        })

    convs.sort(key=lambda c: c["timestamp_iso"], reverse=True)
    return jsonify({"conversations": convs})


# ---------------------------------------------------------------------------
# API endpoint for Conversation thread polling (returns JSON)
# ---------------------------------------------------------------------------

@messages_bp.route("/api/messages/<int:other_id>/json")
@login_required
def api_conversation(other_id):
    if current_user.is_banned:
        return jsonify({"error": "Banned"}), 403

    db.session.expire_all()
    other = User.query.get_or_404(other_id)

    # Mark all unread incoming messages from this partner as read
    Message.query.filter_by(
        sender_id=other_id, receiver_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()

    thread = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.sent_at.asc()).all()

    messages_json = []
    for msg in thread:
        messages_json.append({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "body": msg.body,
            "sent_at": msg.sent_at.strftime('%b %d, %H:%M'),
            "is_me": (msg.sender_id == current_user.id)
        })

    return jsonify({
        "other": {
            "id": other.id,
            "username": other.username
        },
        "messages": messages_json,
        "current_user_id": current_user.id
    })

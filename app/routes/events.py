# Events blueprint — FR-25 to FR-28

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.extensions import db
from app.models import Event, EventRSVP

events_bp = Blueprint("events", __name__)


# ---------------------------------------------------------------------------
# List all events (soonest first) — FR-25
# ---------------------------------------------------------------------------

@events_bp.route("/events")
@login_required
def list_events():
    events = Event.query.order_by(Event.event_date.asc()).all()
    return render_template("events/list.html", events=events)


# ---------------------------------------------------------------------------
# Create a new event — verified alumni or admin only — FR-26
# ---------------------------------------------------------------------------

@events_bp.route("/events/new", methods=["GET", "POST"])
@login_required
def new_event():
    # Only verified alumni or admins may create events
    is_verified_alumni = current_user.role == "alumni" and current_user.is_verified
    is_admin = current_user.role == "admin"

    if not (is_verified_alumni or is_admin):
        flash("Only verified alumni or admins can create events.", "danger")
        return redirect(url_for("events.list_events"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        event_date = request.form.get("event_date", "").strip()
        location = request.form.get("location", "").strip()

        if not title or not description or not event_date:
            flash("Title, description, and event date are required.", "danger")
            return render_template(
                "events/new.html",
                title=title,
                description=description,
                event_date=event_date,
                location=location,
            )

        # Parse the datetime from the form (HTML datetime-local gives YYYY-MM-DDTHH:MM)
        from datetime import datetime

        try:
            parsed_date = datetime.fromisoformat(event_date)
        except (ValueError, TypeError):
            flash("Invalid date format.", "danger")
            return render_template(
                "events/new.html",
                title=title,
                description=description,
                event_date=event_date,
                location=location,
            )

        event = Event(
            title=title,
            description=description,
            event_date=parsed_date,
            location=location,
            created_by=current_user.id,
        )
        db.session.add(event)
        db.session.commit()

        flash("Event created successfully!", "success")
        return redirect(url_for("events.list_events"))

    return render_template("events/new.html")


# ---------------------------------------------------------------------------
# Event detail page with RSVP count — FR-27
# ---------------------------------------------------------------------------

@events_bp.route("/events/<int:event_id>")
@login_required
def view_event(event_id):
    event = Event.query.get_or_404(event_id)
    rsvp_count = event.rsvps.count()

    # Check if the current user has already RSVP'd
    user_rsvp = EventRSVP.query.filter_by(
        event_id=event_id, user_id=current_user.id
    ).first()

    return render_template(
        "events/detail.html",
        event=event,
        rsvp_count=rsvp_count,
        user_rsvp=user_rsvp,
    )


# ---------------------------------------------------------------------------
# RSVP to an event (prevent duplicates) — FR-28
# ---------------------------------------------------------------------------

@events_bp.route("/events/<int:event_id>/rsvp", methods=["POST"])
@login_required
def rsvp(event_id):
    Event.query.get_or_404(event_id)

    existing = EventRSVP.query.filter_by(
        event_id=event_id, user_id=current_user.id
    ).first()

    if existing:
        # Toggle: remove RSVP if already set
        db.session.delete(existing)
        db.session.commit()
        flash("Your RSVP has been cancelled.", "info")
    else:
        rsvp_record = EventRSVP(event_id=event_id, user_id=current_user.id)
        db.session.add(rsvp_record)
        db.session.commit()
        flash("You have RSVP'd to this event!", "success")

    return redirect(url_for("events.view_event", event_id=event_id))

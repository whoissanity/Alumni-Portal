# Success Stories blueprint — FR-32 (Alumni submission) & public gallery

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user, login_required
from app.extensions import db
from app.models import SuccessStory, User, Notification

stories_bp = Blueprint("stories", __name__, url_prefix="/stories")


@stories_bp.route("/")
def list_stories():
    """List all published success stories."""
    page = request.args.get("page", 1, type=int)
    pagination = (
        SuccessStory.query.filter_by(is_published=True)
        .order_by(SuccessStory.created_at.desc())
        .paginate(page=page, per_page=9, error_out=False)
    )
    stories = pagination.items
    return render_template("stories/list.html", stories=stories, pagination=pagination)


@stories_bp.route("/<int:story_id>")
def story_detail(story_id):
    """View a single success story."""
    story = SuccessStory.query.get_or_404(story_id)
    # Only allow viewing if published, or if the author or an admin is viewing
    if not story.is_published:
        if not current_user.is_authenticated or (
            current_user.id != story.author_id and current_user.role != "admin"
        ):
            abort(404)
    return render_template("stories/detail.html", story=story)


@stories_bp.route("/submit", methods=["GET", "POST"])
@login_required
def submit_story():
    """FR-32: Alumni submits a success story for publication."""
    # Restrict to verified alumni only
    if current_user.role != "alumni" or not current_user.is_verified:
        flash("Only verified alumni can submit success stories.", "warning")
        return redirect(url_for("stories.list_stories"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.", "danger")
            return render_template("stories/submit.html", title=title, content=content)

        story = SuccessStory(
            title=title,
            content=content,
            author_id=current_user.id,
            is_published=False,  # Needs admin approval (FR-33)
        )
        db.session.add(story)
        db.session.commit()

        # Notify admins if any
        admins = User.query.filter_by(role="admin").all()
        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                message=f"New success story pending approval: '{title}' by {current_user.username}",
                link=url_for("admin.pending_stories"),
            )
            db.session.add(notif)
        db.session.commit()

        flash("Your success story has been submitted! It will be published after admin approval.", "success")
        return redirect(url_for("stories.my_stories"))

    return render_template("stories/submit.html")


@stories_bp.route("/my-stories")
@login_required
def my_stories():
    """List stories submitted by the logged-in user."""
    stories = (
        SuccessStory.query.filter_by(author_id=current_user.id)
        .order_by(SuccessStory.created_at.desc())
        .all()
    )
    return render_template("stories/my_stories.html", stories=stories)

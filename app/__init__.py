# Flask application factory

import os
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from .config import config_by_name
from .extensions import db, bcrypt, login_manager, mail


@login_manager.user_loader
def load_user(user_id):
    """Load a user by ID for Flask-Login."""
    from app.models import User
    return User.query.get(int(user_id))


def create_app(config_name=None):
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)


    # Update login_view now that auth blueprint exists
    login_manager.login_view = "auth.login"

    # Register blueprints
    from .routes.main import main_bp
    app.register_blueprint(main_bp)

    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    # Register admin blueprint
    from .routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    from .routes.profile import profile_bp
    app.register_blueprint(profile_bp)

    from .routes.resume_review import resume_review_bp
    app.register_blueprint(resume_review_bp)

    from .routes.jobs import jobs_bp
    app.register_blueprint(jobs_bp)

    from .routes.mentorship import mentorship_bp
    app.register_blueprint(mentorship_bp)

    from .routes.events import events_bp
    app.register_blueprint(events_bp)

    from .routes.messages import messages_bp
    app.register_blueprint(messages_bp)

    from .routes.notifications import notifications_bp
    app.register_blueprint(notifications_bp)

    from .routes.stories import stories_bp
    app.register_blueprint(stories_bp)

    # Create tables on first run
    with app.app_context():
        db.create_all()

    return app

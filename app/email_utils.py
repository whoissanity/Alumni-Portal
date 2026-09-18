# Email utility functions for the Alumni Network & Career Portal

from flask import current_app
from flask_mail import Message
from app.extensions import mail
from app.models import User


def send_alumni_verified_email(user):
    """Emails disabled."""
    pass


def send_job_match_emails(job):
    """Emails disabled."""
    pass


def send_mentorship_confirmed_emails(mentorship_request):
    """Emails disabled."""
    pass


def send_registration_email(user):
    """Emails disabled."""
    pass


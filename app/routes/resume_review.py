# Resume Review blueprint — AI resume analysis (FR-18, FR-20)
# Note: FR-19 (job recommendations) would be a separate feature

from flask import Blueprint, flash, redirect, url_for, current_app, render_template
from flask_login import login_required, current_user
from app.extensions import db
from app.models import ResumeReview
import os
import json
import re
import time
import logging
from google import genai

# Check for required libraries
try:
    import docx
except ImportError:
    docx = None

try:
    import pypdf
except ImportError:
    pypdf = None

resume_review_bp = Blueprint("resume_review", __name__, url_prefix="/resume")

if not os.environ.get("GEMINI_API_KEY_PRIMARY") and not os.environ.get("GEMINI_API_KEY_SECONDARY"):
    logging.getLogger(__name__).warning(
        "Neither GEMINI_API_KEY_PRIMARY nor GEMINI_API_KEY_SECONDARY is set. "
        "Resume AI review will be unavailable until at least one is configured."
    )


def extract_text_from_resume(resume_filename):
    """Extract text from a resume file (PDF or DOCX)."""
    if not resume_filename:
        return None
        
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        upload_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    
    resume_path = os.path.join(upload_folder, resume_filename)
    
    if not os.path.exists(resume_path):
        return None
    
    try:
        if resume_filename.lower().endswith(".docx"):
            if docx is None:
                raise ImportError("python-docx is not installed")
            doc = docx.Document(resume_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])
        elif resume_filename.lower().endswith(".pdf"):
            if pypdf is None:
                raise ImportError("pypdf is not installed")
            reader = pypdf.PdfReader(resume_path)
            pages_text = ""
            for page in reader.pages:
                pages_text += page.extract_text() or ""
            text = pages_text
        else:
            return None
        return text.strip()[:16000]  # Limit size for API call
    except Exception as e:
        current_app.logger.error(f"Failed to extract text from {resume_filename}: {e}")
        return None


def clean_json_response(response_text):
    """Clean markdown code fences from AI response."""
    # Remove markdown code blocks (```json ... ```)
    text = re.sub(r"```[\s]*json[\s]*", "", response_text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    return text.strip()


@resume_review_bp.route("/review", methods=["POST"])
@login_required
def review_resume():
    """Route to analyze a resume using AI."""
    # Students and verified alumni can use this feature
    if current_user.role not in ("student", "alumni"):
        flash("Only students and alumni can submit resumes for review.", "warning")
        return redirect(url_for("main.index"))

    # Alumni must be verified
    if current_user.role == "alumni" and not current_user.is_verified:
        flash("Your alumni account is pending verification.", "warning")
        return redirect(url_for("profile.profile"))

    # Check if user has a resume
    if not current_user.resume_filename:
        flash("Please upload your resume first before reviewing.", "warning")
        return redirect(url_for("profile.profile"))

    try:
        # Extract text from resume
        resume_text = extract_text_from_resume(current_user.resume_filename)
        if not resume_text:
            flash("Failed to extract text from resume. Please try uploading again.", "danger")
            return redirect(url_for("profile.profile"))

        # Call Gemini API with primary → secondary key fallback
        primary_key = os.environ.get("GEMINI_API_KEY_PRIMARY")
        secondary_key = os.environ.get("GEMINI_API_KEY_SECONDARY")
        keys_to_try = [k for k in [primary_key, secondary_key] if k]

        prompt = f"""Analyze this resume and return ONLY valid JSON with keys:
"score" (integer 0-100), "formatting_feedback" (string),
"content_feedback" (string), "ats_feedback" (string).
Resume text:
{resume_text}"""

        result_text = None
        last_error = None

        for key_index, api_key in enumerate(keys_to_try):
            client = genai.Client(api_key=api_key)
            key_label = "primary" if key_index == 0 else "secondary"
            for attempt in range(2):  # 2 tries per key
                try:
                    response = client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=prompt
                    )
                    result_text = response.text
                    break
                except Exception as e:
                    last_error = e
                    current_app.logger.warning(
                        f"Gemini API ({key_label} key) attempt {attempt + 1} failed: {e}"
                    )
                    if attempt == 0:
                        time.sleep(2)
            if result_text is not None:
                break
            current_app.logger.warning(
                f"All attempts failed on {key_label} key, moving to next key if available."
            )

        if result_text is None:
            current_app.logger.error(f"Gemini API error after trying all keys: {last_error}")
            flash(
                "AI review is temporarily unavailable (the AI service is under heavy load). "
                "Please try again in a minute.",
                "warning",
            )
            return redirect(url_for("profile.profile"))

        # Parse JSON response
        clean_text = clean_json_response(result_text)
        try:
            result = json.loads(clean_text)
        except json.JSONDecodeError:
            current_app.logger.error(f"Failed to parse resume review JSON: {clean_text[:200]}")
            flash("Invalid response from AI service. Please try again later.", "warning")
            return redirect(url_for("profile.profile"))
        
        # Validate required fields
        score = int(result.get("score", 50))
        formatting_feedback = result.get("formatting_feedback", "No formatting feedback available.")
        content_feedback = result.get("content_feedback", "No content feedback available.")
        ats_feedback = result.get("ats_feedback", "No ATS feedback available.")
        
        # Ensure score is within range
        score = max(0, min(100, score))

        # Save review to database
        review = ResumeReview(
            student_id=current_user.id,
            score=score,
            feedback_json=json.dumps({
                "score": score,
                "formatting_feedback": formatting_feedback,
                "content_feedback": content_feedback,
                "ats_feedback": ats_feedback
            })
        )
        db.session.add(review)
        db.session.commit()

        return render_template(
            "resume_review.html",
            score=score,
            formatting_feedback=formatting_feedback,
            content_feedback=content_feedback,
            ats_feedback=ats_feedback
        )

    except Exception as e:
        current_app.logger.error(f"Resume review error: {e}")
        flash("AI review is temporarily unavailable, please try again later.", "warning")
        return redirect(url_for("profile.profile"))
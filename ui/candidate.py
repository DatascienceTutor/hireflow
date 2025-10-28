"""
Candidate dashboard UI components (post-login).
This file contains the render functions for each section displayed in app.py.
It no longer contains its own router or sidebar.
"""

from typing import List, Dict, Any
import streamlit as st
from sqlalchemy.orm import Session
from models import candidate
from services.common import get_unique_column_values, header_with_progress, get_column_value_by_condition
from services.candidate_service import save_candidate_answers, cosine_similarity
from models.question import Question
from services.common import header_with_progress
import contextlib
from db.session import get_db
from models.candidate import Candidate
from services.openai_service import get_embedding
import traceback
import logging

# --- Helper Function for DB Submission ---

def _submit_all_answers(candidate_id: int, answers: Dict[int, str], answer_embeddings: Dict[int, list] | None = None) -> Dict[str, Any]:
    """
    Persist answers using a fresh DB session.
    Always returns a dict with at least the key 'saved_count' and optionally 'error'.
    """
    try:
        with contextlib.closing(next(get_db())) as db:
            cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
            if not cand:
                return {"saved_count": 0, "error": "candidate not found"}

            # Call save function (may raise)
            res = save_candidate_answers(db, cand, answers, answer_embeddings)

            # Normalize response: ensure dict is returned
            if isinstance(res, dict):
                # ensure saved_count exists
                res.setdefault("saved_count", res.get("saved_count", 0))
                return res
            else:
                # If the save function returned something unexpected (None or other), convert it
                return {"saved_count": 0, "error": "save_candidate_answers returned no result or invalid type"}
    except Exception as exc:
        # Catch all and return an error dict (safest for UI)
        tb = traceback.format_exc()
        logging.error(f"Error submitting answers: {tb}")
        return {"saved_count": 0, "error": str(exc), "trace": tb}

# --- Candidate Dashboard (Interview) ---

def render_candidate_dashboard():
    """
    Renders the main candidate dashboard, which contains the interview UI.
    """
    # Ensure interview_started exists in session state
    st.session_state.setdefault("interview_started", False)

    user_email = st.session_state.get("user_email")
    if not user_email:
        st.warning("Session invalid. Please log in again.")
        return

    # Load candidate (full model instance)
    with contextlib.closing(next(get_db())) as db:
        candidate = get_column_value_by_condition(
            db, Candidate, "email", user_email, target_column=None, multiple=False
        )

    if not candidate:
        st.error("Candidate not found for this email. Please contact admin.")
        return

    st.subheader(f"My Interview")
    
    # --- State 1: Interview Not Started ---
    if not st.session_state.get("interview_started"):
        st.write("Welcome to your technical interview. When you are ready, click the button below to begin.")
        st.markdown(
            """
            - You can answer questions one by one and navigate using **Next** / **Back**.
            - Your answers will be saved only when you click **Submit** at the end.
            """
        )
        if st.button("Start Interview", type="primary"):
            # Start interview: set flag and clear old state
            st.session_state["interview_started"] = True
            st.session_state.pop("interview_questions", None)
            st.session_state.pop("interview_answers", None)
            st.session_state.pop("interview_index", None)
            st.rerun()
        return

    # --- State 2: Interview In Progress ---

    # --- Initialization: load questions once ---
    if "interview_questions" not in st.session_state:
        with contextlib.closing(next(get_db())) as db:
            questions_obj_list: List[Question] = get_column_value_by_condition(
                db, Question, "job_code", candidate.job_code, target_column=None, multiple=True
            )

        if not questions_obj_list:
            st.error("No questions assigned for this job code. Please contact the recruiter.")
            st.session_state["interview_questions"] = [] # Set to empty to prevent reload
            return

        # Convert to lightweight dicts for session storage
        st.session_state["interview_questions"] = [
            {"id": q.id, "text": q.question_text, "model_embedding": q.model_answer_embedding}
            for q in questions_obj_list
        ]
        # Initialize empty answers keyed by string QID
        st.session_state["interview_answers"] = {str(q["id"]): "" for q in st.session_state["interview_questions"]}
        st.session_state["interview_index"] = 0

    # --- Rendering: always run after initialization ---
    questions: List[Dict[str, Any]] = st.session_state.get("interview_questions", [])
    answers: Dict[str, str] = st.session_state.get("interview_answers", {})
    idx: int = st.session_state.get("interview_index", 0)

    if not questions:
        st.info("No interview questions available.")
        return

    # clamp index
    idx = max(0, min(idx, len(questions) - 1))
    st.session_state["interview_index"] = idx

    total = len(questions)
    current_q = questions[idx]
    qid = current_q["id"]
    q_text = current_q["text"]

    # Top-right progress indicator
    header_with_progress(idx + 1, total)
    st.markdown("---")

    with st.container(border=True):
        st.markdown(f"### {q_text}")
        
        # Answer box
        answers[str(qid)] = st.text_area(
            "Your Answer",
            value=answers.get(str(qid), ""),
            height=250,
            key=f"answer_{qid}",
            label_visibility="collapsed"
        )
        st.session_state["interview_answers"] = answers

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if idx > 0: # Only show 'Back' if not on the first question
            if st.button("⬅️ Back", key=f"back_{qid}"):
                st.session_state["interview_index"] -= 1
                st.rerun()
    with col2:
        st.write("")  # spacer
    with col3:
        if st.session_state["interview_index"] < total - 1:
            if st.button("Next ➡️", key=f"next_{qid}"):
                st.session_state["interview_index"] += 1
                st.rerun()
        else:
            # Last question - show Submit
            if st.button("Submit Interview ✅", key="submit_all", type="primary"):
                
                with st.spinner("Processing and saving your answers..."):
                    # Prepare answers payload
                    answers_payload: Dict[int, str] = {
                        int(k): v for k, v in st.session_state["interview_answers"].items() if v and v.strip()
                    }

                    # Generate embeddings for answers
                    embeddings: Dict[int, list] = {}
                    for qid_str, answer_text in st.session_state["interview_answers"].items():
                        if not answer_text or not answer_text.strip():
                            continue
                        try:
                            emb = get_embedding(answer_text)
                            if emb:
                                embeddings[int(qid_str)] = emb
                        except Exception as e:
                            logging.warning(f"Could not generate embedding for answer to QID {qid_str}: {e}")

                    # Persist answers
                    result = _submit_all_answers(candidate.id, answers_payload, embeddings if embeddings else None)
                    
                    if not isinstance(result, dict):
                        st.error("Unexpected error saving answers. Please contact admin.")
                    else:
                        if result.get("saved_count", 0) > 0:
                            st.success("Your responses have been successfully saved. Thank you!")
                            # Clear interview state
                            st.session_state["interview_started"] = False
                            st.session_state.pop("interview_questions", None)
                            st.session_state.pop("interview_answers", None)
                            st.session_state.pop("interview_index", None)
                            st.balloons()
                        else:
                            err = result.get("error", "Unknown error")
                            st.error(f"Failed to save responses: {err}")
                            trace = result.get("trace")
                            if trace:
                                st.code(trace) # For debugging

# --- Candidate Profile Tab ---

def render_candidate_profile():
    """Renders the candidate's profile/settings page."""
    st.subheader("My Profile")
    
    user_email = st.session_state.get("user_email")
    if not user_email:
        st.warning("Session invalid. Please log in again.")
        return

    # Load candidate
    with contextlib.closing(next(get_db())) as db:
        candidate = get_column_value_by_condition(
            db, Candidate, "email", user_email, target_column=None, multiple=False
        )

    if not candidate:
        st.error("Candidate not found for this email. Please contact admin.")
        return

    with st.form("profile_form"):
        st.text_input("Name", value=candidate.name, key="profile_name")
        st.text_input("Email", value=candidate.email, disabled=True)
        st.text_input("Job Code", value=candidate.job_code, disabled=True)
        st.text_input("Technology", value=candidate.tech, disabled=True)
        
        if st.form_submit_button("Update Profile"):
            # In a real app, you would save the updated name here
            st.success("Profile updated successfully")


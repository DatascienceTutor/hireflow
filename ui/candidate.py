"""
Candidate dashboard (post-login).
"""

from typing import List, Dict, Any
import streamlit as st
from sqlalchemy.orm import Session
from models import candidate
from services.common import get_unique_column_values,header_with_progress,get_column_value_by_condition
from services.candidate_service import save_candidate_answers,cosine_similarity
from models.question import Question
from services.common import header_with_progress
import contextlib
from db.session import get_db
from models.candidate import Candidate
from services.openai_service import get_embedding
import traceback



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
        return {"saved_count": 0, "error": str(exc), "trace": tb}


def render_candidate():
    """
    Candidate dashboard & interview UI.
    Uses st.session_state for simple navigation and state persistence.
    """
    # Ensure interview_started exists in session state and default to False
    if "interview_started" not in st.session_state:
        st.session_state["interview_started"] = False

    user_email = st.session_state.get("user_email")
    if not user_email:
        st.warning("Please sign in with your email to continue.")
        return

    # Load candidate (full model instance)
    with contextlib.closing(next(get_db())) as db:
        candidate = get_column_value_by_condition(
            db, Candidate, "email", user_email, target_column=None, multiple=False
        )

    if not candidate:
        st.error("Candidate not found for this email. Please contact admin.")
        return

    # Header
    st.title(f"Welcome {candidate.email.split('@')[0]} — Candidate Dashboard")
    st.markdown(
        """
        - Use the left sidebar to start your interview.
        - You can answer questions one by one and navigate using Next / Back.
        - Your answers will be saved when you click Submit at the end.
        """
    )

    # Sidebar menu
    with st.sidebar:
        st.header("Menu")
        if st.button("Interview"):
            # Start interview: set flag and clear question/answer/index state (questions reloaded on rerun)
            st.session_state["interview_started"] = True
            st.session_state.pop("interview_questions", None)
            st.session_state.pop("interview_answers", None)
            st.session_state.pop("interview_index", None)
            st.rerun()

        if st.button("Log out"):
            # Clear session keys and return to login state
            for k in ["user_email", "user_role", "user_name", "page", "interview_started"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    # If interview not started, show info and exit (preserves state)
    if not st.session_state.get("interview_started"):
        st.info("Click **Interview** in the sidebar to begin.")
        return

    # --- Initialization: load questions once and store simple dicts in session state ---
    if "interview_questions" not in st.session_state:
        with contextlib.closing(next(get_db())) as db:
            # Fetch full Question objects for the candidate's job_code
            questions_obj_list: List[Question] = get_column_value_by_condition(
                db, Question, "job_code", candidate.job_code, target_column=None, multiple=True
            )

        if not questions_obj_list:
            st.error("No questions assigned for this job code. Contact the recruiter.")
            st.session_state["interview_questions"] = []
            return

        # Convert to lightweight dicts for safe Streamlit session storage
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
    st.markdown(f"### {q_text}")

    # Answer box (we bind the current answer to the text_area key)
    answers[str(qid)] = st.text_area(
        "Your Answer",
        value=answers.get(str(qid), ""),
        height=200,
        key=f"answer_{qid}",
    )
    st.session_state["interview_answers"] = answers

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("⬅️ Back", key=f"back_{qid}"):
            if st.session_state["interview_index"] > 0:
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
            if st.button("Submit ✅", key="submit_all"):
                # Prepare answers payload (int qid -> answer_text), skip empties
                answers_payload: Dict[int, str] = {
                    int(k): v for k, v in st.session_state["interview_answers"].items() if v and v.strip()
                }

                # Optionally generate embeddings (placeholder function). Remove if unused.
                embeddings: Dict[int, list] = {}
                for qid_str, answer_text in st.session_state["interview_answers"].items():
                    if not answer_text or not answer_text.strip():
                        continue
                    emb = get_embedding(answer_text)
                    if emb:
                        embeddings[int(qid_str)] = emb

                # Persist answers using a fresh DB session
                result = _submit_all_answers(candidate.id, answers_payload, embeddings if embeddings else None)
                if not isinstance(result, dict):
                    st.error("Unexpected error saving answers. Contact admin.")
                else:
                    if result.get("saved_count", 0) > 0:
                        st.success("Your responses are successfully saved. Thank you!")
                    else:
                        # show helpful message from returned dict
                        err = result.get("error")
                        if err:
                            st.error(f"Failed to save responses: {err}")
                        else:
                            st.error("Failed to save responses. Contact admin.")
                        # Optionally log trace for debug (do not show trace to users in prod)
                        trace = result.get("trace")
                        if trace:
                            st.code(trace)



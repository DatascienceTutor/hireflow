"""
Hiring manager dashboard (post-login).
"""

import traceback
import streamlit as st
from typing import List, Dict, Any
import contextlib
import json
import logging
import pandas as pd
import numpy as np
from db.session import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text, distinct
from services.job_service import create_job
from services.candidate_service import create_candidate
import fitz  # PyMuPDF
from pathlib import Path
import uuid
from models.job import Job
from models.candidate import Candidate
from streamlit_searchbox import st_searchbox
import re
from services.openai_service import generate_knowledge_for_tech,get_embedding
from services.common import get_unique_column_values, get_column_value_by_condition,create_searchbox
from models.question import Question

def render_manager():
    # Get the user name from session state
    user_name = st.session_state.get("user_name", "Manager")
    st.sidebar.title("Menu")

    # Sidebar navigation options
    page = st.sidebar.radio(
        "Test",
        ["Dashboard", "JD Upload", "Resume Upload", "Generate Questions"],
        label_visibility="collapsed",
    )

    # Log out button in the sidebar
    if st.sidebar.button("Log out"):
        for k in ["user_email", "user_role", "user_name", "page"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    # Render the selected page
    if page == "Dashboard":
        render_dashboard(user_name)
    elif page == "JD Upload":
        render_jd_upload()
    elif page == "Resume Upload":
        render_resume_upload()
    elif page == "Generate Questions":
        render_generate_questions()


def render_dashboard(user_name):
    st.title(f"Welcome {user_name} -- Hiring Manager Dashboard")
    st.write("This is the dashboard page where you can view key metrics and insights.")


def render_jd_upload():
    st.title("Job Description Upload")
    uploaded_file = st.file_uploader("Upload Job Description (PDF)", type=["pdf"])
    tech_options = [
        "JavaScript",
        "Python",
        "Java",
        "React.js",
        "Node.js",
        "TypeScript",
        "C# / .NET",
        "SQL",
        "Docker",
        "Kubernetes",
    ]

    tech = st.selectbox("Select Technology", tech_options)
    job_title_placeholder = ""
    if uploaded_file:
        # Use pathlib to get the filename without the extension
        file_name_without_ext = Path(uploaded_file.name).stem
        unique_id = str(uuid.uuid4())[:8]
        job_title_placeholder = (
            f"{file_name_without_ext.replace(" ","_").title()}_{unique_id}"
        )
    title = st.text_input("Job Title", value=job_title_placeholder)

    # Upload and Save button
    if uploaded_file and tech and title and st.button("Upload and Save"):
        try:
            # Extract text from PDF
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            description = "\n".join([page.get_text() for page in doc])

            # Save to database using create_job
            with contextlib.closing(next(get_db())) as db:
                job = create_job(db, tech=tech, title=title, description=description)
                st.success(
                    f"✅ Job '{job.title}' saved successfully with code `{job.job_code}`."
                )

        except Exception as e:
            st.error(f"❌ Error processing PDF: {e}")


def render_resume_upload():
    st.title("Resume Upload")

    # def get_unique_job_codes(db: Session) -> list[tuple[str, str]]:
    #     """Fetches a list of all unique job codes from the database."""
    #     unique_codes = db.query(Job.job_code, Job.title).distinct().all()
    #     return unique_codes

    # def get_job_description_by_code(db: Session, job_code: str) -> str:
    #     """Fetches the job description for a given job code from the database."""
    #     job = db.query(Job).filter(Job.job_code == job_code).first()
    #     return job.description if job else None

    uploaded_file = st.file_uploader("Upload Resumes (PDF)", type=["pdf"])
    tech_options = [
        "JavaScript",
        "Python",
        "Java",
        "React.js",
        "Node.js",
        "TypeScript",
        "C# / .NET",
        "SQL",
        "Docker",
        "Kubernetes",
    ]
    tech = st.selectbox("Select Technology", tech_options)
    with contextlib.closing(next(get_db())) as db:
        unique_job_codes = get_unique_column_values(db, Job, ["job_code", "title"])

    job_code = create_searchbox(
        label="Select Job Code",
        placeholder="Search for a Job Code...",
        key="job_code_searchbox",
        data=unique_job_codes,
        display_fn=lambda x: f"{x[0]}_{x[1]}",
        return_fn=lambda x: x[0],
    )

    if job_code:
        job_description = get_column_value_by_condition(
            db, Job, "job_code", job_code.split("_")[0].strip(), "description"
        )

    resume_name_placeholder = ""
    if uploaded_file:
        # Use pathlib to get the filename without the extension
        file_name_without_ext = Path(uploaded_file.name).stem
        resume_name_placeholder = f"{file_name_without_ext.replace(" ","_").title()}"
    name = st.text_input("Candidate Name", value=resume_name_placeholder)
    if (
        uploaded_file
        and tech
        and job_code
        and job_description
        and st.button("Upload and Save")
    ):
        try:
            # Extract text from PDF
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            resume_text = "\n".join([page.get_text() for page in doc])
            email_matches = re.findall(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resume_text
            )
            email_id = (
                email_matches[0] if email_matches else None
            )  # Use first match or None

            # Save to database using create_job
            with contextlib.closing(next(get_db())) as db:
                resume_db = create_candidate(
                    db,
                    name=name,
                    email=email_id,
                    tech=tech,
                    job_code=job_code.split("_")[0],
                    resume=resume_text,
                    job_description=job_description,
                )
                st.success(f"✅ Resume '{resume_db.name}' saved successfully.")

        except Exception as e:
            st.error(f"❌ Error processing PDF: {e}")


def render_generate_questions():
    st.title("Generate Questions Based on Skillset")

    st.markdown(
        """
        <style>
        div[data-testid="stSearchbox"], div[data-testid="stSelectbox"], div[data-testid="stTextInput"] {
            width: 100% !important;
        }
        </style>
    """,
        unsafe_allow_html=True,
    )

    # initialize session state containers if missing
    st.session_state.setdefault("generated_questions", [])
    st.session_state.setdefault("current_job_code", None)

    # containers for pending operations (will be applied after rendering loop)
    st.session_state.setdefault("edits_pending", {})        # mapping idx -> {question, answer, keywords}
    st.session_state.setdefault("to_delete_indices", [])   # list of indices to delete

    # --- Search inputs (not in a form for simplicity) ---
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        with contextlib.closing(next(get_db())) as db:
            unique_candidate_id = get_unique_column_values(db, Candidate, ["candidate_code"])
        candidate_id = create_searchbox(
            label="Select Candidate",
            placeholder="Search..",
            key="candidate_code_searchbox",
            data=unique_candidate_id,
            display_fn=lambda x: x,
            return_fn=lambda x: x,
        )

    with col2:
        with contextlib.closing(next(get_db())) as db:
            unique_job_id = get_unique_column_values(db, Candidate, ["job_code"])
        job_id = create_searchbox(
            label="Select Job",
            placeholder="Search..",
            key="job_code_searchbox",
            data=unique_job_id,
            display_fn=lambda x: x,
            return_fn=lambda x: x,
        )

    with col3:
        with contextlib.closing(next(get_db())) as db:
            unique_cand_name = get_unique_column_values(db, Candidate, ["name"])
        name_id = create_searchbox(
            label="Select Name",
            placeholder="Name Search",
            key="name_searchbox",
            data=unique_cand_name,
            display_fn=lambda x: x,
            return_fn=lambda x: x,
        )

    with col4:
        n_questions = st.number_input(
            "Number of Questions", min_value=1, max_value=20, value=5, step=1, key="n_questions_input"
        )

    submitted = st.button("Search")

    # When Search pressed, fetch job_description and generate questions
    if submitted:
        job_description = None
        # open DB context here (important)
        with contextlib.closing(next(get_db())) as db:
            if candidate_id:
                job_description = get_column_value_by_condition(
                    db, Candidate, "candidate_code", candidate_id, "job_description"
                )
            elif job_id:
                job_description = get_column_value_by_condition(
                    db, Job, "job_code", job_id, "job_description"
                )
            elif name_id:
                job_description = get_column_value_by_condition(
                    db, Candidate, "name", name_id, "job_description"
                )

        if job_description:
            with st.spinner("Generating questions..."):
                try:
                    questions_data = generate_knowledge_for_tech(job_description, n_questions=n_questions)
                except Exception as exc:
                    st.error("Generation failed:")
                    st.exception(exc)
                    questions_data = []

            normalized = []
            for it in (questions_data or []):
                if not isinstance(it, dict):
                    continue
                normalized.append({
                    "question": it.get("question", "") or "",
                    "answer": it.get("answer", "") or "",
                    "keywords": it.get("keywords", []) or [],
                    "_raw": it,
                })

            st.session_state["generated_questions"] = normalized
            st.session_state["current_job_code"] = job_id

            # Reset any pending operations after generation
            st.session_state["edits_pending"] = {}
            st.session_state["to_delete_indices"] = []
        else:
            st.warning("No job description found for the selected item.")

    # ---------------------------
    # Safe helper callbacks used by buttons (mutate st.session_state only via on_click)
    # ---------------------------
    def _mark_delete(idx: int):
        lst = st.session_state.setdefault("to_delete_indices", [])
        if idx not in lst:
            lst.append(idx)

    def _save_edit(idx: int):
        qk = f"edit_q_input_{idx}"
        ak = f"edit_a_input_{idx}"
        kk = f"edit_k_input_{idx}"
        # read values from session_state (these keys exist if inputs were created)
        new_q = st.session_state.get(qk, "")
        new_a = st.session_state.get(ak, "")
        new_k_raw = st.session_state.get(kk, "")
        new_k_list = [k.strip() for k in new_k_raw.split(",") if k.strip()]
        edits = st.session_state.setdefault("edits_pending", {})
        edits[str(idx)] = {
            "question": new_q,
            "answer": new_a,
            "keywords": new_k_list,
        }
        # turn off the edit toggle so UI collapses on next rerun
        st.session_state[f"edit_toggle_{idx}"] = False

    def _cancel_edit(idx: int):
        # simply turn off edit mode; inputs remain in session_state but will be ignored
        st.session_state[f"edit_toggle_{idx}"] = False

    # ---------------------------
    # Display generated questions (if any)
    # ---------------------------
    if st.session_state.get("generated_questions"):
        st.subheader("Generated Questions")

        # Ensure per-item session keys are initialized BEFORE any widgets are created.
        # This avoids the StreamlitAPIException about changing session_state after widget instantiation.
        for idx, qa in enumerate(st.session_state["generated_questions"]):
            edit_key = f"edit_toggle_{idx}"
            q_input_key = f"edit_q_input_{idx}"
            a_input_key = f"edit_a_input_{idx}"
            k_input_key = f"edit_k_input_{idx}"

            # initialize edit toggle and input values only if they don't exist already
            st.session_state.setdefault(edit_key, False)
            # seed the input keys only if they are not already present (so user edits persist)
            st.session_state.setdefault(q_input_key, qa.get("question", ""))
            st.session_state.setdefault(a_input_key, qa.get("answer", ""))
            st.session_state.setdefault(k_input_key, ",".join(qa.get("keywords", []) or []))

        kept = []
        # Render each item. We DO NOT directly mutate generated_questions in-loop.
        for idx, qa in enumerate(st.session_state["generated_questions"]):
            q_text = qa.get("question", "")
            a_text = qa.get("answer", "")
            kws = qa.get("keywords", []) or []

            container = st.container()
            with container:
                st.markdown(f"**Q{idx+1}: {q_text}**")
                st.markdown(f"**Answer:** {a_text}")
                if kws:
                    st.markdown(f"**Keywords:** {', '.join(kws)}")

                # use a persistent checkbox to toggle edit mode (checkbox key was initialized above)
                edit_key = f"edit_toggle_{idx}"

                col_left, col_right = st.columns([1, 1])
                with col_left:
                    # the checkbox is bound to st.session_state[edit_key]
                    st.checkbox("Edit", value=st.session_state[edit_key], key=edit_key, help="Toggle to edit this Q/A")
                with col_right:
                    # Delete button uses on_click to safely mutate state
                    if st.button("🗑️ Delete", key=f"delete_btn_{idx}", on_click=_mark_delete, args=(idx,)):
                        st.warning(f"Marked Q{idx+1} for deletion")

                # If in edit mode, show inputs with stable keys (already seeded above)
                if st.session_state.get(edit_key, False):
                    q_input_key = f"edit_q_input_{idx}"
                    a_input_key = f"edit_a_input_{idx}"
                    k_input_key = f"edit_k_input_{idx}"

                    # These widgets persist their values in st.session_state so callbacks can read them
                    st.text_input("Edit Question", value=st.session_state[q_input_key], key=q_input_key)
                    st.text_area("Edit Answer", value=st.session_state[a_input_key], key=a_input_key, height=120)
                    st.text_input("Keywords (comma separated)", value=st.session_state[k_input_key], key=k_input_key)

                    col_save, col_cancel = st.columns([1, 1])
                    with col_save:
                        st.button("Save", key=f"save_edit_{idx}", on_click=_save_edit, args=(idx,))
                    with col_cancel:
                        st.button("Cancel", key=f"cancel_edit_{idx}", on_click=_cancel_edit, args=(idx,))

            # build kept list (we'll apply edits/deletes after the loop)
            kept.append(qa)

        # ---------------------------
        # After rendering: apply pending deletes / edits (safe to mutate session state now)
        # ---------------------------
        to_delete = sorted(set(st.session_state.get("to_delete_indices", [])), reverse=True)  # reverse so indices remain valid
        if to_delete:
            new_kept = [item for i, item in enumerate(kept) if i not in to_delete]
            st.session_state["generated_questions"] = new_kept
            # clear pending deletes
            st.session_state["to_delete_indices"] = []
            st.success(f"Deleted {len(to_delete)} question(s).")
        else:
            # apply edits if any
            edits_pending = st.session_state.get("edits_pending", {}) or {}
            if edits_pending:
                for idx_str, changes in edits_pending.items():
                    try:
                        i = int(idx_str)
                    except ValueError:
                        continue
                    if 0 <= i < len(kept):
                        kept[i].update(changes)
                st.session_state["generated_questions"] = kept
                # clear pending edits
                st.session_state["edits_pending"] = {}
                st.success(f"Applied {len(edits_pending)} edit(s).")
            else:
                # defensive: persist kept as-is
                st.session_state["generated_questions"] = kept

        st.markdown("---")

        # Approve & Save All
        if st.button("✅ Approve & Save All"):
            # Save generated questions to DB (one Question row per QA)
            gen_qas = st.session_state.get("generated_questions", [])
            job_code = st.session_state.get("current_job_code")

            if not gen_qas:
                st.info("No generated questions to save.")
            else:
                with contextlib.closing(next(get_db())) as db:
                    try:
                        inserted = 0
                        for qa in gen_qas:
                            # defensive defaults
                            q_text = qa.get("question", "") or ""
                            a_text = qa.get("answer", "") or ""
                            kws = qa.get("keywords", []) or []

                            # create model instance (adjust field names if your model differs)
                            q_row = Question(
                                job_code=job_code,
                                question_text=q_text,
                                model_answer=a_text,
                                keywords=kws,
                                model_answer_embedding=None
                            )
                            if a_text:
                                try:
                                    # generate embedding (may raise)
                                    embedding = get_embedding(a_text)
                                    # Ensure embedding is JSON-serializable (list of floats)
                                    q_row.model_answer_embedding = embedding
                                    # Optional: small sleep to avoid hitting strict rate limits if many items
                                    # time.sleep(0.1)
                                except Exception as emb_exc:
                                    # Log the error but continue saving the question without embedding
                                    st.warning(
                                        f"Embedding generation failed for question {idx+1}: {str(emb_exc)}"
                                    )
                                    # For debugging (developer mode) include traceback
                                    st.write(traceback.format_exc())
                                    q_row.model_answer_embedding = None

                            db.add(q_row)
                            inserted += 1

                        # commit once for all inserts
                        db.commit()

                        # clear session state and related pending operations
                        st.session_state["generated_questions"] = []
                        st.session_state["edits_pending"] = {}
                        st.session_state["to_delete_indices"] = []
                        st.session_state["current_job_code"] = None

                        st.success(f"Saved {inserted} question(s) to DB.")
                    except Exception as e:
                        # rollback on error and show exception
                        try:
                            db.rollback()
                        except Exception:
                            pass
                        st.exception(e)


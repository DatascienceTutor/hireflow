"""
Hiring manager UI components.
This file contains the render functions for each tab displayed in app.py.
It no longer contains its own router or sidebar.
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
from sqlalchemy import text, distinct,func
from services.job_service import create_job
from services.candidate_service import create_candidate
import fitz  # PyMuPDF
from pathlib import Path
import uuid
from models.job import Job
from models.candidate import Candidate
from models.candidate_answer import CandidateAnswer
from streamlit_searchbox import st_searchbox
import re
from services.openai_service import generate_knowledge_for_tech, get_embedding
from services.common import get_unique_column_values, get_column_value_by_condition, create_searchbox
from models.question import Question

# --- Main Dashboard Tab ---

def render_manager():
    """
    Renders the main dashboard tab with a list of candidates to review.
    """
    st.subheader("Candidate Interview Reviews")
    st.write("Review completed interviews and their scores.")

    try:
        with contextlib.closing(next(get_db())) as db:
            # Query to get all candidates who have answers, their total score,
            # and their name from the candidates table.
            # We join CandidateAnswers with Candidate on candidate_id/candidate_code
            completed_interviews = (
                db.query(
                    Candidate.name,
                    Candidate.candidate_code,
                    func.sum(CandidateAnswer.llm_score).label("overall_score"),
                )
                .join(
                    CandidateAnswer,
                    Candidate.candidate_code == CandidateAnswer.candidate_id,
                )
                .filter(CandidateAnswer.llm_score != None)
                .group_by(Candidate.candidate_code, Candidate.name)
                .all()
            )

        if not completed_interviews:
            st.info("No completed candidate interviews to review yet.")
            return

        # Display each candidate in an expander
        for candidate in completed_interviews:
            expander_title = f"**{candidate.name}** ({candidate.candidate_code}) - Overall Score: **{candidate.overall_score or 'N/A'}**"
            with st.expander(expander_title):
                st.write(f"#### Detailed Review for {candidate.name}")

                # Fetch individual answers for this candidate
                with contextlib.closing(next(get_db())) as db_inner:
                    answers = (
                        db_inner.query(
                            Question.question_text,
                            CandidateAnswer.answer_text,
                            CandidateAnswer.llm_score,
                            CandidateAnswer.feedback,
                        )
                        .join(
                            CandidateAnswer,
                            Question.id == CandidateAnswer.question_id,
                        )
                        .filter(
                            CandidateAnswer.candidate_id == candidate.candidate_code
                        )
                        .all()
                    )

                if not answers:
                    st.warning("No individual answers found for this candidate.")
                    continue

                # Loop through and display each Q/A
                for i, answer in enumerate(answers):
                    st.markdown(f"---")
                    st.markdown(f"**Q{i+1}: {answer.question_text}**")
                    st.markdown(f"**Candidate's Answer:**")
                    st.text_area(
                        "Answer",
                        value=answer.answer_text,
                        disabled=True,
                        key=f"ans_{candidate.candidate_code}_{i}",
                        label_visibility="collapsed",
                    )
                    st.markdown(
                        f"**Score:** `{answer.llm_score or 'Not Scored'}`"
                    )
                    st.markdown(f"**Feedback:**")
                    st.info(f"{answer.feedback or 'No feedback provided.'}")

    except Exception as e:
        st.error(f"An error occurred while fetching candidate reviews:")
        st.exception(e)


# --- JD Upload Tab ---

def render_jd_upload_page():
    """Renders the Job Description (JD) upload tab."""
    st.subheader("Upload New Job Description")
    st.caption("Upload a PDF to create a new job entry in the system.")
    
    tech_options = [
        "JavaScript", "Python", "Java", "React.js", "Node.js", 
        "TypeScript", "C# / .NET", "SQL", "Docker", "Kubernetes",
    ]

    # Use a form for cleaner submission
    with st.form("jd_upload_form"):
        uploaded_file = st.file_uploader("Job Description (PDF)", type=["pdf"])
        tech = st.selectbox("Select Primary Technology", tech_options)

        # Logic for placeholder
        job_title_placeholder = ""
        if uploaded_file:
            file_name_without_ext = Path(uploaded_file.name).stem
            unique_id = str(uuid.uuid4())[:8]
            job_title_placeholder = f"{file_name_without_ext.replace(' ','_').title()}_{unique_id}"
        
        title = st.text_input("Job Title", value=job_title_placeholder)
        
        # Form submit button
        submitted = st.form_submit_button("Upload and Save")

    if submitted:
        if not all([uploaded_file, tech, title]):
            st.warning("Please fill in all fields and upload a PDF.")
            return
        
        try:
            with st.spinner("Processing PDF and saving job..."):
                # Extract text from PDF
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                description = "\n".join([page.get_text() for page in doc])

                # Save to database using create_job
                with contextlib.closing(next(get_db())) as db:
                    job = create_job(db, tech=tech, title=title, description=description)
                    st.success(f"✅ Job '{job.title}' saved successfully with code `{job.job_code}`.")

        except Exception as e:
            st.error(f"❌ Error processing PDF: {e}")
            logging.error(f"JD Upload Error: {traceback.format_exc()}")

# --- Resume Upload Tab ---

def render_resume_upload_page():
    """Renders the Resume upload tab."""
    st.subheader("Upload Candidate Resume")
    st.caption("Upload a candidate's resume and link it to an existing job code.")
    
    tech_options = [
        "JavaScript", "Python", "Java", "React.js", "Node.js", 
        "TypeScript", "C# / .NET", "SQL", "Docker", "Kubernetes",
    ]

    # Use a form for cleaner submission
    with st.form("resume_upload_form"):
        job_code_display = None
        with contextlib.closing(next(get_db())) as db:
            unique_job_codes = get_unique_column_values(db, Job, ["job_code", "title"])
        
        job_code_display = create_searchbox(
            label="Select Job Code",
            placeholder="Search for a Job Code...",
            # Use a unique key to prevent conflicts with other tabs
            key="resume_job_code_searchbox", 
            data=unique_job_codes,
            display_fn=lambda x: f"{x[0]} - {x[1]}", # Cleaner display
            return_fn=lambda x: x[0], # Only return the code
        )
        
        tech = st.selectbox("Select Primary Technology", tech_options)
        uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

        # Name placeholder logic
        resume_name_placeholder = ""
        if uploaded_file:
            file_name_without_ext = Path(uploaded_file.name).stem
            resume_name_placeholder = f"{file_name_without_ext.replace(' ','_').title()}"
        
        name = st.text_input("Candidate Name", value=resume_name_placeholder)
        
        submitted = st.form_submit_button("Upload and Save")

    if submitted:
        if not all([uploaded_file, tech, job_code_display, name]):
            st.warning("Please fill in all fields and upload a PDF.")
            return

        try:
            with st.spinner("Processing resume and saving candidate..."):
                # Get job description (needs to be done after button click)
                job_description = None
                with contextlib.closing(next(get_db())) as db:
                     job_description = get_column_value_by_condition(
                         db, Job, "job_code", job_code_display, "description" # Fetch from Job table
                     )

                if not job_description:
                    st.error(f"Could not find job description for job code: {job_code_display}")
                    return

                # Extract text from PDF
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                resume_text = "\n".join([page.get_text() for page in doc])
                email_matches = re.findall(
                    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resume_text
                )
                email_id = email_matches[0] if email_matches else None

                # Save to database
                with contextlib.closing(next(get_db())) as db:
                    resume_db = create_candidate(
                        db,
                        name=name,
                        email=email_id,
                        tech=tech,
                        job_code=job_code_display, # Use the returned code
                        resume=resume_text,
                        job_description=job_description,
                    )
                    st.success(f"✅ Resume '{resume_db.name}' saved successfully.")

        except Exception as e:
            st.error(f"❌ Error processing PDF: {e}")
            logging.error(f"Resume Upload Error: {traceback.format_exc()}")

# --- Generate Questions Tab ---

def render_generate_questions_page():
    """Renders the tab for generating interview questions."""
    st.subheader("Generate Interview Questions")

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
    st.session_state.setdefault("edits_pending", {})
    st.session_state.setdefault("to_delete_indices", [])

    # --- Search inputs (not in a form for simplicity) ---
    st.write("First, find a job description to generate questions from.")
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        with contextlib.closing(next(get_db())) as db:
            unique_candidate_id = get_unique_column_values(db, Candidate, ["candidate_code"])
        candidate_id = create_searchbox(
            label="Select Candidate",
            placeholder="Search by Candidate...",
            key="gen_q_candidate_code_searchbox", # Unique key
            data=unique_candidate_id,
            display_fn=lambda x: x,
            return_fn=lambda x: x,
        )

    with col2:
        with contextlib.closing(next(get_db())) as db:
            # BUG FIX: Was querying Candidate table for job_code, should query Job table
            unique_job_id = get_unique_column_values(db, Job, ["job_code"]) 
        job_id = create_searchbox(
            label="Select Job",
            placeholder="Search by Job...",
            key="gen_q_job_code_searchbox", # Unique key
            data=unique_job_id,
            display_fn=lambda x: x,
            return_fn=lambda x: x,
        )

    with col3:
        with contextlib.closing(next(get_db())) as db:
            unique_cand_name = get_unique_column_values(db, Candidate, ["name"])
        name_id = create_searchbox(
            label="Select Name",
            placeholder="Search by Name...",
            key="gen_q_name_searchbox", # Unique key
            data=unique_cand_name,
            display_fn=lambda x: x,
            return_fn=lambda x: x,
        )

    with col4:
        n_questions = st.number_input(
            "Number of Questions", min_value=1, max_value=20, value=5, step=1, key="n_questions_input"
        )

    submitted = st.button("Search and Generate Questions")

    # When Search pressed, fetch job_description and generate questions
    if submitted:
        job_description = None
        with contextlib.closing(next(get_db())) as db:
            if candidate_id:
                job_description = get_column_value_by_condition(
                    db, Candidate, "candidate_code", candidate_id, "job_description"
                )
            elif job_id:
                # BUG FIX: Was looking for "job_description", Job model has "description"
                job_description = get_column_value_by_condition(
                    db, Job, "job_code", job_id, "description" 
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
            st.session_state["edits_pending"] = {}
            st.session_state["to_delete_indices"] = []
        else:
            st.warning("No job description found for the selected item.")

    # ---------------------------
    # Safe helper callbacks
    # ---------------------------
    def _mark_delete(idx: int):
        lst = st.session_state.setdefault("to_delete_indices", [])
        if idx not in lst:
            lst.append(idx)

    def _save_edit(idx: int):
        qk = f"edit_q_input_{idx}"
        ak = f"edit_a_input_{idx}"
        kk = f"edit_k_input_{idx}"
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
        st.session_state[f"edit_toggle_{idx}"] = False

    def _cancel_edit(idx: int):
        st.session_state[f"edit_toggle_{idx}"] = False

    # ---------------------------
    # Display generated questions (if any)
    # ---------------------------
    if st.session_state.get("generated_questions"):
        st.markdown("---")
        st.subheader("Review Generated Questions")

        # Initialize session keys before rendering widgets
        for idx, qa in enumerate(st.session_state["generated_questions"]):
            st.session_state.setdefault(f"edit_toggle_{idx}", False)
            st.session_state.setdefault(f"edit_q_input_{idx}", qa.get("question", ""))
            st.session_state.setdefault(f"edit_a_input_{idx}", qa.get("answer", ""))
            st.session_state.setdefault(f"edit_k_input_{idx}", ",".join(qa.get("keywords", []) or []))

        # --- UX Improvement: Process deletes and edits *before* rendering ---
        to_delete = sorted(set(st.session_state.get("to_delete_indices", [])), reverse=True)
        current_questions = st.session_state.get("generated_questions", [])
        
        if to_delete:
            new_kept = [item for i, item in enumerate(current_questions) if i not in to_delete]
            st.session_state["generated_questions"] = new_kept
            st.session_state["to_delete_indices"] = []
            st.success(f"Deleted {len(to_delete)} question(s).")
            st.rerun() # Rerun to show the updated list immediately
        
        edits_pending = st.session_state.get("edits_pending", {})
        if edits_pending:
            for idx_str, changes in edits_pending.items():
                try:
                    i = int(idx_str)
                    if 0 <= i < len(current_questions):
                        current_questions[i].update(changes)
                except ValueError:
                    continue
            st.session_state["generated_questions"] = current_questions
            st.session_state["edits_pending"] = {}
            st.success(f"Applied {len(edits_pending)} edit(s).")
            st.rerun() # Rerun to show the updated list
        # --- End of UX Improvement ---

        # Render each item
        for idx, qa in enumerate(st.session_state.get("generated_questions", [])):
            q_text = qa.get("question", "")
            a_text = qa.get("answer", "")
            kws = qa.get("keywords", []) or []

            # Use a container with a border to separate questions
            with st.container(border=True):
                st.markdown(f"**Q{idx+1}: {q_text}**")
                st.markdown(f"**Answer:** {a_text}")
                if kws:
                    st.markdown(f"**Keywords:** {', '.join(kws)}")

                edit_key = f"edit_toggle_{idx}"
                col_left, col_right = st.columns([1, 1])
                with col_left:
                    st.checkbox("Edit", value=st.session_state[edit_key], key=edit_key, help="Toggle to edit this Q/A")
                with col_right:
                    # on_click will mark for deletion, and the rerun at the top will process it
                    if st.button("🗑️ Delete", key=f"delete_btn_{idx}", on_click=_mark_delete, args=(idx,)):
                        st.warning(f"Marked Q{idx+1} for deletion")
                        st.rerun() # Immediate rerun to process delete

                # If in edit mode, show inputs
                if st.session_state.get(edit_key, False):
                    q_input_key = f"edit_q_input_{idx}"
                    a_input_key = f"edit_a_input_{idx}"
                    k_input_key = f"edit_k_input_{idx}"

                    st.text_input("Edit Question", key=q_input_key)
                    st.text_area("Edit Answer", key=a_input_key, height=120)
                    st.text_input("Keywords (comma separated)", key=k_input_key)

                    col_save, col_cancel = st.columns([1, 1])
                    with col_save:
                        # on_click will save and rerun
                        st.button("Save", key=f"save_edit_{idx}", on_click=_save_edit, args=(idx,))
                    with col_cancel:
                        st.button("Cancel", key=f"cancel_edit_{idx}", on_click=_cancel_edit, args=(idx,))
            
        st.markdown("---")

        # Approve & Save All
        if st.button("✅ Approve & Save All to Database"):
            gen_qas = st.session_state.get("generated_questions", [])
            job_code = st.session_state.get("current_job_code")

            if not gen_qas:
                st.info("No generated questions to save.")
            else:
                with st.spinner(f"Saving {len(gen_qas)} questions to database..."):
                    with contextlib.closing(next(get_db())) as db:
                        try:
                            inserted = 0
                            for idx, qa in enumerate(gen_qas):
                                q_text = qa.get("question", "") or ""
                                a_text = qa.get("answer", "") or ""
                                kws = qa.get("keywords", []) or []
                                
                                q_row = Question(
                                    job_code=job_code,
                                    question_text=q_text,
                                    model_answer=a_text,
                                    keywords=kws,
                                    model_answer_embedding=None
                                )
                                if a_text:
                                    try:
                                        embedding = get_embedding(a_text)
                                        q_row.model_answer_embedding = embedding
                                    except Exception as emb_exc:
                                        st.warning(
                                            f"Embedding generation failed for question {idx+1}: {str(emb_exc)}"
                                        )
                                        logging.error(f"Embedding Error: {traceback.format_exc()}")
                                        q_row.model_answer_embedding = None

                                db.add(q_row)
                                inserted += 1
                            
                            db.commit()
                            st.info("Questions are saved to database")
                            st.balloons()

                            # clear session state
                            st.session_state["generated_questions"] = []
                            st.session_state["edits_pending"] = {}
                            st.session_state["to_delete_indices"] = []
                            st.session_state["current_job_code"] = None

                            
                            # st.rerun() # Rerun to clear the UI

                        except Exception as e:
                            try:
                                db.rollback()
                            except Exception:
                                pass
                            st.exception(e)


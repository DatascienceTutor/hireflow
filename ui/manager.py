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
from sqlalchemy import text, distinct, func
from services.job_service import create_job
from services.candidate_service import create_candidate
import fitz  # PyMuPDF
from pathlib import Path
import uuid

# --- Updated Model Imports ---
from models.job import Job
from models.candidate import Candidate
from models.candidate_answer import CandidateAnswer
from models.question import Question
from models.interview import Interview  # <-- Import Interview model
from sqlalchemy.exc import IntegrityError 
from datetime import datetime

from streamlit_searchbox import st_searchbox
import re
from services.openai_service import generate_knowledge_for_tech, get_embedding
from services.common import (
    get_unique_column_values,
    get_column_value_by_condition,
    create_searchbox,
)

# --- Main Dashboard Tab (Renamed and Updated) ---


def render_manager():
    """
    Renders the main dashboard tab by querying the Interview table.
    """

    manager_email = st.session_state.get("user_email")
    if not manager_email:
        st.warning("Could not identify your session. Please log in again.")
        return
    
    selected_candidate_id = None
    selected_status = "All"

    try:
        with contextlib.closing(next(get_db())) as db:

            candidates_for_manager = (
                db.query(Candidate.id, Candidate.name, Candidate.candidate_code)
                .join(Interview, Candidate.id == Interview.candidate_id)
                .join(Job, Job.id == Interview.job_id)
                .filter(Job.manager_email == manager_email)
                .distinct() # Ensure each candidate appears only once
                .all()
            )
            
            status_options = ["All", "Pending", "Completed"]

            # --- 3. Add the filter widgets ---
            st.markdown("---")
            col1, col2 = st.columns([3, 2])

            with col1:
                # NEW: Searchbox for Candidate
                selected_candidate_id = create_searchbox(
                    label="Search by Candidate Name",
                    placeholder="Type a candidate's name...",
                    key="dashboard_candidate_search",
                    data=candidates_for_manager,
                    display_fn=lambda x: f"{x[1]}_({x[2]})", # Show Name (Code)
                    return_fn=lambda x: x[0] if x else None,  # Return the Candidate ID
                )
            
            with col2:
                selected_status = st.selectbox(
                    "Filter by Status",
                    options=status_options,
                )
            st.markdown("---")

            # --- NEW, SIMPLER QUERY ---
            # Join Interview -> Candidate (on ID) -> Job (on ID)
            base_query = (
                db.query(
                    Candidate.id,
                    Candidate.name,
                    Candidate.candidate_code,
                    Job.title.label("job_title"),
                    Interview.status,
                    Interview.evaluation_status,
                    Interview.final_score,
                    Interview.id.label("interview_id")
                )
                .join(Candidate, Candidate.id == Interview.candidate_id)
                .join(Job, Job.id == Interview.job_id)
                .filter(Job.manager_email == manager_email)
            )
            # --- END NEW QUERY ---
        
        if selected_candidate_id: # If a candidate was selected
                base_query = base_query.filter(Candidate.id == selected_candidate_id)
            
        if selected_status != "All": # If user selected "Pending" or "Completed"
                base_query = base_query.filter(Interview.status == selected_status)
        
        if selected_candidate_id or selected_status != "All":
                reviews = base_query.order_by(Interview.created_at.desc()).all()
        else:
            # No filters selected, show message instead of all results
            st.info("Please select a candidate or filter by status to see results.")
            return # Stop execution to prevent showing all results

        if not reviews:
            st.info("No interviews found. Upload JD and candidate resumes to create them.")
            return

        # Display each interview in an expander
        for review in reviews:
            # You can now show the job title and interview status
            title = f"**{review.name}** ({review.candidate_code}) for **{review.job_title}**"
            score = (
                f"**{review.final_score:.1f}**"
                if review.final_score is not None
                else "**N/A**"
            )
            
            expander_title = (
                f"{title} | Status: **{review.status}** | Score: {score}"
            )

            with st.expander(expander_title):
                st.subheader("Candidate Interview Reviews")
                st.write("Review completed interviews and their scores.")
                st.write(f"#### Detailed Review for {review.name}")
                st.write(f"**Overall Score (0-100):** {score}")
                st.write(f"**Evaluation Status:** {review.evaluation_status}")

                # This inner query to get individual answers is still correct
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
                            CandidateAnswer.interview_id == review.interview_id
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
                        key=f"ans_{review.candidate_code}_{review.interview_id}_{i}",
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

    tech_options_a = [
        "JavaScript", "Python", "Java", "React.js", "Node.js",
        "TypeScript", "C# / .NET", "SQL", "Docker", "Kubernetes",
    ]

    uploaded_file = st.file_uploader("Job Description (PDF)", type=["pdf"])
    tech = st.selectbox("Select Primary Technology", tech_options_a)
    job_title_placeholder = ""
    if uploaded_file and tech:
        file_name_without_ext = Path(uploaded_file.name).stem
        unique_id = str(uuid.uuid4())[:8]
        job_title_placeholder = (
            f"{file_name_without_ext.replace(' ','_').title()}_{unique_id}"
        )
    title = st.text_input("Job Title",value=job_title_placeholder)
    
    submitted = st.button("Upload and Save JD")
    manager_email=st.session_state.get("user_email")
    if submitted:
        if not all([uploaded_file, tech, title]):
            st.warning("Please fill in all fields and upload a PDF.")
            return
        
        try:
            with st.spinner("Processing PDF and saving job..."):
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                description = "\n".join([page.get_text() for page in doc])

                with contextlib.closing(next(get_db())) as db:
                    job = create_job(
                        db, tech=tech, title=title, description=description,manager_email=manager_email,
                    )
                    st.success(
                        f"✅ Job '{job.title}' saved successfully with code `{job.job_code}`."
                    )

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

    job_code_display = None
    with contextlib.closing(next(get_db())) as db:
        unique_job_codes = get_unique_column_values(
            db, Job, ["id","job_code", "title"]
        )

    job_code_display = create_searchbox(
        label="Select Job Code",
        placeholder="Search for a Job Code...",
        key="resume_job_code_searchbox",
        data=unique_job_codes,
        display_fn=lambda x: f"{x[1]}_{x[2]}",
        return_fn=lambda x: x[0],
    )
    
    uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

    resume_name_placeholder = ""
    if uploaded_file:
        file_name_without_ext = Path(uploaded_file.name).stem
        resume_name_placeholder = (
            f"{file_name_without_ext.replace(' ','_').title()}"
        )
    
    name = st.text_input("Candidate Name", value=resume_name_placeholder)
    if job_code_display:
        with contextlib.closing(next(get_db())) as db:
            tech = get_column_value_by_condition(
                            db, Job, "id", job_code_display, "tech"
                        )
    
    submitted = st.button("Upload and Save Resume")

    if submitted:
        if not all([uploaded_file, tech, job_code_display, name]):
            st.warning("Please fill in all fields and upload a PDF.")
            return

        try:
            with st.spinner("Processing resume and saving candidate..."):
                job_description = None
                with contextlib.closing(next(get_db())) as db:
                    job_description = get_column_value_by_condition(
                        db, Job, "id", job_code_display, "description"
                    )

                if not job_description:
                    st.error(
                        f"Could not find job description for job code: {job_code_display}"
                    )
                    return

                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                resume_text = "\n".join([page.get_text() for page in doc])
                email_matches = re.findall(
                    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-B_.-]+\.[a-zA-Z]{2,}", resume_text
                )
                email_id = email_matches[0] if email_matches else None

                with contextlib.closing(next(get_db())) as db:
                    resume_db = create_candidate(
                        db,
                        name=name,
                        email=email_id,
                        tech=tech,
                        resume=resume_text,
                        job_id=job_code_display
                    )
                    st.success(
                        f"✅ Resume '{resume_db.name}' saved successfully."
                    )

        except Exception as e:
            st.error(f"❌ Error processing PDF: {e}")
            logging.error(f"Resume Upload Error: {traceback.format_exc()}")


# --- Generate Questions Tab ---

def render_assign_interview_page():
    """Renders the tab for assigning an existing job interview to an existing candidate."""
    st.subheader("Assign Interview to Candidate")
    st.caption("Select a candidate and one of your jobs to create an interview assignment.")

    manager_email = st.session_state.get("user_email")
    if not manager_email:
        st.warning("Could not identify manager session. Please log in again.")
        return
    st.markdown("##### 1. Select Candidate")
    candidate_code = None
    selected_candidate = None
    with contextlib.closing(next(get_db())) as db:
        # Fetch all candidates (code and name) for the searchbox
        all_candidates = get_unique_column_values(db, Candidate, ["id","candidate_code", "name"])
    
    candidate_code_display = create_searchbox(
        label="Search for Candidate by Code or Name",
        placeholder="Type code or name...",
        key="assign_candidate_searchbox",
        data=all_candidates,
        display_fn=lambda x: f"{x[1]}_{x[2]}", # Show code and name
        return_fn=lambda x: x[0] if x else None, # Return only the code
    )

    if candidate_code_display:
        # Fetch the full candidate object once selected
        with contextlib.closing(next(get_db())) as db:
            selected_candidate = db.query(Candidate).filter(Candidate.id == candidate_code_display).first()
        if selected_candidate:
            st.success(f"Selected Candidate: **{selected_candidate.name}** ({selected_candidate.candidate_code})")
            candidate_code = selected_candidate.id # Store the code
        else:
            st.error("Selected candidate not found in database.")

    st.markdown("##### 2. Select Job")
    job_code = None
    selected_job = None

    if candidate_code: # Only show job selection if a candidate is selected
        with contextlib.closing(next(get_db())) as db:
            # Fetch only jobs created by this manager
            manager_jobs = db.query(Job.id,Job.job_code, Job.title).all()

        if not manager_jobs:
            st.warning("You have not created any jobs yet. Please upload a JD first.")
            return

        # Searchbox to select job
        job_code_display = create_searchbox(
            label="Search for one of your Job Codes",
            placeholder="Type code or title...",
            key="assign_job_searchbox",
            data=manager_jobs,
            display_fn=lambda x: f"{x[1]}_{x[2]}", # Show code and title
            return_fn=lambda x: x[0] if x else None, # Return only the code
        )

        if job_code_display:
             # Fetch the full job object
            with contextlib.closing(next(get_db())) as db:
                selected_job = db.query(Job).filter(Job.id == job_code_display).first()
            if selected_job:
                st.success(f"Selected Job: **{selected_job.title}** ({selected_job.job_code})")
                job_code = selected_job.id # Store the code
            else:
                 st.error("Selected job not found.")
    st.markdown("---")
    if selected_candidate and selected_job:
        st.markdown(f"Assign interview for **{selected_job.title}** to **{selected_candidate.name}**?")
        if st.button("Assign Interview", type="primary"):
            try:
                with contextlib.closing(next(get_db())) as db:
                    # Check if this assignment already exists
                    existing_interview = db.query(Interview).filter(
                        Interview.candidate_id == selected_candidate.id, # Use candidate's integer ID
                        Interview.job_id == selected_job.id          # Use job's integer ID
                    ).first()

                    if existing_interview:
                        st.warning(f"An interview for this job has already been assigned to {selected_candidate.name} (Status: {existing_interview.status}).")
                    else:
                        # Create the new Interview record
                        new_interview = Interview(
                            job_id=selected_job.id,
                            candidate_id=selected_candidate.id,
                            status="Pending", # Or "Assigned"
                            evaluation_status="Not Evaluated",
                            created_at=datetime.utcnow()
                        )
                        db.add(new_interview)
                        db.commit()
                        st.success(f"Interview for '{selected_job.title}' successfully assigned to {selected_candidate.name}!")
                        st.balloons()
                        # Optionally clear selections or rerun? Might be better to keep selections
                        # st.rerun()

            except IntegrityError:
                 db.rollback()
                 st.error("Database error: Could not create the interview assignment. It might already exist.")
            except Exception as e:
                db.rollback()
                st.error(f"An unexpected error occurred: {e}")
                logging.exception("Error assigning interview:")

    else:
        st.info("Select both a candidate and a job to enable assignment.")


def render_generate_questions_page():
    """
    Renders the tab for generating interview questions ON DEMAND via API.
    Workflow: Select Candidate -> Select Pending Interview/Job -> Generate.
    Uses the description ONLY from the selected JOB.
    """
    st.subheader("Generate Interview Questions")
    st.caption("Select a candidate, then select one of their pending interviews to generate questions.")

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

    st.session_state.setdefault("genq_selected_candidate_info", None) # Stores (code, name, id)
    st.session_state.setdefault("genq_selected_job_code", None)
    # Re-use existing state for generated questions if desired, or use new keys
    st.session_state.setdefault("generated_questions_api", []) # Use a different key if keeping knowledge bank tab
    st.session_state.setdefault("current_job_code_api", None)  # Use a different key
    st.session_state.setdefault("edits_pending_api", {})      # Use a different key
    st.session_state.setdefault("to_delete_indices_api", [])  # Use a different key

    st.markdown("##### 1. Select Candidate")
    selected_candidate_info = st.session_state.genq_selected_candidate_info # Get current selection
    candidate_id_for_query = selected_candidate_info[0] if selected_candidate_info else None

    with contextlib.closing(next(get_db())) as db:
        # Fetch candidate code, name, and ID
        all_candidates = get_unique_column_values(db, Candidate, ["id","candidate_code", "name"])

    # Searchbox to select candidate
    candidate_selection = create_searchbox(
        label="Search for Candidate by Code or Name",
        placeholder="Type code or name...",
        key="genq_candidate_searchbox_v3", # Unique key
        data=all_candidates,
        display_fn=lambda x: f"{x[1]}_{x[2]}", # Show code and name
        # Return the whole tuple (code, name, id)
        return_fn=lambda x: x if x else None
    )

    if candidate_selection != st.session_state.genq_selected_candidate_info:
        st.session_state.genq_selected_candidate_info = candidate_selection
        st.session_state.genq_selected_job_code = None
        st.rerun()
    
    if st.session_state.genq_selected_candidate_info:
        st.success(f"Selected Candidate: **{st.session_state.genq_selected_candidate_info[1]}** ({st.session_state.genq_selected_candidate_info[2]})")
    else:
        st.info("Select a candidate to see their pending interviews.")
        st.stop()
    
    st.markdown("##### 2. Select Pending Interview / Job")
    pending_jobs_for_candidate = []
    selected_job_code = st.session_state.genq_selected_job_code # Get current selection
 
    with contextlib.closing(next(get_db())) as db:
        pending_interviews_query = (
            db.query(Job.id,Job.job_code, Job.title) # Select Job details needed for display/return
            .join(Interview, Job.id == Interview.job_id)
            .filter(Interview.candidate_id == candidate_id_for_query) # Filter by selected candidate ID
            .filter(Interview.status == "Pending")
            .order_by(Job.title) # Optional: Order the list
            .all()
        )
        pending_jobs_for_candidate = pending_interviews_query
    if not pending_jobs_for_candidate:
        st.warning(f"No pending interviews found for {st.session_state.genq_selected_candidate_info[1]}. Assign an interview first.")
        # Clear job selection state if list becomes empty
        st.session_state.genq_selected_job_code = None
        st.stop() # Stop if no jobs to select
    else:
        # Use searchbox for the filtered jobs
        job_selection = create_searchbox(
            label="Select Pending Job Interview",
            placeholder="Select from pending interviews...",
            key="genq_job_searchbox_v3", # Unique key
            data=pending_jobs_for_candidate,
            # Display job code and title
            display_fn=lambda x: f"{x[1]}_{x[2]}",
            # Return the job_code
            return_fn=lambda x: x if x else None
        )
        if job_selection != st.session_state.genq_selected_job_code:
            st.session_state.genq_selected_job_code = job_selection
            st.rerun() # Rerun if job selection changes

        if st.session_state.genq_selected_job_code:
             st.success(f"Selected Job: **{st.session_state.genq_selected_job_code[1]}**({st.session_state.genq_selected_job_code[2]})")
        else:
             st.info("Select a pending interview/job for the chosen candidate.")
    
    st.markdown("---")
    n_questions = st.number_input(
        "Number of Questions to Generate", min_value=1, max_value=20, value=5, step=1,
        key="n_questions_input_v3" # Unique key
    )

    can_generate = bool(st.session_state.genq_selected_candidate_info and st.session_state.genq_selected_job_code)

    if st.button("Generate Questions", disabled=not can_generate,type='primary'):
        job_code_to_use = st.session_state.genq_selected_job_code[0]
        job_description = None

        # Fetch the description ONLY from the selected JOB CODE
        with contextlib.closing(next(get_db())) as db:
            selected_job_obj = db.query(Job.description).filter(Job.id == job_code_to_use).first()
            if selected_job_obj:
                job_description = selected_job_obj.description
            else:
                st.error(f"Critical Error: Could not find details for the selected job code: {job_code_to_use}")
                st.stop() # Stop if job vanished somehow

        if job_description:
            st.info(f"Using description from selected Job: {st.session_state.genq_selected_job_code[1]}")
            st.session_state["current_job_code_api"] = job_code_to_use # Store for saving

            with st.spinner("Generating questions..."):
                try:
                    # Make sure generate_knowledge_for_tech exists and works
                    questions_data = generate_knowledge_for_tech(
                        job_description, n_questions=n_questions
                    )

                    # --- Clear old edit/display state BEFORE setting new questions ---
                    keys_to_delete = [k for k in st.session_state if k.startswith(("edit_q_api_", "edit_a_api_", "edit_k_api_", "edit_toggle_api_", "delete_btn_api_"))]
                    for key in keys_to_delete: del st.session_state[key]
                    st.session_state["edits_pending_api"] = {}
                    st.session_state["to_delete_indices_api"] = []
                    # --- End clearing state ---

                    if questions_data: # Normalize and store
                         normalized = []
                         for it in (questions_data or []):
                             # (Your normalization logic - same as before)
                             if not isinstance(it, dict): continue
                             prompt = it.get("question", "") or ""
                             ref = it.get("answer", "") or ""
                             kws = it.get("keywords", []) or []
                             if isinstance(kws, str): kws = [k.strip() for k in kws.split(",") if k.strip()]
                             if not prompt or not ref: continue
                             normalized.append({"question": prompt, "answer": ref, "keywords": kws})

                         st.session_state["generated_questions_api"] = normalized
                         # Don't rerun here, let the display section render immediately
                    else:
                         st.warning("API returned no valid questions for this description.")
                         st.session_state["generated_questions_api"] = [] # Clear

                except Exception as exc:
                     st.error("Question generation failed:")
                     st.exception(exc)
                     st.session_state["generated_questions_api"] = [] # Clear
        else:
             st.warning(f"Job description for '{job_code_to_use}' is empty. Cannot generate questions.")
             st.session_state["generated_questions_api"] = [] # Clear

    elif not can_generate:
         st.info("Select both a candidate and one of their pending interviews to enable question generation.")


    # --- Step 4: Display/Edit Generated Questions ---
    # Using the specific session state keys for this workflow

    # --- Safe helper callbacks (use API-specific keys) ---
    def _mark_delete_api(idx: int):
        lst = st.session_state.setdefault("to_delete_indices_api", [])
        if idx not in lst: lst.append(idx)

    def _save_edit_api(idx: int):
        # Use keys like 'edit_q_api_{idx}'
        qk = f"edit_q_api_{idx}"
        ak = f"edit_a_api_{idx}"
        kk = f"edit_k_api_{idx}"
        new_q = st.session_state.get(qk, "")
        new_a = st.session_state.get(ak, "")
        new_k_raw = st.session_state.get(kk, "")
        new_k_list = [k.strip() for k in new_k_raw.split(",") if k.strip()]
        edits = st.session_state.setdefault("edits_pending_api", {})
        edits[str(idx)] = {"question": new_q, "answer": new_a, "keywords": new_k_list}
        st.session_state[f"edit_toggle_api_{idx}"] = False # Close edit box

    def _cancel_edit_api(idx: int):
        st.session_state[f"edit_toggle_api_{idx}"] = False # Close edit box


    # --- Process Deletes/Edits Before Rendering List ---
    to_delete = sorted(set(st.session_state.get("to_delete_indices_api", [])), reverse=True)
    current_questions = st.session_state.get("generated_questions_api", [])

    if to_delete:
        new_kept = [item for i, item in enumerate(current_questions) if i not in to_delete]
        st.session_state["generated_questions_api"] = new_kept
        st.session_state["to_delete_indices_api"] = []
        st.success(f"Deleted {len(to_delete)} question(s).")
        st.rerun()

    edits_pending = st.session_state.get("edits_pending_api", {})
    if edits_pending:
        modified = False
        for idx_str, changes in edits_pending.items():
            try:
                i = int(idx_str)
                if 0 <= i < len(current_questions):
                    current_questions[i].update(changes)
                    modified = True
            except ValueError: continue
        if modified:
            st.session_state["generated_questions_api"] = current_questions
            st.session_state["edits_pending_api"] = {}
            st.success(f"Applied {len(edits_pending)} edit(s).")
            st.rerun()

    # --- Display generated questions ---
    if st.session_state.get("generated_questions_api"):
        st.markdown("---")
        st.subheader("Review Generated Questions")

        # Initialize widget state keys before creating widgets
        for idx, qa in enumerate(st.session_state["generated_questions_api"]):
            st.session_state.setdefault(f"edit_toggle_api_{idx}", False)
            # Set default value for inputs based on current question data,
            # BUT only if the key doesn't already exist (to preserve user edits between reruns)
            st.session_state.setdefault(f"edit_q_api_{idx}", qa.get("question", ""))
            st.session_state.setdefault(f"edit_a_api_{idx}", qa.get("answer", ""))
            st.session_state.setdefault(f"edit_k_api_{idx}", ",".join(qa.get("keywords", []) or []))

        # Render loop
        for idx, qa in enumerate(st.session_state["generated_questions_api"]):
            q_text = qa.get("question", "")
            a_text = qa.get("answer", "")
            kws = qa.get("keywords", []) or []

            with st.container(border=True):
                st.markdown(f"**Q{idx+1}: {q_text}**")
                st.markdown(f"**Answer:** {a_text}")
                if kws: st.markdown(f"**Keywords:** {', '.join(kws)}")

                edit_key = f"edit_toggle_api_{idx}"
                col_left, col_right = st.columns([1, 1])
                with col_left:
                    # Checkbox value comes from session state
                    st.checkbox("Edit", key=edit_key, help="Toggle to edit this Q/A")
                with col_right:
                    # Delete uses on_click callback
                    st.button("🗑️ Delete", key=f"delete_btn_api_{idx}", on_click=_mark_delete_api, args=(idx,))

                # Edit mode display
                if st.session_state.get(edit_key, False):
                    q_input_key = f"edit_q_api_{idx}"
                    a_input_key = f"edit_a_api_{idx}"
                    k_input_key = f"edit_k_api_{idx}"

                    # Text inputs/area get their value from session state via key
                    st.text_input("Edit Question", key=q_input_key)
                    st.text_area("Edit Answer", key=a_input_key, height=120)
                    st.text_input("Keywords (comma separated)", key=k_input_key)

                    col_save, col_cancel = st.columns([1, 1])
                    with col_save:
                        st.button("Save", key=f"save_edit_api_{idx}", on_click=_save_edit_api, args=(idx,))
                    with col_cancel:
                        st.button("Cancel", key=f"cancel_edit_api_{idx}", on_click=_cancel_edit_api, args=(idx,))

        # --- Save Button ---
        st.markdown("---")
        if st.button("✅ Approve & Send to Candidate"):
            gen_qas_to_save = st.session_state.get("generated_questions_api", [])
            job_code_to_save = st.session_state.get("current_job_code_api") # Use API-specific key

            if not gen_qas_to_save:
                st.info("No generated questions to save.")
            elif not job_code_to_save:
                 st.error("Cannot save: Job code is missing. Please regenerate questions.")
            else:
                with st.spinner(f"Saving {len(gen_qas_to_save)} questions to database for job {job_code_to_save}..."):
                    with contextlib.closing(next(get_db())) as db:
                        try:
                            inserted = 0
                            for idx, qa_save in enumerate(gen_qas_to_save):
                                # (Your existing Question object creation logic...)
                                q_row = Question(
                                    job_id=job_code_to_save, # Use correct job code
                                    question_text=qa_save.get("question", ""),
                                    model_answer=qa_save.get("answer", ""),
                                    keywords=qa_save.get("keywords", []),
                                    model_answer_embedding=None, # Embedding logic below
                                )
                                # (Your existing embedding generation logic...)
                                a_text_save = qa_save.get("answer", "")
                                if a_text_save:
                                    try:
                                        embedding = get_embedding(a_text_save)
                                        q_row.model_answer_embedding = embedding
                                    except Exception as emb_exc:
                                         st.warning(f"Embedding failed for Q{idx+1}: {emb_exc}")
                                         logging.error(f"Embedding Error: {traceback.format_exc()}")
                                         q_row.model_answer_embedding = None

                                db.add(q_row)
                                inserted += 1

                            db.commit()
                            st.success(f"Saved {inserted} question(s) to DB for job {job_code_to_save}.")
                            st.balloons()

                            # Clear state after successful save
                            st.session_state["generated_questions_api"] = []
                            st.session_state["edits_pending_api"] = {}
                            st.session_state["to_delete_indices_api"] = []
                            st.session_state["current_job_code_api"] = None

                        except Exception as e:
                            try: db.rollback()
                            except Exception: pass
                            st.error("Database error occurred while saving.")
                            st.exception(e)

"""
Hiring manager dashboard (post-login).
"""

import streamlit as st
import contextlib
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
from services.openai_service import generate_knowledge_for_tech


def get_unique_column_values(db: Session, table_class, column_names: list[str]) -> list:
    """
    Fetches unique values of one or more columns from the specified table.

    :param db: SQLAlchemy Session
    :param table_class: SQLAlchemy model class (e.g., Job)
    :param column_names: List of column names as strings
    :return: List of unique values (list of strings if one column, list of tuples if multiple)
    """
    # Validate columns
    columns = []
    for col_name in column_names:
        col = getattr(table_class, col_name, None)
        if col is None:
            raise ValueError(
                f"Column '{col_name}' does not exist in {table_class.__name__} table."
            )
        columns.append(col)

    # Query distinct values
    unique_values = db.query(*columns).distinct().all()

    # Return based on number of columns
    if len(columns) == 1:
        return [value[0] for value in unique_values]  # Flatten for single column
    else:
        return unique_values  # List of tuples for multiple columns


# job_codes = get_unique_column_values(db, Job, "job_code")
# titles = get_unique_column_values(db, Job, "title")


def get_column_value_by_condition(
    db: Session, table_class, filter_column: str, filter_value: str, target_column: str
) -> str:
    """
    Fetches the value of target_column from table_class where filter_column matches filter_value.

    :param db: SQLAlchemy Session
    :param table_class: SQLAlchemy model class (e.g., Job)
    :param filter_column: Column name to filter by (e.g., 'job_code')
    :param filter_value: Value to match in filter_column
    :param target_column: Column name whose value you want to retrieve (e.g., 'description')
    :return: Value of target_column or None if not found
    """
    # Get columns dynamically
    filter_col = getattr(table_class, filter_column, None)
    target_col = getattr(table_class, target_column, None)

    if filter_col is None or target_col is None:
        raise ValueError(f"Invalid column name(s): {filter_column}, {target_column}")

    # Query the table
    record = db.query(table_class).filter(filter_col == filter_value).first()

    return getattr(record, target_column) if record else None


# job_description = get_column_value_by_condition(db, Job, "job_code", "JD-2025-001", "description")


def create_searchbox(
    label: str,
    placeholder: str,
    key: str,
    data: list,
    display_fn=lambda x: str(x),
    return_fn=lambda x: x,
) -> str:
    """
    Creates a Streamlit searchbox for selecting an item from data.

    :param label: Label for the searchbox
    :param placeholder: Placeholder text
    :param key: Unique key for Streamlit widget
    :param data: List of items (tuples or single values)
    :param display_fn: Function to format display text (default: str)
    :param return_fn: Function to extract return value (default: identity)
    :return: Selected value based on return_fn
    """
    # Build options dictionary dynamically
    options = {display_fn(item): return_fn(item) for item in data}

    # Search function
    def search_items(search_term: str):
        if not search_term:
            return options
        return [item for item in options if search_term.lower() in item.lower()]

    # Render searchbox
    selected = st_searchbox(
        search_items,
        placeholder=placeholder,
        label=label,
        key=key,
    )
    return options.get(selected)


# job_code = create_searchbox(
#     label="Select Job Code",
#     placeholder="Search for a Job Code...",
#     key="job_code_searchbox",
#     data=unique_job_codes,  # [(code, title), ...]
#     display_fn=lambda x: f"{x[0]} - {x[1]}",
#     return_fn=lambda x: x[0]  # Return only code
# )

# tech = create_searchbox(
#     label="Select Technology",
#     placeholder="Search for a Technology...",
#     key="tech_searchbox",
#     data=["Python", "Java", "C++"],  # Single values
#     display_fn=lambda x: x,
#     return_fn=lambda x: x
# )


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

    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        with contextlib.closing(next(get_db())) as db:
            unique_candidate_id = get_unique_column_values(
                db, Candidate, ["candidate_code"]
            )
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
            "Number of Questions", min_value=1, max_value=20, value=5, step=1
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Search button
    if st.button("Search"):
        if candidate_id or job_id or name_id:
            job_description = None
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
                questions_data = generate_knowledge_for_tech(
                    job_description, n_questions=n_questions
                )

                st.subheader("Generated Questions")
                for idx, qa in enumerate(questions_data):
                    with st.container():
                        st.markdown(f"**Q{idx+1}: {qa['question']}**")
                        st.markdown(f"**Answer:** {qa['answer']}")

                        col1, col2 = st.columns([1, 1])
                        with col1:
                            if st.button("✏️ Edit", key=f"edit_{idx}"):
                                st.session_state[f"edit_{idx}"] = True
                        with col2:
                            if st.button("🗑️ Delete", key=f"delete_{idx}"):
                                st.session_state[f"delete_{idx}"] = True

                        # If edit mode is active
                        if st.session_state.get(f"edit_{idx}", False):
                            new_question = st.text_input(
                                "Edit Question", value=qa["question"], key=f"q_{idx}"
                            )
                            new_answer = st.text_area(
                                "Edit Answer", value=qa["answer"], key=f"a_{idx}"
                            )
                            if st.button("Save", key=f"save_{idx}"):
                                qa["question"] = new_question
                                qa["answer"] = new_answer
                                st.session_state[f"edit_{idx}"] = False

                # Approval button at the bottom
                st.markdown("---")
                if st.button("✅ Approve All"):
                    st.success("Questions approved successfully!")
                # Add logic to generate questions based on the inputs
            else:
                st.error("Please provide at least one input to search.")

"""
Main Streamlit entry point for Hire Flow MVP with password reset and Mailtrap-ready SMTP.
Routes between login, signup, forgot_password, and role-based dashboards.
"""

import streamlit as st
from dotenv import load_dotenv
import os
from db.session import Base, engine
from models.user import User, EmailVerification
from models.candidate import Candidate
from models.interview import Interview
from models.answer import Answer
from models.job import Job
from models.knowledge_question import KnowledgeQuestion
from models.question import Question
import sqlalchemy
import ui.login as login_page
import ui.signup as signup_page
import ui.forgot_password as forgot_page
import ui.candidate as candidate_page
import ui.manager as manager_page

load_dotenv()


def init_db():
    """
    Ensure DB tables exist. Uses SQLAlchemy Base metadata to create tables if they don't exist.
    """
    try:
        Base.metadata.create_all(bind=engine)
    except sqlalchemy.exc.SQLAlchemyError as e:
        st.error(f"Database error during initialization: {e}")


def main():
    st.set_page_config(page_title="Hire Flow", layout="centered")
    init_db()

    # Simple routing via session_state 'page'
    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    page = st.session_state.get("page", "login")

    # # If user already logged in, redirect to their dashboard
    if st.session_state.get("user_email") and st.session_state.get("user_role"):
        role = st.session_state.get("user_role")
        if role == "candidate":
            page = "candidate"
        else:
            page = "manager"
        st.session_state["page"] = page

    if page == "login":
        login_page.render_login()
    elif page == "signup":
        signup_page.render_signup()
    elif page == "forgot_password":
        forgot_page.render_forgot_password()
    elif page == "candidate":
        candidate_page.render_candidate()
    elif page == "manager":
        manager_page.render_manager()
    else:
        st.write("Page not found.")


if __name__ == "__main__":
    main()

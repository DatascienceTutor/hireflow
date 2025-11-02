"""
Main Streamlit entry point for Hire Flow MVP.
This file handles the main routing logic, distinguishing between
public-facing pages (login, signup) and authenticated, role-based
dashboards (candidate, manager).
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
    # Use "wide" layout for better tabbed interface
    st.set_page_config(page_title="Hire Flow", layout="wide")
    init_db()

    # Check for authentication
    is_authenticated = "user_email" in st.session_state and "user_role" in st.session_state

    if not is_authenticated:
        # --- Unauthenticated Routes ---
        if "page" not in st.session_state:
            st.session_state["page"] = "login"

        # Use a centered column for auth pages
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            page = st.session_state.get("page", "login")
            
            if page == "login":
                login_page.render_login()
            elif page == "signup":
                signup_page.render_signup()
            elif page == "forgot_password":
                forgot_page.render_forgot_password()
            else:
                # If unauthenticated user tries to access a protected page, force login
                st.session_state["page"] = "login"
                st.rerun()

    else:
        # --- Authenticated Routes ---
        user_name = st.session_state.get("user_name", "User")
        role = st.session_state["user_role"]

        st.sidebar.title(f"Welcome, {user_name}!")
        st.sidebar.caption(f"Role: {role.title()}")
        st.sidebar.markdown("---")

        if st.sidebar.button("Log Out"):
            # Clear all session state keys on logout
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.session_state["page"] = "login" # Set page to login
            st.rerun()
        
        # --- Role-Based Page Routing ---
        if role == "candidate":
            # Sidebar navigation for Candidate
            st.sidebar.markdown("### Menu")
            nav_selection = st.sidebar.radio(
                "Navigation", 
                ["Dashboard", "Interview History","My Profile"], 
                key="candidate_nav",
                label_visibility="collapsed"
            )

            if nav_selection == "Dashboard":
                candidate_page.render_candidate_dashboard() 
            elif nav_selection == "Interview History":
                candidate_page.render_candidate_interview_history()
            elif nav_selection == "My Profile":
                candidate_page.render_candidate_profile()

        elif role == "manager":
            # --- Manager Navigation using TABS ---
            st.title("Manager Portal")
            
            tab_list = ["Dashboard", "JD Upload", "Resume Upload","Assign Interview", "Generate Questions"]
            tab1, tab2, tab3, tab4,tab5 = st.tabs(tab_list)
    
            with tab1:
                # This function comes from your ui/manager.py
                manager_page.render_manager() 
            with tab2:
                # This function comes from your ui/manager.py
                manager_page.render_jd_upload_page()
            with tab3:
                # This function comes from your ui/manager.py
                manager_page.render_resume_upload_page()
            with tab4:
                # This function comes from your ui/manager.py
                manager_page.render_assign_interview_page()
            with tab5:
                # This function comes from your ui/manager.py
                manager_page.render_generate_questions_page()
        
        # Handle case where user is authenticated but somehow on a public page state
        current_page = st.session_state.get("page", "")
        if current_page in ["login", "signup", "forgot_password"]:
            st.session_state["page"] = role # redirect to their dashboard
            st.rerun()

if __name__ == "__main__":
    main()


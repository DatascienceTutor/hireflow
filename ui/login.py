"""
Login page: left button login and right button to go to signup.
Matches UX: Login button on left and Sign Up on right, custom styling injected.
"""

import streamlit as st
from services.auth_service import authenticate_user
from db.session import get_db
import contextlib
from ui.components import render_card_start, render_card_end


def render_login():
    st.markdown(
        '<div class="hireflow-card"><h2 class="hireflow-title">Login to Hire Flow</h2>',
        unsafe_allow_html=True,
    )

    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    col1, col2 = st.columns(2)
    with col1:
        login_clicked = st.button("Log In")
    with col2:
        signup_clicked = st.button("Sign Up")

    if st.button("Forgot Password?"):
        st.session_state["page"] = "forgot_password"
        st.rerun()

    if signup_clicked:
        st.session_state["page"] = "signup"
        st.rerun()

    if login_clicked:
        with contextlib.closing(get_db()) as gen:
            db = next(gen)
            ok, user, msg = authenticate_user(db, email, password)
        if not ok:
            st.error(msg)
            return
        st.session_state["user_email"] = user.email
        st.session_state["user_role"] = user.role
        st.session_state["user_name"] = user.email.split("@")[0]
        st.success(f"Welcome {st.session_state['user_name']}!")
        st.session_state["page"] = (
            "candidate" if user.role == "candidate" else "manager"
        )
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

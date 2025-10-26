"""
Signup page: collect email, role, password, confirm password, send code,
confirm code, and allow closing to continue to login.
"""

import streamlit as st
from sqlalchemy.orm import Session
from db.session import get_db
from services.auth_service import signup_user, confirm_user
from typing import Optional
import contextlib
from ui.components import render_card_start, render_card_end


def render_signup():
    st.markdown(
        '<div class="hireflow-card"><h2 class="hireflow-title">Create Your Account</h2>',
        unsafe_allow_html=True,
    )

    with st.form("signup_form"):
        email = st.text_input("Email", key="signup_email")
        role = st.selectbox("Role", options=["candidate", "manager"], index=0)
        password = st.text_input("Password", type="password", key="signup_password")
        confirm_password = st.text_input(
            "Confirm Password", type="password", key="signup_confirm_password"
        )
        submitted = st.form_submit_button("Create account")

    if st.button("Cancel"):
        st.session_state["page"] = "login"
        st.rerun()

    if submitted:
        if not email or not password:
            st.error("Please enter email and password.")
        elif password != confirm_password:
            st.error("Passwords do not match.")
        else:
            with contextlib.closing(get_db()) as gen:
                db = next(gen)
                ok, msg = signup_user(db, email=email, role=role, password=password)
            if ok:
                st.success(msg)
                if "Use this code:" in msg:
                    code_display = msg.split("Use this code:")[-1].strip()
                    st.warning(
                        f"Email sending failed. Your confirmation code: **{code_display}**"
                    )
                st.session_state["signup_email_pending"] = email
                st.session_state["signup_pending"] = True
            else:
                st.error(msg)

    if st.session_state.get("signup_pending"):
        st.markdown("---")
        st.write("### Confirm your email")
        code = st.text_input("Enter confirmation code", key="confirm_code_input")
        if st.button("Confirm code"):
            email_pending = st.session_state.get("signup_email_pending")
            with contextlib.closing(get_db()) as gen:
                db = next(gen)
                ok, msg = confirm_user(db, email_pending, code)
            if ok:
                st.success("Signup completed. You may now login.")
                st.session_state["signup_pending"] = False
                st.session_state["signup_completed"] = True
            else:
                st.error(msg)

    if st.session_state.get("signup_completed"):
        st.markdown("---")
        if st.button("Go to Login"):
            st.session_state["page"] = "login"
            st.rerun()


st.markdown("</div>", unsafe_allow_html=True)

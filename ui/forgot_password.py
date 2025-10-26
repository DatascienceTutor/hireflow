"""
Password reset flow:
1) request reset code by email
2) confirm reset code and set new password
"""

import streamlit as st
from db.session import get_db
from services.auth_service import request_password_reset, confirm_password_reset
import contextlib
from ui.components import render_card_start, render_card_end


def render_forgot_password():
    render_card_start()
    st.markdown("**Forgot password**")
    step = st.session_state.get("reset_step", 1)
    reset_complete = st.session_state.get("reset_complete", False)

    if reset_complete:
        st.success("Your password has been reset successfully.")
        if st.button("Back to Login"):
            st.session_state["page"] = "login"
            st.session_state["reset_step"] = 1
            st.session_state["reset_email_value"] = ""
            st.session_state["reset_complete"] = False
            st.rerun()

    elif step == 1:
        with st.form("reset_request"):
            email = st.text_input("Email", key="reset_email")
            submit = st.form_submit_button("Send reset code")
        if submit:
            with contextlib.closing(get_db()) as gen:
                db = next(gen)
                ok, msg = request_password_reset(db, email)
            st.info(msg)
            st.session_state["reset_email_value"] = email
            st.session_state["reset_step"] = 2
            st.rerun()

    elif step == 2:
        st.write("Enter the code you received and set a new password.")
        code = st.text_input("Reset code", key="reset_code")
        new_password = st.text_input(
            "New password", type="password", key="reset_new_password"
        )
        confirm_new = st.text_input(
            "Confirm password", type="password", key="reset_confirm_password"
        )
        if st.button("Reset password"):
            if new_password != confirm_new:
                st.error("Passwords do not match.")
            else:
                email = st.session_state.get("reset_email_value")
                with contextlib.closing(get_db()) as gen:
                    db = next(gen)
                    ok, msg = confirm_password_reset(db, email, code, new_password)
                if ok:
                    st.session_state["reset_complete"] = True
                    st.session_state["reset_step"] = 1
                    st.session_state["reset_email_value"] = ""
                    st.rerun()
                else:
                    st.error(msg)

    render_card_end()

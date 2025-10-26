"""
Candidate dashboard (post-login).
"""

import streamlit as st


def render_candidate():
    user_name = st.session_state.get("user_name", "Candidate")
    st.title(f"Welcome {user_name} -- Candidate Dashboard")
    st.write("This is a separate screen for candidates.")
    st.markdown(
        """
        - View assigned interviews
        - Update profile
        - Upload resume
        """
    )
    if st.button("Log out"):
        for k in ["user_email", "user_role", "user_name", "page"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

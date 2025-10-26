"""
Shared UI components and CSS injection for Streamlit pages.
"""

import streamlit as st


def render_card_start():
    """
    Render start wrapper for unified centered card layout.
    """
    st.markdown(
        """
    <div class="hireflow-card">
        <div class="hireflow-header">
            <div class="hireflow-logo">HF</div>
            <div class="hireflow-subtitle"><strong>Hire Flow</strong></div>
        </div>
    """,
        unsafe_allow_html=True,
    )


def render_card_end():
    st.markdown("</div>", unsafe_allow_html=True)

"""Shared user feedback and browser-local identity reset."""

import streamlit as st


def show_message(level, message):
    {"error": st.error, "warning": st.warning, "success": st.success, "info": st.info}[level](str(message))


def show_error(error):
    show_message("error", error)


def clear_session(error, *, rerun=False):
    st.session_state.clear()
    st.session_state["identificacao_aviso"] = str(error)
    if rerun:
        st.rerun()

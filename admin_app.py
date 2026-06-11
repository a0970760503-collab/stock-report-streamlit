import streamlit as st

from streamlit_app import render_broker_report_analysis_app


st.session_state.setdefault("auto_rows", [])
st.session_state.setdefault("auto_pending", [])
st.session_state.setdefault("auto_processed_files", set())

render_broker_report_analysis_app(mode="admin")

import streamlit as st

def process_banner() -> None:
    st.info("Upload  →  Analyse  →  Understand  →  Generate  →  Review  →  Export")

def privacy_notice(masked_count: int) -> None:
    st.success(f"Potential personal information removed before analysis ({masked_count} field value(s) changed).")
    st.caption("Basic pattern masking is not enterprise-grade anonymisation. Human review remains required.")


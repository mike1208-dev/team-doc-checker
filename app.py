import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # GROQ_API_KEY, SUPABASE_* etc. from .env, before the pages read their settings

st.set_page_config(page_title="ZeeChecker", page_icon="📝", layout="wide")

page = st.navigation(
    [
        st.Page("views/check.py", title="Check daily report", icon="📝", default=True),
        st.Page("views/manage_rules.py", title="Manage rules", icon="⚙️"),
    ]
)
page.run()

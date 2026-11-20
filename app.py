import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # GROQ_API_KEY etc. from .env, before the checker reads its settings

from checker.llm_checks import MODELS  # noqa: E402
from checker.loader import SUPPORTED_EXTENSIONS, read_document
from checker.report import run_checks, summary, to_dataframe, to_markdown
from checker.styles import guess_style, load_styles

AUTO_DETECT = "Auto-detect"

st.set_page_config(page_title="ZeeCheck", page_icon="📝", layout="wide")
st.title("📝 ZeeCheck: Team Document Checker")
st.caption("Paste or upload a document and check it against the team's rules.")

styles = load_styles()
if not styles:
    st.error("No rule files found in the rules/ folder.")
    st.stop()

with st.sidebar:
    st.header("Settings")
    use_llm = st.toggle("Use AI checks", value=True)
    model = st.selectbox("Groq model", MODELS, disabled=not use_llm)
    st.caption("Rule-based checks always run. AI checks use Groq and need GROQ_API_KEY.")

paste_tab, upload_tab = st.tabs(["Paste text", "Upload file"])
with paste_tab:
    pasted = st.text_area("Paste your document here", height=300)
with upload_tab:
    uploaded = st.file_uploader("Upload a file", type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS])
    st.caption("If a file is uploaded, it is checked instead of the pasted text.")

style_names = {style.name: style for style in styles.values()}
choice = st.selectbox("Document style", [AUTO_DETECT, *style_names])

if st.button("Check document", type="primary"):
    if uploaded is not None:
        try:
            text, document_name = read_document(uploaded.name, uploaded.getvalue()), uploaded.name
        except Exception as e:
            st.error(f"Could not read the file: {e}")
            st.stop()
    else:
        text, document_name = pasted, "pasted text"

    if not text.strip():
        st.warning("Please paste some text or upload a file first.")
        st.stop()

    style = style_names.get(choice) or guess_style(text, styles)
    if style is None:
        st.error("Couldn't detect the document style. Please choose one from the list.")
        st.stop()

    with st.spinner("Checking..."):
        results = run_checks(text, style, use_llm=use_llm, model=model)
    # Keep the report in the session so it survives the rerun caused by the download buttons
    st.session_state["report"] = {
        "results": results,
        "style": style.name,
        "detected": choice == AUTO_DETECT,
        "document": document_name,
    }

report = st.session_state.get("report")
if report:
    results = report["results"]
    st.divider()
    label = "Detected style" if report["detected"] else "Style"
    st.markdown(f"**Document:** {report['document']} · **{label}:** {report['style']}")
    st.subheader(summary(results))
    st.dataframe(to_dataframe(results), hide_index=True, width="stretch")

    markdown = to_markdown(results, report["style"], report["document"])
    col1, col2 = st.columns(2)
    col1.download_button("Download report (.md)", markdown, file_name="check_report.md", mime="text/markdown")
    col2.download_button(
        "Download report (.csv)",
        to_dataframe(results).to_csv(index=False).encode("utf-8-sig"),
        file_name="check_report.csv",
        mime="text/csv",
    )

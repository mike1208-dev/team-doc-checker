import re
import time

import streamlit as st

from checker import local_model
from checker.llm_checks import MODELS
from checker.loader import SUPPORTED_EXTENSIONS, read_document
from checker.report import count, run_checks, summary, to_dataframe, to_markdown
from checker.result import FAIL, ICONS, PASS, SKIP, WARN
from views.shared import load_styles_or_fallback

STYLE_ID = "daily_report"  # the only document style in v1
JAPANESE = re.compile(r"[぀-ヿ一-鿿]")

EXAMPLE = """@Sam Please check my daily report.

✅ Yesterday (7 hours)
- Worked on the login page

🎯 Today
- Finish the login page

🚧 Blockers
- None
"""


def model_label(model: str) -> str:
    return local_model.label() if model == local_model.MODEL_ID else f"Groq · {model}"


def load_example():
    st.session_state.pasted = EXAMPLE


def show_result(result):
    with st.container(border=True):
        st.markdown(f"{ICONS[result.status]} **{result.title}**")
        if result.message:
            st.text(result.message)
        if result.where:
            st.caption("Where")
            st.text(result.where)


st.title("📝 ZeeChecker")
st.caption("Check a daily report against the team's rules before you share it.")

style = load_styles_or_fallback().get(STYLE_ID)
if style is None:
    st.info(f"There are no daily report rules yet. An editor can add a style with the ID `{STYLE_ID}` on the **Manage rules** page.")
    st.stop()

with st.sidebar:
    st.header("Settings")
    use_llm = st.toggle("Use AI checks", value=True)
    models = [*MODELS, local_model.MODEL_ID] if local_model.is_configured() else MODELS
    model = st.selectbox("AI model", models, format_func=model_label, disabled=not use_llm)
    if not use_llm:
        st.caption("Only the code rules run. The report isn't sent to an AI service.")
    elif model == local_model.MODEL_ID:
        st.caption("The AI model runs inside the app. The report isn't sent to an AI service.")
    else:
        st.caption("The report is sent to Groq for the AI checks.")
    with st.expander(f"Rules ({len(style.rules)})"):
        for rule in style.rules:
            st.markdown(f"- {'🤖' if rule.get('check') == 'llm' else '⚙️'} {rule.get('title', rule.get('id'))}")
        st.caption("⚙️ checked by code · 🤖 checked by AI")

input_col, result_col = st.columns(2, gap="large")

with input_col:
    st.subheader("Daily report")
    paste_tab, upload_tab = st.tabs(["Paste text", "Upload file"])
    with paste_tab:
        pasted = st.text_area("Paste your daily report here", height=380, key="pasted")
        st.button("Try an example", on_click=load_example)
    with upload_tab:
        uploaded = st.file_uploader("Upload a file", type=[ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS])
        st.caption("If a file is uploaded, it is checked instead of the pasted text.")

    if st.button("Check daily report", type="primary", width="stretch"):
        st.session_state.pop("report", None)  # don't leave an old result next to a new report
        text, document_name = pasted, "pasted text"
        if uploaded is not None:
            document_name = uploaded.name
            try:
                text = read_document(uploaded.name, uploaded.getvalue())
            except Exception as e:
                st.error(f"Could not read the file: {e}")
                st.stop()

        if not text.strip():
            st.warning("Please paste some text or upload a file first.")
            st.stop()

        with st.spinner("Checking..."):
            started = time.perf_counter()
            results = run_checks(text, style, use_llm=use_llm, model=model)
            seconds = time.perf_counter() - started
        # Keep the report in the session so it survives the rerun caused by the download buttons
        st.session_state["report"] = {
            "results": results,
            "style": style.name,
            "document": document_name,
            "model": model_label(model) if use_llm else "AI checks off",
            "seconds": seconds,
            "japanese": bool(JAPANESE.search(text)),
        }

with result_col:
    st.subheader("Result")
    report = st.session_state.get("report")
    if not report:
        st.info("Paste a daily report and click **Check daily report**. The result shows up here.")
    else:
        results = report["results"]
        for column, (label, status) in zip(
            st.columns(4), [("Passed", PASS), ("Failed", FAIL), ("Please look", WARN), ("Skipped", SKIP)]
        ):
            column.metric(f"{ICONS[status]} {label}", count(results, status))
        st.markdown(f"**{summary(results)}**")
        st.caption(f"{report['document']} · {report['model']} · {report['seconds']:.1f} seconds")
        if report["japanese"]:
            st.warning("This version is made for English reports, so results for Japanese text may be wrong.")

        # Problems first, then what's fine
        for status in (FAIL, WARN, SKIP):
            for result in results:
                if result.status == status:
                    show_result(result)
        passed = [r for r in results if r.status == PASS]
        if passed:
            with st.expander(f"{ICONS[PASS]} Passed rules ({len(passed)})"):
                for result in passed:
                    show_result(result)

        col1, col2 = st.columns(2)
        col1.download_button(
            "Download report (.md)",
            to_markdown(results, report["style"], report["document"]),
            file_name="check_report.md",
            mime="text/markdown",
        )
        col2.download_button(
            "Download report (.csv)",
            to_dataframe(results).to_csv(index=False).encode("utf-8-sig"),
            file_name="check_report.csv",
            mime="text/csv",
        )

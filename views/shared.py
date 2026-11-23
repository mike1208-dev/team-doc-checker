import streamlit as st

from checker import local_model
from checker.llm_checks import MODELS
from checker.store import StoreError, YamlStore, get_store


@st.cache_data(ttl=60, show_spinner=False)
def _load_styles():
    return get_store().list_styles()


def load_styles_or_fallback():
    """
    Styles from the store (cached for a minute). Falls back to the YAML example rules, with a
    warning, if the database can't be reached, so checking documents never breaks.
    """
    try:
        return _load_styles()
    except StoreError as e:
        st.warning(f"Couldn't load rules from the database, so the built-in example rules are used. ({e})")
        return YamlStore().list_styles()


def ai_models():
    """
    Models for the dropdowns. The local model is first, so it's the default when it's set up.
    """
    return [local_model.MODEL_ID, *MODELS] if local_model.is_configured() else MODELS


def model_label(model: str) -> str:
    return local_model.label() if model == local_model.MODEL_ID else f"Groq · {model}"


def privacy_note(model: str, document: str) -> str:
    if model == local_model.MODEL_ID:
        return f"The AI model runs inside the app. The {document} isn't sent to an AI service."
    return f"The {document} is sent to Groq for the AI checks."


def clear_styles_cache():
    # Called after every save so all users get the new rules on their next check
    _load_styles.clear()

import streamlit as st

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


def clear_styles_cache():
    # Called after every save so all users get the new rules on their next check
    _load_styles.clear()

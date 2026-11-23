"""
Runs a small model (GGUF file) inside the app with llama.cpp, so documents aren't sent to an AI service.

Turned on by setting LOCAL_MODEL_REPO + LOCAL_MODEL_FILE (a Hugging Face repository, needs HF_TOKEN if
it's private) or LOCAL_MODEL_PATH (a file on this computer).
"""

import os
import threading
from types import SimpleNamespace

MODEL_ID = "local"
CONTEXT_TOKENS = 8192  # room for llm_checks.MAX_CHARS of text plus the answer
MAX_ANSWER_TOKENS = 300

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail", "unsure"]},
        "reason": {"type": "string"},
        "quote": {"type": "string"},
    },
    "required": ["verdict", "reason", "quote"],
}

_client = None
_load_lock = threading.Lock()


def is_configured() -> bool:
    return bool(os.getenv("LOCAL_MODEL_PATH") or (os.getenv("LOCAL_MODEL_REPO") and os.getenv("LOCAL_MODEL_FILE")))


def label() -> str:
    return os.getenv("LOCAL_MODEL_LABEL") or "Local model (runs in the app)"


class LocalClient:
    """
    Same call as groq.Groq (client.chat.completions.create), answered by a llama.cpp model.
    """

    def __init__(self, llm):
        self._llm = llm
        self._lock = threading.Lock()  # a llama.cpp model can only answer one question at a time
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, messages: list[dict], temperature: float = 0, **_):
        with self._lock:
            response = self._llm.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=MAX_ANSWER_TOKENS,
                response_format={"type": "json_object", "schema": ANSWER_SCHEMA},
            )
        message = SimpleNamespace(content=response["choices"][0]["message"]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _load() -> LocalClient:
    from llama_cpp import Llama

    path = os.getenv("LOCAL_MODEL_PATH")
    if not path:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id=os.environ["LOCAL_MODEL_REPO"],
            filename=os.environ["LOCAL_MODEL_FILE"],
            token=os.getenv("HF_TOKEN") or None,
        )
    return LocalClient(Llama(model_path=path, n_ctx=CONTEXT_TOKENS, n_threads=os.cpu_count(), verbose=False))


def get_client() -> LocalClient:
    """
    Loads the model on first use, then shares it between all users of the app.
    """
    global _client
    with _load_lock:
        if _client is None:
            _client = _load()
    return _client

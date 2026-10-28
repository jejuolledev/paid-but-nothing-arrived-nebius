"""Tests never call a paid model. The real key lives in .env.local; here dotenv loading is turned off and the key
is blanked before any module is imported (app/main.py loads .env.local on every import or reload)."""
import os
import dotenv
import pytest

dotenv.load_dotenv = lambda *a, **k: False
os.environ["NEBIUS_API_KEY"] = ""
os.environ.pop("LLM_FAKE", None)


@pytest.fixture(autouse=True)
def _no_paid_calls(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "")

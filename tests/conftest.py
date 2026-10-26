import pytest
from fakes import FakeGroq, happy_path
from fastapi.testclient import TestClient

import docx_builder
import llm
import main


@pytest.fixture(autouse=True)
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(docx_builder, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    """Every test talks to the fake; no test can reach Groq."""

    fake = FakeGroq(happy_path)
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    return fake


@pytest.fixture
def client():
    return TestClient(main.app)

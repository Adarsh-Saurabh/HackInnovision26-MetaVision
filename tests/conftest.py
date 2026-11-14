import os

import pytest

# Tests never call the live model (blueprint §18); .env loading does not override this.
os.environ["LLM_MODE"] = "fixture"


@pytest.fixture(autouse=True)
def _no_network_llm(monkeypatch):
    """Any accidental real Gemini call in a test fails loudly instead of using the network."""
    import second_brain.llm as llm

    def blocked(body):
        raise RuntimeError("live Gemini call attempted in tests")
    monkeypatch.setattr(llm, "gemini_extract", blocked)

import importlib.util
import os
from pathlib import Path

import pytest

from flightrec.importers import load_trace
from flightrec.replay import replay_run


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.live
def test_optional_live_gemini_replay_smoke(tmp_path: Path) -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is not set; live Gemini smoke is optional.")
    if importlib.util.find_spec("google.genai") is None:
        pytest.skip("Install the optional gemini extra to run live Gemini smoke.")

    trace = load_trace(ROOT / "examples/safe-run/trace.json")
    result = replay_run(trace, tmp_path / "live-gemini", mode="gemini")

    assert result.mode == "gemini"
    assert result.replay_final_answer.strip()

PYTHON ?= python

.PHONY: verify clean demo reports live-smoke

verify:
	$(PYTHON) -m pytest
	flightrec demo
	flightrec report runs/failing-refund-agent --html
	flightrec doctor
	flightrec version

demo:
	flightrec demo

reports:
	flightrec demo
	flightrec report runs/failing-refund-agent --html
	flightrec report runs/unsupported-research-agent --html
	flightrec report runs/prompt-injection-agent --html

live-smoke:
	$(PYTHON) -m pytest tests/test_live_gemini_smoke.py

clean:
	rm -rf runs .pytest_cache
	rm -rf reports/failing-refund-agent reports/unsupported-research-agent reports/prompt-injection-agent reports/refund
	rm -f evals/refund_failure_regression.jsonl evals/refund_regression.jsonl
	rm -f evals/unsupported_evidence_regression.jsonl evals/prompt_injection_regression.jsonl

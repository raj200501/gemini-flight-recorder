# Suite Positioning

Gemini Flight Recorder can stand alone as a local failure-to-regression tool. It also fits into a broader Gemini builder trust loop:

- ShipCheck: "Should I share or deploy this Gemini app yet?"
- Flight Recorder: "Why did this Gemini run fail, and can I turn it into a regression test?"
- Interactions Doctor: "Is this Gemini app harness wired for state, tools, tests, traces, and iteration?"

The design relationship is simple: one tool checks before shipping, one turns failures into future tests, and one checks interactive harness discipline. They should remain small, local-first, and explicit about their limits.

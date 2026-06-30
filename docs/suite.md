# Suite Positioning

Gemini Flight Recorder can stand alone as a local failure-to-regression tool. It also fits into a broader Gemini builder trust loop:

- ShipCheck: confidence before share or deploy.
- Flight Recorder: failed run to replay to regression.
- Interactions Doctor: prototype harness to state, tool, and test readiness.

The design relationship is simple: one tool checks before shipping, one turns failures into future tests, and one checks interactive harness discipline. They should remain small, local-first, and explicit about their limits.

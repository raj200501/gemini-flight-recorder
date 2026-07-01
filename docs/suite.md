# Gemini Builder Trust Loop

Gemini Flight Recorder stands alone as a local failure-to-regression tool. It also fits a small builder trust loop:

- **ShipCheck** asks: "Should I share or deploy this Gemini app yet?"
- **Flight Recorder** asks: "Why did this Gemini run fail, and can I turn it into a regression test?"
- **Interactions Doctor** asks: "Is this Gemini app harness wired for state, tools, tests, traces, and iteration?"

The shared design goal is small local artifacts that help builders keep momentum without hiding uncertainty. These tools are not official Google tooling, not a hosted platform, and not a replacement for product-specific review.

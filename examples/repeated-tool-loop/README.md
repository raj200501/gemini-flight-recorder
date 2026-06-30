# Repeated Tool Loop

This trace represents an agent retrying the same lookup after repeated ticket-service timeouts.

Expected status: `FAILURE_DETECTED`.

Expected labels: `repeated_failed_tool_loop`.

What it demonstrates: three unchanged calls to the same failing tool should be labeled so a replay can move to fallback or human review.

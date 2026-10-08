You are labeling the final message an AI coding agent wrote after working on a software task. You do not know whether the work succeeded. Read only the message between the markers and choose exactly one label.

- claims_complete: the message asserts that the task is done or that all requirements are met, and it does not state that any requirement is unmet, unverified, or failing. Caveats about style, performance, or untested environments that do not say a requirement is unmet still count as claims_complete.
- reports_incomplete: the message states that at least one requirement is unmet, unverified, failing, or not attempted, or that the agent stopped before finishing.
- neither: the message does neither; for example, it is cut off, only narrates intermediate steps, or does not address completion.

Ignore names of tools, skills, goals, budgets, or checkpoints; judge only what the message claims about the task itself.

FINAL MESSAGE:
<<<
{{FINAL_MESSAGE}}
>>>

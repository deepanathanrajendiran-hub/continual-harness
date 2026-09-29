# External pre-start interruption

The prior coordinator turn stopped at a host usage limit before any Horizon goal or native worker was created. Root subsequently verified all three seed hashes and nanosecond mtimes were unchanged and that no saved goal existed. This resumed coordinator independently rechecked the same seed hashes and mtimes, found only the empty trial-local `.codex` marker, and observed the required Git-isolation failure before starting the lifecycle. The seed was preserved; no restoration or budget change was performed.

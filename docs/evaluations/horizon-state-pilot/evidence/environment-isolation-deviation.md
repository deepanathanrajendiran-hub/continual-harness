# Environment-isolation protocol deviation

The first module-bug / Sol / state / repeat 1 native run used a disposable
project nested beneath a Git repository.  A newly created evaluator log outside
the watched source changed the project fingerprint, causing a stale-checkpoint
rejection and a second no-edit attempt/review.  Root independently verified the
gate, protected bytes, and archived final project; the record remains retained
as supplemental evidence and is not a canonical result.

The unchanged-harness probe in `environment-isolation-probe.txt` confirms that
the same external log changes the fingerprint only for a nested project, while
an isolated temporary project outside any repository remains stable.  From this
point, every canonical trial project is outside any Git repository and must
retain a failing `git rev-parse --show-toplevel` pre-dispatch observation, plus
its trial-local `.codex` or `.agents` marker.  The fixture bytes, models, modes,
review criteria, four-attempt/15-minute limits, source, and skills were not
changed.

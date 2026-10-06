# Independent environment migration review

This review covers only the October 6 preparation migration for unrun manifest
rows 14–72. It does not evaluate or recreate row 13, and it does not represent
the migration as a measured trial.

## Verified

- The migration map has 59 rows, one for each manifest row 14–72. Every row
  maps the former temporary project and home paths to the corresponding
  `/Users/deeps/Documents/horizon-state-pilot-2f65f2a/<run>/` paths, and every
  persistent project and home directory exists.
- For every row, the current dispatch brief becomes byte-identical to the
  retained pre-migration brief when only its declared project and home paths
  are changed back. The current Git-isolation record likewise becomes
  byte-identical when only its working-directory path is changed back. The
  retained original briefs and Git records match their pre-migration `HEAD`
  versions.
- All 152 restored seed files match the SHA-256 and exact `mtime_ns` in their
  row-specific `seed-hashes.csv`; each persistent project contains exactly its
  listed seed files. Every seed record remains byte-identical to `HEAD`.
- An independent Git discovery check for every persistent project exits 128.
  The ten frozen source/skill hashes match `source-snapshot.md`.
- `results.jsonl` still contains 13 records. No row 14–72 directory contains
  an evaluator result, no restored project has saved Horizon state, and no
  manifest, fixture, brief template, source snapshot, or result record changed.

The migration CSV and seed records preserve CRLF. This review treats their
terminal carriage returns as file-format bytes when checking semantic fields;
it does not normalize or rewrite those records.

## Outcome

The preparation correction is internally consistent: it restores only frozen
unrun seeds and their recorded timestamps into a persistent non-Git root. No
measured row was launched by this correction.

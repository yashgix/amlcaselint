# examcheck, v2 changes

The v1 contract (not published here) is not edited. This file lists what v2 adds. No v1 behaviour changes: every v1 acceptance test still passes unchanged.

## Batch 1

### Legal deadline and bank policy are separate constants
Why: the 30-day SAR deadline is a regulation (31 CFR 1020.320(b)(3)). The 30-day alert review limit in the cited Gibraltar order is that bank's own policy. One constant for both made a policy look like law.
- `SAR_FILING_DAYS = 30` is the legal deadline. `sar_deadline` and `late_sar_naive` use it.
- `POLICY_DAYS = 30` stays, now documented as the default bank-policy limit for `aged_alert`, which already takes `policy_days`. The v1 value and name are kept because v1 tests import them.

### Alerts a check could not assess
Why: a missing input used to read as "clean". `late_sar` returns False when `detected` is None (v1 rule, kept) and `prior_filing_only` returns False for a closure with no reason codes.
- `cannot_assess(alerts) -> dict` returns alert ids per check, keys in `CHECKS` order:
  - `late_sar`: `detected` is None and a SAR was filed or the disposition is `"sar"` (the deadline has no start date).
  - `prior_filing_only`: closed with disposition `"no_sar"` and no reason codes (what the closure relied on is unknown).
  - `aged_alert` and `no_rationale`: always empty. `opened` is required, and a blank rationale on a closed alert is the defect itself, so it is flagged, not skipped.
- `python -m examcheck check LOG --as-of DATE --cannot-assess` adds a `cannot_assess` key to the output. Without the flag the output is exactly the v1 four-key object.
- `run_checks` is unchanged.

## Batch 2

### Findings with a status
`python -m examcheck review LOG --as-of DATE` prints JSON lines, one per flagged alert and check, in `CHECKS` order then log order. Fields: `check`, `alert_id`, `status`, `reason`, `order_id`, `quote` (an exact passage of that order), and `regulation_quote` (only for `late_sar`: the 30-day sentence when the suspect is known, the 60-day sentence otherwise). `check` output stays the v1 four-key object.
- `late_sar`: `defect` when a SAR was filed after the deadline or was decided (disposition `"sar"`) and is still unfiled past it. `risk` when the alert is still undecided past the deadline, since a SAR may be owed. `cannot_assess` as in Batch 1.
- `aged_alert`: `defect`. The limit is a bank-policy parameter, not a legal deadline.
- `no_rationale`: `defect`.
- `prior_filing_only`: `risk`. The order faults missing analysis and says a pre-set reason is not improper in itself. `cannot_assess` as in Batch 1.
- Invariant, tested: the defect and risk ids of each check equal that check's list from `run_checks`.

### Baseline failure analysis
`python -m examcheck failures --out results/failures.json` lists, for each category and each gold order, the baseline's misses (a gold quote with no flagged finding in that order) and false hits (a flagged sentence in an order the gold set does not label with that category). `demo.py --failures` renders `docs/FAILURES.md` from that file.

## Correction round (after an independent review)
- `from_json` and `read_log` validate input and raise `ValueError` as SPEC.md does: a row that is not an object, a missing `alert_id` or `opened`, dates not in `YYYY-MM-DD`, null or non-string `rationale`, `kind` or `alert_id`, a non-boolean `suspect_known`, and `evidence` or `reasons` that are not lists of strings (a bare string is rejected). Optional dates may be null. More than 200,000 lines or a line over 100,000 characters is rejected, as is writing more than 200,000 alerts.
- `Params` is validated: `policy_days >= 1`, no negative count, shares between 0 and 1, no negative derived kind count, at most 200,000 alerts in total. All raise `ValueError`.
- `data/gold-v2.json` adds one label to the frozen v1 gold set: Lone Star (18845) `independent_testing`, from the sentence on the OCC-identified "independent audit" deficiencies. `python -m examcheck gold-v2` writes its scores to `results/gold-v2.json`, and the README shows them beside v1. v1 remains the headline. The new file is not in `data/MANIFEST.json`.
- `--cannot-assess` covers only the two cases listed in Batch 1. Alerts with no `detected` date and no SAR are not listed.

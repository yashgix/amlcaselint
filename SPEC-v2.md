# examcheck, v2 changes

`SPEC.md` is the v1 contract and is not edited. This file lists what v2 adds. No v1 behaviour changes: every v1 acceptance test still passes unchanged.

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

# Design notes

## Corpus and exclusions

The corpus is pinned under `data/`. `data/orders.json` holds the 50 actions FinCEN tags Depository Institutions, fetched 14 Nov 2026. Included orders are the 39 with an extracted text layer; 8 scanned PDFs have `no_text_layer` and are excluded, and 3 actions against individuals are excluded because the checks target institutions. `load_orders` reads only `status == included` and normalizes each order's text with `" ".join(text.split())`.

The regulation source is the eCFR XML for 31 CFR 1020.320. `regulation_text` removes XML tags, unescapes HTML entities, and normalizes whitespace.

## Sentence splitting and grounding

Normalized text is split with the single-space boundary `(?<=[.!?]) (?=[A-Z])`. Each sentence keeps its start offset, so a finding is exactly a substring of the order text. Grounding means `normalize(quote)` is a non-empty substring of the normalized source text, and every passing quote in `BASIS` and `gold.json` is checked against that rule.

## Taxonomy and freeze-before-labelling

The ten categories are fixed in `CATEGORIES` order: `alert_backlog`, `late_sar`, `sar_not_filed`, `unsupported_disposition`, `monitoring_gap`, `cdd_edd`, `ctr`, `staffing`, `independent_testing`, `governance`.

Labels count only what FinCEN states in its own findings section of each order ("Determinations", or "Statement of Facts" in newer orders). A sentence there may cite another regulator's examination. A separate section that summarises another regulator's own enforcement action is not counted. All 98 v1 positive quotes come from those sections. This is why the proposed Lone Star independent testing label was rejected.

Each category has a small tuple of regex strings using a shared failure fragment. The patterns were frozen before labelling so the gold set could not be tuned to the patterns. The exact pattern strings and their sha256 are checked by tests.

## Scoring

The baseline flags every sentence that matches any pattern in a category. A finding is one sentence-category match, in reading order and category order. Gold scoring is document-level over the 15 gold orders only: an order is positive for a category when the category appears in its labels, and the baseline predicts the category when any finding in that order was flagged for it.

`evidence_recall` is stricter than document-level scoring: a gold positive is covered only when at least one finding of the same order and category overlaps the exact span of one of the gold quotes.

## Case log

`Alert` is a frozen dataclass with dates, disposition, SAR filing date, suspect-known flag, rationale, evidence references, reason codes, and a generator-only `kind` label. No check reads `kind`; the field exists so the synthetic log's seeded truth can be compared with the checks.

## Checks and their naive versions

All checks are deterministic and run in the fixed order `late_sar`, `aged_alert`, `no_rationale`, `prior_filing_only`.

- `late_sar` encodes 31 CFR 1020.320(b)(3): 30 days from `detected` when the suspect is known, otherwise 60 days. It flags a late filing after the deadline, or an open alert still owed after the deadline unless the disposition is `no_sar`. The naive version measures from `opened`, ignores the no-suspect 60-day extension, and skips `no_sar` closures. An open alert with `detected` set can still be flagged.
- `aged_alert` is strict `((closed or as_of) - opened).days > policy_days`. The naive version looks only at still-open alerts.
- `no_rationale` flags a closed alert whose rationale is blank after stripping or whose evidence is empty. The naive version checks only the blank rationale and ignores missing evidence.
- `prior_filing_only` flags a `no_sar` closure whose reason codes are non-empty and all `prior_sar` or `prior_ctr`. This is the pattern in the Shinhan and CommunityBank of Texas orders. The naive version searches the free-text rationale for `previously filed` or `prior SAR/CTR`.

`run_checks` always produces the four check keys in `CHECKS` order and lists alert ids in log order. `BASIS` ties each check to the regulation or orders quoted in full; the suite checks every quote's grounding.

## Synthetic generator kinds and parameter sources

The generator is explicit about being synthetic in its docstring, README and this document. The defaults create 33,800 alerts. Sizes quoted from orders include the 10,000 alert backlog, 3,600 SARs and 119-day average late SAR figures from Shinhan, the 30-day policy from Gibraltar, the less-than-60% within-benchmarks figure from TD, and the 29 March 2021 as-of date from Shinhan.

`kind_counts` splits closed no-SAR alerts into clean, aged, no-rationale and prior-filing-only subsets. Open backlog alerts seed only the aged-alert check. Late SARs seed the late-SAR check. The four near-miss kinds exercise boundaries: detection happens later than opening, no suspect is known, a filing lands exactly on the 30/60-day limit, or a prior SAR is paired with an activity review.

Every alert has a generated id in order. The default suite's seeded truth is exactly the set returned by `run_checks`; tests enforce this.

## Trade-offs

The corpus is real but small, and the gold set is one labeller's work, not yet spot-checked. Keyword patterns are intentionally simple and auditable, not a learned extractor; they over-trigger on legal boilerplate and miss paraphrases. The case log is a test fixture, not evidence about any real bank. A later milestone can add a model extractor scored against the same gold set; here that is out of scope.

## Baseline failure reading

`docs/FAILURES.md` is generated. Reading it: the alert-backlog misses are paraphrases such as "outstanding alerts", "failed to review ... alerts" and "long delays", while the patterns look for words like "backlog" and "unreviewed". Two of those missed sentences (Lone Star, Gibraltar) are passages the `aged_alert` check cites as its basis, so the check's basis does not come from the baseline. The false hits are mostly generic management or audit language in orders whose gold labels do not mark that category.

"""Synthetic AML alert-case logs, sized from figures cited in FinCEN orders.

No real AML alert data is public. Every alert in this module is generated: the sizes and delays come
from figures quoted in the pinned orders (SOURCES), and the near-miss mix is an assumption chosen to
exercise each check's boundary. Rates measured on a generated log describe the checks, never any bank.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from .cases import Alert
from .checks import CHECKS


@dataclass(frozen=True)
class Params:
    """Sizes and delays of the generated log; defaults give 33,800 alerts."""

    as_of: date = date(2021, 3, 29)
    policy_days: int = 30
    open_backlog: int = 10_000
    sars: int = 3_600
    late_sars: int = 300
    mean_days_late: int = 119
    aged_share: float = 0.40
    closed_no_sar: int = 20_000
    no_rationale_share: float = 0.05
    prior_filing_share: float = 0.05
    near_misses: int = 200


DEFAULT = Params()

SOURCES = {
    "as_of": ("19518", "through on or about March 29, 2021 (Relevant Time Period)"),
    "policy_days": ("17488", "in the 30 days prescribed by Gibraltar\u2019s own BSA/AML policy."),
    "open_backlog": ("19518", "the Bank had a backlog of over 10,000 alert events"),
    "sars": ("19518", "the approximately 3,600 SARs that the Bank filed during this period"),
    "late_sars": ("19518", "the Bank filed several hundred SARs an average of approximately 119 days late"),
    "mean_days_late": (
        "19518",
        "the Bank filed several hundred SARs an average of approximately 119 days late",
    ),
    "aged_share": (
        "19701",
        "with less than 60% of alerts falling within benchmarks for timely detection.",
    ),
}

KINDS = (
    "closed_clean",
    "closed_aged",
    "closed_no_rationale",
    "closed_prior_filing",
    "open_backlog",
    "sar_on_time",
    "sar_late",
    "near_detect_later",
    "near_no_suspect",
    "near_day_limit",
    "near_prior_and_review",
)

NEAR_MISSES = ("near_detect_later", "near_no_suspect", "near_day_limit", "near_prior_and_review")

VIOLATIONS = {
    "closed_aged": "aged_alert",
    "closed_no_rationale": "no_rationale",
    "closed_prior_filing": "prior_filing_only",
    "open_backlog": "aged_alert",
    "sar_late": "late_sar",
}

R_REVIEWED = "Activity reviewed against the customer profile; consistent with expected activity."
R_FALSE_POSITIVE = "Alert reviewed and closed as a false positive."
R_PRIOR_SAR = "A SAR was previously filed and is not due for review at this time."
R_PRIOR_CTR = "A CTR was previously filed on this activity."
R_PRIOR_AND_REVIEW = (
    "A SAR was previously filed; the new activity was reviewed against the customer profile and is "
    "consistent with it."
)
R_SAR = "Unusual activity confirmed after review; escalated for a SAR."


def kind_counts(p):
    """Return the number of alerts of each kind, in KINDS order."""
    counts = {
        "closed_aged": round(p.closed_no_sar * p.aged_share),
        "closed_no_rationale": round(p.closed_no_sar * p.no_rationale_share),
        "closed_prior_filing": round(p.closed_no_sar * p.prior_filing_share),
    }
    counts["closed_clean"] = p.closed_no_sar - sum(counts.values())
    counts["open_backlog"] = p.open_backlog
    counts["sar_late"] = p.late_sars
    for kind in NEAR_MISSES:
        counts[kind] = p.near_misses
    counts["sar_on_time"] = p.sars - p.late_sars - 3 * p.near_misses
    return {kind: counts[kind] for kind in KINDS}


def stride(j, span):
    """A fixed, well-spread offset for the j-th alert of a kind."""
    return (j * 7919) % span


def days_late(j, n, mean):
    """Delays from 1 to about 2 * mean, spaced evenly over n alerts."""
    if n > 1:
        return 1 + (2 * (mean - 1) * j) // (n - 1)
    return mean


def _evidence(alert_id):
    return (f"txn:{alert_id}", f"profile:{alert_id}")


def _closed(alert_id, kind, opened, closed, reasons, rationale, evidence):
    return Alert(
        alert_id=alert_id,
        opened=opened,
        closed=closed,
        disposition="no_sar",
        rationale=rationale,
        evidence=evidence,
        reasons=reasons,
        kind=kind,
    )


def _sar(alert_id, kind, opened, detected, closed, filed, suspect_known):
    return Alert(
        alert_id=alert_id,
        opened=opened,
        detected=detected,
        closed=closed,
        disposition="sar",
        sar_filed=filed,
        suspect_known=suspect_known,
        rationale=R_SAR,
        evidence=_evidence(alert_id),
        reasons=("activity_reviewed",),
        kind=kind,
    )


def make_suite(p=DEFAULT):
    """Generate the full log: kinds in KINDS order, ids A000001 onward."""
    counts = kind_counts(p)
    day = timedelta(days=1)
    alerts = []
    for kind in KINDS:
        n = counts[kind]
        for j in range(n):
            alert_id = f"A{len(alerts) + 1:06d}"
            if kind == "open_backlog":
                opened = p.as_of - (p.policy_days + 1 + stride(j, 335)) * day
                alerts.append(Alert(alert_id=alert_id, opened=opened, kind=kind))
                continue

            opened = p.as_of - (400 + stride(j, 300)) * day
            within = opened + (1 + j % p.policy_days) * day
            evidence = _evidence(alert_id)

            if kind == "closed_clean":
                alerts.append(
                    _closed(alert_id, kind, opened, within, ("activity_reviewed",), R_REVIEWED, evidence)
                )
            elif kind == "closed_aged":
                closed = opened + (p.policy_days + 1 + j % 120) * day
                alerts.append(
                    _closed(alert_id, kind, opened, closed, ("activity_reviewed",), R_REVIEWED, evidence)
                )
            elif kind == "closed_no_rationale":
                if j % 2 == 0:
                    alerts.append(_closed(alert_id, kind, opened, within, ("false_positive",), "", evidence))
                else:
                    alerts.append(
                        _closed(alert_id, kind, opened, within, ("false_positive",), R_FALSE_POSITIVE, ())
                    )
            elif kind == "closed_prior_filing":
                reasons = (("prior_sar",), ("prior_ctr",), ("prior_sar", "prior_ctr"))[j % 3]
                rationale = R_PRIOR_SAR if reasons[0] == "prior_sar" else R_PRIOR_CTR
                alerts.append(_closed(alert_id, kind, opened, within, reasons, rationale, evidence))
            elif kind == "near_prior_and_review":
                alerts.append(
                    _closed(
                        alert_id,
                        kind,
                        opened,
                        within,
                        ("prior_sar", "activity_reviewed"),
                        R_PRIOR_AND_REVIEW,
                        evidence,
                    )
                )
            elif kind == "near_day_limit":
                suspect_known = j % 2 == 0
                filed = opened + (30 if suspect_known else 60) * day
                closed = opened + p.policy_days * day
                alerts.append(_sar(alert_id, kind, opened, opened, closed, filed, suspect_known))
            else:
                delay = 20 if kind == "near_detect_later" else 0
                detected = opened + (delay + j % 6) * day
                closed = detected + day
                if kind == "sar_on_time":
                    gap = 1 + j % 30
                elif kind == "sar_late":
                    gap = 30 + days_late(j, n, p.mean_days_late)
                elif kind == "near_detect_later":
                    gap = 11 + j % 20
                else:  # near_no_suspect
                    gap = 31 + j % 30
                filed = detected + gap * day
                alerts.append(
                    _sar(alert_id, kind, opened, detected, closed, filed, kind != "near_no_suspect")
                )
    return alerts


def truth(alerts):
    """Map each check to the alert ids its seeded kind should flag."""
    seeded = {}
    for alert in alerts:
        check = VIOLATIONS.get(alert.kind)
        if check is not None:
            seeded.setdefault(check, set()).add(alert.alert_id)
    return {check: seeded[check] for check in CHECKS if check in seeded}

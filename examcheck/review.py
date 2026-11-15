"""One finding per alert and check, with a status and the order passage it rests on."""

from dataclasses import dataclass

from .cases import Alert
from .checks import (
    BASIS,
    CHECKS,
    aged_alert,
    late_sar,
    late_sar_unassessable,
    no_rationale,
    prior_filing_only,
    prior_filing_unassessable,
)

DEFECT = "defect"  # the log shows the failure
RISK = "risk"  # the log shows a likely failure that needs a person to confirm
CANNOT_ASSESS = "cannot_assess"  # the log lacks the input the check needs

# Index into BASIS[check] of the order passage each check cites.
_ORDER_QUOTE = {"late_sar": 2, "aged_alert": 0, "no_rationale": 1, "prior_filing_only": 0}
_REGULATION_QUOTE = {True: 0, False: 1}  # keyed by suspect_known


@dataclass(frozen=True)
class AlertFinding:
    check: str
    alert_id: str
    status: str
    reason: str
    order_id: str
    quote: str
    regulation_quote: str | None = None


def _late_sar_status(alert: Alert, as_of):
    if late_sar_unassessable(alert):
        return CANNOT_ASSESS, "a SAR was filed or is owed but there is no detection date"
    if not late_sar(alert, as_of):
        return None
    if alert.sar_filed is not None:
        return DEFECT, "SAR filed after the deadline"
    if alert.disposition == "sar":
        return DEFECT, "SAR decided but not filed by the deadline"
    return RISK, "alert still undecided past the SAR deadline, a SAR may be owed"


def _aged_status(alert: Alert, as_of):
    if not aged_alert(alert, as_of):
        return None
    return DEFECT, "alert open longer than the bank-policy limit"


def _rationale_status(alert: Alert, as_of):
    if not no_rationale(alert):
        return None
    return DEFECT, "closed with a blank rationale or no evidence"


def _prior_filing_status(alert: Alert, as_of):
    if prior_filing_unassessable(alert):
        return CANNOT_ASSESS, "no-SAR closure with no reason codes"
    if not prior_filing_only(alert):
        return None
    return RISK, "closure relies only on an earlier SAR or CTR, the order faults missing analysis"


_STATUS = {
    "late_sar": _late_sar_status,
    "aged_alert": _aged_status,
    "no_rationale": _rationale_status,
    "prior_filing_only": _prior_filing_status,
}


def _finding(check, alert, status, reason):
    order_id, quote = BASIS[check][_ORDER_QUOTE[check]]
    regulation = None
    if check == "late_sar":
        regulation = BASIS[check][_REGULATION_QUOTE[alert.suspect_known]][1]
    return AlertFinding(check, alert.alert_id, status, reason, order_id, quote, regulation)


def review(alerts, as_of) -> list:
    """Findings in CHECKS order, then log order. Alerts a check does not flag have none."""
    findings = []
    for check in CHECKS:
        for alert in alerts:
            result = _STATUS[check](alert, as_of)
            if result:
                findings.append(_finding(check, alert, *result))
    return findings

'''Deterministic checks over an AML alert-case log, each tied to FinCEN's text.'''

import re
from datetime import timedelta

from .cases import Alert
from .corpus import REGULATION

CHECKS = ('late_sar', 'aged_alert', 'no_rationale', 'prior_filing_only')
POLICY_DAYS = 30

_PRIOR_FILING = re.compile(r'previously filed|prior (?:SAR|CTR)', re.IGNORECASE)
_DATED_CHECKS = frozenset({'late_sar', 'aged_alert'})


def sar_deadline(alert: Alert):
    '''The last day a SAR may be filed under 31 CFR 1020.320(b)(3).'''
    days = POLICY_DAYS if alert.suspect_known else 2 * POLICY_DAYS
    return alert.detected + timedelta(days=days)


def late_sar(alert: Alert, as_of) -> bool:
    '''Whether a SAR was filed late or is still owed after the deadline.'''
    if alert.detected is None:
        return False
    deadline = sar_deadline(alert)
    if alert.sar_filed is not None:
        return alert.sar_filed > deadline
    return alert.disposition != 'no_sar' and as_of > deadline


def aged_alert(alert: Alert, as_of, policy_days: int = POLICY_DAYS) -> bool:
    '''Whether an alert took more than policy_days to close, or is still open.'''
    end = alert.closed or as_of
    return (end - alert.opened).days > policy_days


def no_rationale(alert: Alert) -> bool:
    '''Whether a closed alert lacks a rationale or supporting evidence.'''
    return alert.closed is not None and (not alert.rationale.strip() or not alert.evidence)


def prior_filing_only(alert: Alert) -> bool:
    '''Whether a no-SAR closure rests only on earlier SAR/CTR filings.'''
    return (
        alert.disposition == 'no_sar'
        and bool(alert.reasons)
        and all(reason in ('prior_sar', 'prior_ctr') for reason in alert.reasons)
    )


def late_sar_naive(alert: Alert, as_of) -> bool:
    '''A plausible but wrong version: dates from opened, no 60-day rule.'''
    if alert.detected is None or alert.disposition == 'no_sar':
        return False
    end = alert.sar_filed or as_of
    return (end - alert.opened).days > POLICY_DAYS


def aged_alert_naive(alert: Alert, as_of, policy_days: int = POLICY_DAYS) -> bool:
    '''A plausible but wrong version: ignores closed alerts entirely.'''
    return alert.closed is None and (as_of - alert.opened).days > policy_days


def no_rationale_naive(alert: Alert) -> bool:
    '''A plausible but wrong version: ignores missing evidence.'''
    return alert.closed is not None and not alert.rationale.strip()


def prior_filing_naive(alert: Alert) -> bool:
    '''A plausible but wrong version: keyword matching on free text.'''
    return alert.disposition == 'no_sar' and bool(_PRIOR_FILING.search(alert.rationale))


_STRICT = {
    'late_sar': late_sar,
    'aged_alert': aged_alert,
    'no_rationale': no_rationale,
    'prior_filing_only': prior_filing_only,
}
_NAIVE = {
    'late_sar': late_sar_naive,
    'aged_alert': aged_alert_naive,
    'no_rationale': no_rationale_naive,
    'prior_filing_only': prior_filing_naive,
}


def run_checks(alerts, as_of, naive: bool = False) -> dict:
    '''Run all checks, keyed in CHECKS order with alert ids in log order.'''
    rules = _NAIVE if naive else _STRICT
    result = {}
    for check in CHECKS:
        rule = rules[check]
        if check in _DATED_CHECKS:
            result[check] = [alert.alert_id for alert in alerts if rule(alert, as_of)]
        else:
            result[check] = [alert.alert_id for alert in alerts if rule(alert)]
    return result


BASIS = {
    'late_sar': (
        (
            REGULATION,
            'A bank is required to file a SAR no later than 30 calendar days after the date of initial '
            'detection by the bank of facts that may constitute a basis for filing a SAR.',
        ),
        (
            REGULATION,
            'In no case shall reporting be delayed more than 60 calendar days after the date of initial '
            'detection of a reportable transaction.',
        ),
        ('19518', 'the Bank filed several hundred SARs an average of approximately 119 days late'),
        ('17535', 'the Bank filed 75 initial suspicious activity reports, 67 of which were not timely filed.'),
    ),
    'aged_alert': (
        (
            '17488',
            'Gibraltar failed to review and close or escalate nearly 60% of its monthly alerts in the 30 days '
            'prescribed by Gibraltar’s own BSA/AML policy.',
        ),
        (
            '19518',
            'At one point, the Bank had a backlog of over 10,000 alert events (within more than 700 pre-cases) '
            'that had not been reviewed.',
        ),
        (
            '19701',
            'In 2018, the AML program registered over 70,000 backlogged detection alerts and roughly 3,000 aged '
            'subpoena responses and further investigation cases, with less than 60% of alerts falling within '
            'benchmarks for timely detection.',
        ),
        ('18845', 'Lone Star had 4,888 outstanding alerts, 627 cases, and 213 internal referrals.'),
    ),
    'no_rationale': (
        (
            '19518',
            'the Bank’s internal policies required analysts to consider and append documentation on any alerts '
            'raised by the TM system.',
        ),
        (
            '17552',
            'the Branch could not produce any analysis or documentation to support the U.S. Compliance '
            'Officer’s assertion that the cash activity appeared normal.',
        ),
        ('19328', 'did not provide sufficient support to justify the closure.'),
    ),
    'prior_filing_only': (
        (
            '19518',
            'At times, the justification for clearing an alert, as opposed to escalating it, relied on whether '
            'the Bank previously filed a SAR or a currency transaction report, rather than on an analysis of '
            'the actual account activity and a determination of its reasonableness.',
        ),
        (
            '19328',
            'BSA analysts cleared the activity by using the same pre-set reason code, namely: “A SAR was '
            'previously filed and is not due for review at this time.”',
        ),
    ),
}

"""Fixed failure categories and their keyword patterns."""

import re

CATEGORIES = (
    "alert_backlog",
    "late_sar",
    "sar_not_filed",
    "unsupported_disposition",
    "monitoring_gap",
    "cdd_edd",
    "ctr",
    "staffing",
    "independent_testing",
    "governance",
)

LABELS = {
    "alert_backlog": "Alert backlog",
    "late_sar": "Late SAR",
    "sar_not_filed": "SAR not filed",
    "unsupported_disposition": "Unsupported disposition",
    "monitoring_gap": "Monitoring gap",
    "cdd_edd": "CDD / EDD",
    "ctr": "CTR filing",
    "staffing": "Staffing",
    "independent_testing": "Independent testing",
    "governance": "Governance",
}

FAIL = (
    r"(?:fail\w*|inadequate\w*|insufficient\w*|deficien\w+|lack\w*|"
    r"did not|ineffective|weak\w*|not adequate\w*)"
)

_TEMPLATES = {
    "alert_backlog": (
        r"backlog",
        r"\b(?:unreviewed|unworked|aged|aging|stale) (?:alerts?|cases?)\b",
        (
            r"\balerts?\b.{0,60}\b(?:not|never) (?:been )?"
            r"(?:reviewed|investigated|worked|dispositioned)\b"
        ),
    ),
    "late_sar": (
        r"\b(?:untimely|late)\b.{0,60}\b(?:SARs?|suspicious activity reports?)\b",
        (
            r"\b(?:SARs?|suspicious activity reports?)\b.{0,60}"
            r"\b(?:untimely|late|not timely|delayed)\b"
        ),
        r"\bfail\w* to (?:timely|promptly) file\b",
    ),
    "sar_not_filed": (
        (
            r"\bfail\w* to (?:file|report)\b.{0,80}"
            r"\b(?:SARs?|suspicious activity reports?|suspicious transactions?)\b"
        ),
        r"\bdid not (?:file|report)\b.{0,60}\b(?:SARs?|suspicious)",
        r"\b(?:unreported|unfiled) suspicious\b",
    ),
    "unsupported_disposition": (
        r"\b(?:closed|cleared|dispositioned|resolved)\b.{0,80}\bwithout\b",
        (
            r"\b(?:inadequate|insufficient|lack of|without)\b.{0,30}"
            r"\b(?:documentation|rationale|justification|support)\b"
        ),
        (
            r"\b(?:alerts?|cases?|investigations?)\b.{0,80}"
            r"\b(?:inadequately|insufficiently|poorly) "
            r"(?:documented|investigated|supported|reviewed)\b"
        ),
    ),
    "monitoring_gap": (
        r"\b(?:transaction|account|suspicious activity) monitoring\b.{0,80}FAIL",
        r"FAIL.{0,60}\b(?:transaction|account|automated|suspicious activity) monitoring\b",
        r"\b(?:thresholds?|scenarios?)\b.{0,60}\b(?:tun\w+|calibrat\w+)\b",
    ),
    "cdd_edd": (
        (
            r"FAIL.{0,80}\b(?:due diligence|know your customer|KYC|"
            r"customer identification|beneficial own\w+|risk rat\w+)\b"
        ),
        (
            r"\b(?:due diligence|know your customer|KYC|customer identification|"
            r"beneficial own\w+|risk rat\w+)\b.{0,80}FAIL"
        ),
    ),
    "ctr": (
        (
            r"(?:fail\w*|did not|untimely|late|inaccurate|incomplete)\b.{0,60}"
            r"\b(?:currency transaction reports?|CTRs?)\b"
        ),
        (
            r"\b(?:currency transaction reports?|CTRs?)\b.{0,60}"
            r"\b(?:late|untimely|not (?:filed|timely)|inaccurate|incomplete)\b"
        ),
        r"\bimproperly exempt\w*\b",
    ),
    "staffing": (
        r"\b(?:staff\w*|personnel|resources)\b.{0,60}FAIL",
        r"FAIL.{0,40}\b(?:staff\w*|personnel|resources)\b",
        r"\bunder-?staff\w*",
    ),
    "independent_testing": (
        r"\bindependent (?:testing|tests?|audits?|reviews?)\b.{0,80}FAIL",
        r"FAIL.{0,60}\bindependent (?:testing|tests?|audits?|reviews?)\b",
    ),
    "governance": (
        r"\bBSA (?:officer|compliance officer|department|function)\b.{0,80}FAIL",
        (
            r"\b(?:senior management|board of directors|management|board)\b.{0,60}"
            r"\b(?:fail\w*|did not|inadequate\w*|ignored|lack\w*)\b"
        ),
        r"\bculture of (?:non-?)?compliance\b",
        r"FAIL.{0,40}\b(?:oversight|governance|internal controls?)\b",
    ),
}

PATTERNS = {
    category: tuple(pattern.replace("FAIL", FAIL) for pattern in _TEMPLATES[category])
    for category in CATEGORIES
}
COMPILED = {
    category: tuple(re.compile(pattern, re.IGNORECASE) for pattern in PATTERNS[category])
    for category in CATEGORIES
}

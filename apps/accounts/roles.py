"""The four role names (Tech Risk, auditor, control owner, read only) in one place."""

TECH_RISK = "tech_risk"
CONTROL_OWNER = "control_owner"
AUDITOR = "auditor"
READ_ONLY = "read_only"

ROLE_CHOICES = [
    (TECH_RISK, "Tech Risk"),
    (CONTROL_OWNER, "Control owner"),
    (AUDITOR, "Auditor"),
    (READ_ONLY, "Read only"),
]
ALL_ROLES = frozenset(value for value, _ in ROLE_CHOICES)

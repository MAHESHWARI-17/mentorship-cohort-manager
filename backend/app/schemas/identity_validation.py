import re


def validate_employee_id_format(value: str) -> str:
    normalized = str(value or "").strip()
    if not re.fullmatch(r"\d{7}", normalized):
        raise ValueError("Employee ID must be exactly 7 digits")
    return normalized


def validate_mphasis_email_format(value) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized.endswith("@mphasis.com"):
        raise ValueError('Email must end with "@mphasis.com"')
    return normalized

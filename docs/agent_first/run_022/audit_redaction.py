"""Pure publication redaction for audit copies, not a credential revocation API."""
SECRET_KEYS = frozenset({'credential', 'ciphertext', 'operator_token'})
REDACTED = '[REDACTED: audit copy; original authentication material omitted]'

def redact(value):
    if isinstance(value, dict):
        return {k: REDACTED if k in SECRET_KEYS and isinstance(v, str) and v else redact(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value

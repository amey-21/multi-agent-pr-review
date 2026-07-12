import hmac
import hashlib


def verify_github_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """
    Recomputes GitHub's HMAC-SHA256 signature over the raw request body
    using our shared webhook secret, and compares it against the
    signature GitHub sent in the X-Hub-Signature-256 header.
    
    WHY bytes, not a parsed dict?
    HMAC verification must run over the EXACT raw bytes GitHub sent.
    If we parsed the JSON first and re-serialized it to compute the
    signature, even a single differing whitespace character would
    produce a different hash — so we verify BEFORE any parsing happens.
    
    Args:
        payload_body: the raw, unparsed request body bytes
        signature_header: the value of the X-Hub-Signature-256 header,
                           formatted as "sha256=<hex digest>"
        secret: our shared webhook secret (set in GitHub App config
                and stored in our .env)
    
    Returns:
        True if the signature is valid, False otherwise
    """
    if not signature_header:
        return False
    if not secret:
        # misconfiguration on OUR side, not a malicious request —
        # still must fail closed (reject), not crash with a 500
        return False
    if not signature_header.startswith("sha256="):
        return False

    # extract just the hex digest part, after "sha256="
    expected_signature = signature_header.split("sha256=", 1)[1]

    # compute OUR OWN signature over the same payload using the same secret
    mac = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    computed_signature = mac.hexdigest()

    # hmac.compare_digest instead of == is CRITICAL here — explained below
    return hmac.compare_digest(computed_signature, expected_signature)
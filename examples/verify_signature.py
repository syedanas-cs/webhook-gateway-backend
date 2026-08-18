import hashlib
import hmac
import time


def verify_incoming_webhook(raw_payload_bytes: bytes, sig_header: str, secret: str) -> bool:
    """
    Validates the HMAC-SHA256 signature header sent by the Webhook Gateway.
    Format: t=<timestamp>,v1=<hex_digest>
    """
    # 1. Parse timestamp and signature components
    parts = dict(item.split("=", 1) for item in sig_header.split(","))
    timestamp = parts.get("t")
    signature = parts.get("v1")

    # 2. Check tolerance window (5-minute tolerance against replay attacks)
    if not timestamp or not signature or abs(int(time.time()) - int(timestamp)) > 300:
        return False

    # 3. Recompute expected digest using the shared secret
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=f"t={timestamp}.".encode("utf-8") + raw_payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # 4. Constant-time string comparison
    return hmac.compare_digest(expected, signature)


if __name__ == "__main__":
    # Example usage:
    sample_secret = "test_secret_token_12345"
    sample_payload = b'{"event_type":"invoice.paid","payload":{"amount":250}}'
    sample_timestamp = str(int(time.time()))
    
    # Compute sample header
    signed_payload = f"t={sample_timestamp}.".encode("utf-8") + sample_payload
    computed_digest = hmac.new(
        sample_secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    sample_header = f"t={sample_timestamp},v1={computed_digest}"

    # Verify
    is_valid = verify_incoming_webhook(sample_payload, sample_header, sample_secret)
    print(f"Signature valid: {is_valid}")
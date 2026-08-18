import hashlib
import hmac
import time


class WebhookVerificationError(Exception):
    """Base exception for webhook verification failures."""
    pass


class WebhookSignatureVerifier:
    def __init__(self, tolerance_seconds: int = 300):
        """
        :param tolerance_seconds: Maximum allowed age of the webhook timestamp
                                  in seconds (default 300s / 5 minutes).
        """
        self.tolerance_seconds = tolerance_seconds

    def parse_header(self, header_value: str) -> tuple[str, str]:
        """
        Parses the `X-Webhook-Signature` header string.
        Format expected: "t=<timestamp>,v1=<hex_signature>"
        """
        if not header_value:
            raise WebhookVerificationError("Missing webhook signature header.")

        elements = header_value.strip().split(",")
        timestamp: str | None = None
        signature: str | None = None

        for element in elements:
            parts = element.split("=", 1)
            if len(parts) != 2:
                continue
            key, val = parts[0].strip(), parts[1].strip()
            if key == "t":
                timestamp = val
            elif key == "v1":
                signature = val

        if not timestamp or not signature:
            raise WebhookVerificationError("Malformed signature header format.")

        return timestamp, signature

    def compute_signature(self, secret: str, timestamp: str, raw_body: str | bytes) -> str:
        """Computes the expected HMAC-SHA256 signature."""
        if isinstance(raw_body, str):
            raw_body = raw_body.encode("utf-8")

        payload_to_sign = f"t={timestamp}.".encode("utf-8") + raw_body
        return hmac.new(
            key=secret.encode("utf-8"),
            msg=payload_to_sign,
            digestmod=hashlib.sha256,
        ).hexdigest()

    def verify(
        self,
        raw_body: str | bytes,
        header_value: str,
        secret: str,
        current_time: float | None = None,
    ) -> bool:
        """
        Validates the raw request payload against the provided header and secret.
        
        :raises WebhookVerificationError: If verification fails or timestamp expired.
        """
        timestamp, received_signature = self.parse_header(header_value)

        # 1. Replay attack prevention: Validate timestamp freshness
        try:
            timestamp_int = int(timestamp)
        except ValueError:
            raise WebhookVerificationError("Invalid timestamp in signature header.")

        now = int(current_time or time.time())
        if abs(now - timestamp_int) > self.tolerance_seconds:
            raise WebhookVerificationError("Timestamp outside tolerance window (replay attack protection).")

        # 2. Compute expected digest
        expected_signature = self.compute_signature(secret, timestamp, raw_body)

        # 3. Constant-time comparison to protect against timing attacks
        if not hmac.compare_digest(expected_signature, received_signature):
            raise WebhookVerificationError("Signature mismatch: payload or secret invalid.")

        return True


# Default instance
verifier = WebhookSignatureVerifier()
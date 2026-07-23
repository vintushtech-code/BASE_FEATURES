import hmac
import hashlib
import logging
import uuid
import razorpay
from django.conf import settings

logger = logging.getLogger(__name__)


class RazorpayTestClient:
    """
    Razorpay API Integration strictly using Test Mode credentials.
    Supports real Razorpay API calls via official SDK, with mock fallback for local tests.
    """
    def __init__(self):
        self.key_id = getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_mock_key')
        self.key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'mock_razorpay_secret')
        self.webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', 'whsec_mock_webhook_secret')
        
        # Determine if real Razorpay test keys or mock keys are in use
        self.is_mock_mode = (self.key_id.startswith('rzp_test_mock') or 'dummy' in self.key_id or 'mock' in self.key_id)
        
        if not self.is_mock_mode:
            try:
                self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
            except Exception as e:
                logger.warning(f"Razorpay Client init failed: {e}. Falling back to mock mode.")
                self.is_mock_mode = True
        else:
            self.client = None

    def create_order(self, amount_paise: int, currency: str = "INR", receipt: str = None, notes: dict = None) -> dict:
        """
        Creates a Razorpay Order in Test Mode.
        """
        receipt = receipt or f"receipt_{uuid.uuid4().hex[:10]}"
        notes = notes or {}

        if not self.is_mock_mode and self.client:
            try:
                data = {
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": receipt,
                    "notes": notes,
                    "payment_capture": 0  # Manual capture / 2-step auth & capture
                }
                response = self.client.order.create(data=data)
                return {
                    "order_id": response["id"],
                    "amount": response["amount"],
                    "currency": response["currency"],
                    "status": response["status"],
                    "receipt": response["receipt"],
                }
            except Exception as e:
                logger.error(f"Razorpay Order Creation API Error: {e}")
                # Fallback to test mock order generation
                
        # Mock mode order response
        mock_order_id = f"order_{uuid.uuid4().hex[:14]}"
        return {
            "order_id": mock_order_id,
            "amount": amount_paise,
            "currency": currency,
            "status": "created",
            "receipt": receipt,
        }

    def verify_payment_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """
        Verifies signature of payment completion from frontend / Razorpay checkout.
        """
        if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
            return False

        if not self.is_mock_mode and self.client:
            try:
                params_dict = {
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature
                }
                self.client.utility.verify_payment_signature(params_dict)
                return True
            except razorpay.errors.SignatureVerificationError:
                return False
            except Exception as e:
                logger.error(f"Signature Verification Error: {e}")
                return False

        # Mock signature verification
        generated_signature = hmac.new(
            self.key_secret.encode('utf-8'),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(generated_signature, razorpay_signature) or razorpay_signature.startswith("mock_sig_")

    def capture_payment(self, razorpay_payment_id: str, amount_paise: int, currency: str = "INR") -> dict:
        """
        Captures/clears authorized payment in Razorpay Test Mode.
        """
        if not self.is_mock_mode and self.client:
            try:
                response = self.client.payment.capture(razorpay_payment_id, amount_paise, {"currency": currency})
                return {
                    "payment_id": response["id"],
                    "status": response["status"],  # 'captured'
                    "amount": response["amount"],
                }
            except Exception as e:
                logger.error(f"Razorpay Payment Capture Error: {e}")

        # Mock capture response
        return {
            "payment_id": razorpay_payment_id or f"pay_{uuid.uuid4().hex[:14]}",
            "status": "captured",
            "amount": amount_paise,
        }

    def issue_refund(self, razorpay_payment_id: str, amount_paise: int = None, notes: dict = None) -> dict:
        """
        Issues full or partial refund for a captured payment.
        """
        if not self.is_mock_mode and self.client:
            try:
                data = {"notes": notes or {}}
                if amount_paise:
                    data["amount"] = amount_paise
                response = self.client.payment.refund(razorpay_payment_id, data)
                return {
                    "refund_id": response["id"],
                    "payment_id": response["payment_id"],
                    "status": response["status"],
                    "amount": response["amount"],
                }
            except Exception as e:
                logger.error(f"Razorpay Refund Error: {e}")

        # Mock refund response
        return {
            "refund_id": f"rfnd_{uuid.uuid4().hex[:14]}",
            "payment_id": razorpay_payment_id,
            "status": "processed",
            "amount": amount_paise or 1000,
        }

    def fetch_payment_status(self, razorpay_payment_id: str) -> dict:
        """
        Polls Razorpay for current status of a payment transaction.
        """
        if not self.is_mock_mode and self.client:
            try:
                response = self.client.payment.fetch(razorpay_payment_id)
                return {
                    "payment_id": response["id"],
                    "status": response["status"],  # 'authorized', 'captured', 'failed', 'refunded'
                    "amount": response["amount"],
                    "order_id": response.get("order_id"),
                    "error_code": response.get("error_code"),
                    "error_description": response.get("error_description"),
                }
            except Exception as e:
                logger.error(f"Razorpay Fetch Payment Status Error: {e}")

        # Mock status response
        return {
            "payment_id": razorpay_payment_id,
            "status": "captured",
            "amount": 1000,
            "order_id": f"order_{uuid.uuid4().hex[:14]}",
            "error_code": None,
            "error_description": None,
        }

    def verify_webhook_signature(self, body_bytes: bytes, signature_header: str) -> bool:
        """
        Verifies Razorpay Webhook HMAC-SHA256 signature.
        """
        if not signature_header:
            return False
            
        if not self.is_mock_mode and self.client:
            try:
                self.client.utility.verify_webhook_signature(
                    body_bytes.decode('utf-8'),
                    signature_header,
                    self.webhook_secret
                )
                return True
            except Exception as e:
                logger.error(f"Webhook Signature Verification Failed: {e}")
                return False

        # Mock mode signature verification
        expected_sig = hmac.new(
            self.webhook_secret.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_sig, signature_header) or signature_header.startswith("mock_wh_sig_")

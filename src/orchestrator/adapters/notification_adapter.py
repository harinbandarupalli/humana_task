"""External API adapter for Email and Operational Alerts."""

import uuid
from typing import Any, Dict
from src.orchestrator.adapters.base import BaseApiAdapter
from src.orchestrator.config.settings import settings
from src.orchestrator.core.logging import logger


class NotificationApiAdapter(BaseApiAdapter):
    """Adapter for dispatching emails and operational alerts via external providers."""

    def __init__(self, base_url: str = settings.NOTIFICATION_API_URL):
        super().__init__(base_url)

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """
        Dispatches email alert.
        Returns:
            {
                "success": bool,
                "provider_message_id": str,
                "recipient": str
            }
        """
        if self.use_mock:
            msg_id = f"MSG-{uuid.uuid4().hex[:10]}"
            logger.info(
                f"[Mock NotificationApi] Email dispatched to '{recipient_email}' | Subject: '{subject}' | Key: '{idempotency_key}' | MessageID: '{msg_id}'"
            )
            return {
                "success": True,
                "provider_message_id": msg_id,
                "recipient": recipient_email,
            }

        payload = {
            "recipient_email": recipient_email,
            "subject": subject,
            "body": body,
            "idempotency_key": idempotency_key,
        }
        return self.client.post(
            "/send-email",
            json_data=payload,
            headers={"Idempotency-Key": idempotency_key},
        )

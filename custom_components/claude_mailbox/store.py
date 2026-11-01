"""Persistent message storage for the Claude Mailbox integration."""

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.ulid import ulid_now

from .const import DOMAIN, MAX_STORED_MESSAGES, RETENTION_DAYS, SIGNAL_UPDATED

STORAGE_VERSION = 1
SAVE_DELAY = 1


class MailboxStore:
    """Store messages, addressed by the person entity IDs of the participants."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the store."""
        self._hass = hass
        self._store: Store[dict[str, list[dict[str, Any]]]] = Store(
            hass, STORAGE_VERSION, DOMAIN, private=True
        )
        self._messages: list[dict[str, Any]] = []

    async def async_load(self) -> None:
        """Load the stored messages."""
        if (data := await self._store.async_load()) is not None:
            self._messages = data["messages"]
        self._prune()

    @callback
    def async_add(
        self,
        sender: str,
        recipient: str,
        body: str,
        subject: str | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        """Add a message."""
        message = {
            "id": ulid_now(),
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "reply_to": reply_to,
            "sent_at": dt_util.utcnow().isoformat(),
            "read_at": None,
        }
        self._messages.append(message)
        self._prune()
        self._async_changed()
        return message

    @callback
    def async_inbox(
        self, recipient: str, unread_only: bool, limit: int
    ) -> list[dict[str, Any]]:
        """Return the newest messages of a recipient, oldest first."""
        messages = [
            message
            for message in self._messages
            if message["recipient"] == recipient
            and not (unread_only and message["read_at"])
        ]
        return messages[-limit:]

    @callback
    def async_mark_read(self, recipient: str, message_ids: list[str]) -> int:
        """Mark messages of a recipient as read and return how many changed."""
        wanted = set(message_ids)
        now = dt_util.utcnow().isoformat()
        changed = 0
        for message in self._messages:
            if (
                message["id"] in wanted
                and message["recipient"] == recipient
                and not message["read_at"]
            ):
                message["read_at"] = now
                changed += 1
        if changed:
            self._async_changed()
        return changed

    @callback
    def async_unread_count(self, recipient: str) -> int:
        """Return the number of unread messages of a recipient."""
        return sum(
            1
            for message in self._messages
            if message["recipient"] == recipient and not message["read_at"]
        )

    @callback
    def async_sent_count(self, sender: str, since: datetime) -> int:
        """Return how many messages a sender has sent since a point in time."""
        return sum(
            1
            for message in self._messages
            if message["sender"] == sender
            and dt_util.parse_datetime(message["sent_at"], raise_on_error=True) >= since
        )

    @callback
    def async_can_read(self, person: str, message_id: str) -> bool:
        """Return if a message exists and the person sent or received it."""
        return any(
            message["id"] == message_id and person in (message["sender"], message["recipient"])
            for message in self._messages
        )

    def _prune(self) -> None:
        """Drop messages past the retention period and enforce the size limit."""
        cutoff = dt_util.utcnow() - timedelta(days=RETENTION_DAYS)
        self._messages = [
            message
            for message in self._messages
            if dt_util.parse_datetime(message["sent_at"], raise_on_error=True) >= cutoff
        ][-MAX_STORED_MESSAGES:]

    @callback
    def _async_changed(self) -> None:
        """Schedule a save and notify listeners."""
        self._store.async_delay_save(lambda: {"messages": self._messages}, SAVE_DELAY)
        async_dispatcher_send(self._hass, SIGNAL_UPDATED)

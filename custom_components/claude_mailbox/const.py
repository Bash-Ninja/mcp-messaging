"""Constants for the Claude Mailbox integration."""

DOMAIN = "claude_mailbox"
API_NAME = "Claude Mailbox"

CONF_PARTICIPANTS = "participants"

EVENT_MESSAGE = "claude_mailbox_message"
SIGNAL_UPDATED = "claude_mailbox_updated"

MAX_BODY_LENGTH = 8000
MAX_SUBJECT_LENGTH = 200
MAX_SENT_PER_HOUR = 30
MAX_STORED_MESSAGES = 1000
RETENTION_DAYS = 90
DEFAULT_INBOX_LIMIT = 20
MAX_INBOX_LIMIT = 50

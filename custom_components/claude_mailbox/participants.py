"""Resolve configured person entities to mailbox participants."""

from dataclasses import dataclass

from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant

ATTR_USER_ID = "user_id"


@dataclass(frozen=True, slots=True)
class Participant:
    """A person who can send and receive messages."""

    entity_id: str
    user_id: str
    name: str


def async_get_participants(
    hass: HomeAssistant, entity_ids: list[str]
) -> list[Participant]:
    """Return the configured persons that are linked to a Home Assistant user."""
    participants = []
    for entity_id in entity_ids:
        if (state := hass.states.get(entity_id)) is None:
            continue
        if (user_id := state.attributes.get(ATTR_USER_ID)) is None:
            continue
        name = state.attributes.get(ATTR_FRIENDLY_NAME, entity_id)
        participants.append(Participant(entity_id, user_id, name))
    return participants

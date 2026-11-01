"""Unread message counters for the Claude Mailbox integration."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ClaudeMailboxConfigEntry
from .const import CONF_PARTICIPANTS, SIGNAL_UPDATED
from .store import MailboxStore


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClaudeMailboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one unread counter per participant."""
    entities = []
    for entity_id in entry.options[CONF_PARTICIPANTS]:
        state = hass.states.get(entity_id)
        name = state.attributes.get(ATTR_FRIENDLY_NAME) if state else None
        entities.append(
            UnreadSensor(entry, entry.runtime_data, entity_id, name or entity_id)
        )
    async_add_entities(entities)


class UnreadSensor(SensorEntity):
    """Number of unread messages of a participant."""

    _attr_icon = "mdi:email-outline"
    _attr_should_poll = False
    _attr_native_unit_of_measurement = "messages"

    def __init__(
        self,
        entry: ClaudeMailboxConfigEntry,
        store: MailboxStore,
        person: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        self._store = store
        self._person = person
        self._attr_name = f"Claude Mailbox {name}"
        self._attr_unique_id = f"{entry.entry_id}_{person}_unread"

    @property
    def native_value(self) -> int:
        """Return the number of unread messages."""
        return self._store.async_unread_count(self._person)

    async def async_added_to_hass(self) -> None:
        """Update when the mailbox changes."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATED, self._async_handle_update
            )
        )

    @callback
    def _async_handle_update(self) -> None:
        """Write the new state."""
        self.async_write_ha_state()

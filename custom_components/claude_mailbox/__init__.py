"""The Claude Mailbox integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import CONF_PARTICIPANTS
from .llm_api import MailboxAPI
from .store import MailboxStore

PLATFORMS = [Platform.SENSOR]

type ClaudeMailboxConfigEntry = ConfigEntry[MailboxStore]


async def async_setup_entry(
    hass: HomeAssistant, entry: ClaudeMailboxConfigEntry
) -> bool:
    """Set up Claude Mailbox from a config entry."""
    store = MailboxStore(hass)
    await store.async_load()
    entry.runtime_data = store

    entry.async_on_unload(
        llm.async_register_api(
            hass, MailboxAPI(hass, store, entry.options[CONF_PARTICIPANTS])
        )
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ClaudeMailboxConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

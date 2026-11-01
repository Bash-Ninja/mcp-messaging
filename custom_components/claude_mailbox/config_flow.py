"""Config flow for the Claude Mailbox integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import API_NAME, CONF_PARTICIPANTS, DOMAIN
from .participants import async_get_participants


def _schema(default: list[str] | None = None) -> vol.Schema:
    """Return the form to select the participants."""
    return vol.Schema(
        {
            vol.Required(
                CONF_PARTICIPANTS, default=default or []
            ): EntitySelector(EntitySelectorConfig(domain="person", multiple=True))
        }
    )


def _validate(hass: HomeAssistant, entity_ids: list[str]) -> dict[str, str]:
    """Return the form errors for the selected participants."""
    participants = async_get_participants(hass, entity_ids)
    if len(entity_ids) < 2:
        return {"base": "too_few_participants"}
    if len(participants) != len(entity_ids):
        return {"base": "person_without_user"}
    if len({item.name for item in participants}) != len(participants):
        return {"base": "duplicate_name"}
    return {}


class ClaudeMailboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Claude Mailbox."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> "ClaudeMailboxOptionsFlow":
        """Return the options flow."""
        return ClaudeMailboxOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the participants."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(self.hass, user_input[CONF_PARTICIPANTS])
            if not errors:
                return self.async_create_entry(
                    title=API_NAME, data={}, options=user_input
                )
        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)


class ClaudeMailboxOptionsFlow(OptionsFlowWithReload):
    """Change the participants."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the participants."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(self.hass, user_input[CONF_PARTICIPANTS])
            if not errors:
                return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(self.config_entry.options[CONF_PARTICIPANTS]),
            errors=errors,
        )

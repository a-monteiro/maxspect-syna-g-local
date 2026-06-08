"""Config flow for Maxspect Syna-G Local."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DEVICES, DEFAULT_PORT, DOMAIN


def _device_schema(default_name: str = "Maxspect Syna-G", default_host: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=default_name): str,
            vol.Required(CONF_HOST, default=default_host): str,
            vol.Optional("port", default=DEFAULT_PORT): int,
        }
    )


class MaxspectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Maxspect Syna-G Local."""

    VERSION = 1

    def __init__(self) -> None:
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure the first device."""

        if user_input is not None:
            self._devices.append(user_input)
            return await self.async_step_add_another()

        return self.async_show_form(step_id="user", data_schema=_device_schema())

    async def async_step_add_another(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Ask whether to add another device."""

        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_extra_device()
            title = "Maxspect Syna-G Local"
            if len(self._devices) == 1:
                title = self._devices[0][CONF_NAME]
            return self.async_create_entry(title=title, data={CONF_DEVICES: self._devices})

        return self.async_show_form(
            step_id="add_another",
            data_schema=vol.Schema({vol.Required("add_another", default=False): bool}),
        )

    async def async_step_extra_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure an additional device."""

        if user_input is not None:
            self._devices.append(user_input)
            return await self.async_step_add_another()

        return self.async_show_form(
            step_id="extra_device",
            data_schema=_device_schema(default_name=f"Maxspect Syna-G {len(self._devices) + 1}"),
        )

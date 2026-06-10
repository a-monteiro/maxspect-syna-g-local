"""Maxspect Syna-G Local integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_DEVICES, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .gagent import CHANNEL_NAMES, control, encode_device_time, manual_channel_updates, probe

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["binary_sensor", "button", "light", "number", "sensor"]
SERVICE_APPLY_MANUAL_PRESET = "apply_manual_preset"
SERVICE_APPLY_MANUAL_PRESET_SCHEMA = vol.Schema(
    {
        vol.Optional("device"): str,
        **{
            vol.Required(channel): vol.All(vol.Coerce(int), vol.Range(min=0, max=100))
            for channel in CHANNEL_NAMES
        },
    }
)


class MaxspectCoordinator(DataUpdateCoordinator):
    """Coordinator for one Maxspect local device."""

    def __init__(self, hass: HomeAssistant, name: str, host: str, port: int = DEFAULT_PORT) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        self.device_name = name
        self.host = host
        self.port = port

    async def _async_update_data(self):
        return await self.hass.async_add_executor_job(probe, self.host, self.port)

    async def async_resume_auto(self) -> None:
        """Resume the device's stored automatic/lunar schedule."""

        self.async_set_updated_data(await self.hass.async_add_executor_job(control, self.host, {"MODE": 1}, self.port))

    async def async_turn_channels_off(self) -> None:
        """Explicitly set all manual channel outputs to zero."""

        updates = {f"channel_{idx}": 0 for idx in range(1, 7)}
        self.async_set_updated_data(await self.hass.async_add_executor_job(control, self.host, updates, self.port))

    async def async_set_channel(self, channel: str, value: int) -> None:
        """Set one manual channel output percentage."""

        if channel not in CHANNEL_NAMES:
            raise ValueError(f"unknown channel {channel}")
        if not 0 <= value <= 100:
            raise ValueError("channel value must be between 0 and 100")
        self.async_set_updated_data(await self.hass.async_add_executor_job(control, self.host, {channel: value}, self.port))

    async def async_apply_manual_preset(self, values: list[int]) -> None:
        """Apply a six-channel manual preset."""

        self.async_set_updated_data(
            await self.hass.async_add_executor_job(control, self.host, manual_channel_updates(values), self.port)
        )

    async def async_sync_device_time(self) -> None:
        """Sync the controller clock to Home Assistant's local time."""

        now = dt_util.now().replace(microsecond=0)
        self.async_set_updated_data(
            await self.hass.async_add_executor_job(control, self.host, {"time": encode_device_time(now)}, self.port)
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Maxspect Syna-G Local from a config entry."""

    devices = entry.data.get(CONF_DEVICES) or [entry.data]
    coordinators: list[MaxspectCoordinator] = []

    for idx, device in enumerate(devices, start=1):
        host = device[CONF_HOST]
        name = device.get(CONF_NAME) or f"Maxspect Syna-G {idx}"
        port = int(device.get("port", DEFAULT_PORT))
        coordinator = MaxspectCoordinator(hass, name, host, port)
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _all_coordinators(hass: HomeAssistant) -> list[MaxspectCoordinator]:
    """Return all loaded Maxspect coordinators."""

    return [coordinator for entry_coordinators in hass.data.get(DOMAIN, {}).values() for coordinator in entry_coordinators]


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""

    if hass.services.has_service(DOMAIN, SERVICE_APPLY_MANUAL_PRESET):
        return

    async def async_apply_manual_preset(call: ServiceCall) -> None:
        device = call.data.get("device")
        values = [call.data[channel] for channel in CHANNEL_NAMES]
        coordinators = _all_coordinators(hass)
        if device:
            coordinators = [
                coordinator
                for coordinator in coordinators
                if coordinator.device_name == device or coordinator.host == device
            ]
        if not coordinators:
            raise ValueError(f"no Maxspect Syna-G devices matched {device!r}")
        await asyncio.gather(*(coordinator.async_apply_manual_preset(values) for coordinator in coordinators))

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_MANUAL_PRESET,
        async_apply_manual_preset,
        schema=SERVICE_APPLY_MANUAL_PRESET_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok

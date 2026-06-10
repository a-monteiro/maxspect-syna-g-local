"""Maxspect Syna-G Local integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_DEVICES, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .gagent import control, encode_device_time, probe

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["binary_sensor", "button", "light", "sensor"]


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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok

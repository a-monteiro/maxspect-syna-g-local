"""Maxspect Syna-G Local integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_DEVICES, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .gagent import probe

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["binary_sensor", "sensor"]


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

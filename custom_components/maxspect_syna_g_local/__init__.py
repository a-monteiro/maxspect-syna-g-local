"""Maxspect Syna-G Local integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_DEVICES, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .gagent import (
    CHANNEL_NAMES,
    control,
    encode_device_time,
    lunar_other_update,
    manual_channel_updates,
    probe,
    schedule_auto_update,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["binary_sensor", "button", "light", "number", "sensor", "switch"]
SCHEDULE_BACKUPS_STORAGE_KEY = f"{DOMAIN}_schedule_backups"
SERVICE_APPLY_MANUAL_PRESET = "apply_manual_preset"
SERVICE_BACKUP_SCHEDULE = "backup_schedule"
SERVICE_RESTORE_SCHEDULE = "restore_schedule"
SERVICE_APPLY_LUNAR_CONFIG = "apply_lunar_config"
DEVICE_OPTIONAL_SCHEMA = vol.Schema({vol.Optional("device"): str})
THREE_PERCENTAGES_SCHEMA = vol.All(
    [vol.All(vol.Coerce(int), vol.Range(min=0, max=100))], vol.Length(min=3, max=3)
)
SERVICE_APPLY_LUNAR_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional("device"): str,
        vol.Optional("enabled"): bool,
        vol.Optional("high_channels"): THREE_PERCENTAGES_SCHEMA,
        vol.Optional("low_channels"): THREE_PERCENTAGES_SCHEMA,
        vol.Optional("cycle_day"): vol.All(vol.Coerce(int), vol.Range(min=0, max=29)),
    }
)
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

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        host: str,
        port: int = DEFAULT_PORT,
        schedule_store: Store | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}:{name}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS),
        )
        self.device_name = name
        self.host = host
        self.port = port
        self.schedule_store = schedule_store or Store(hass, 1, SCHEDULE_BACKUPS_STORAGE_KEY)

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

    async def async_backup_schedule(self) -> dict[str, Any]:
        """Persist the current raw auto/schedule block for this device."""

        if self.data is None or not self.data.decoded_data.get("auto"):
            await self.async_request_refresh()
        if self.data is None:
            raise ValueError("device status is unavailable")
        decoded = self.data.decoded_data or {}
        auto_hex = decoded.get("auto")
        if not auto_hex:
            raise ValueError("device status does not contain an auto schedule block")
        raw_auto = bytes.fromhex(auto_hex)
        schedule_auto_update(raw_auto)
        backup = {
            "host": self.host,
            "device_name": self.device_name,
            "serial_number": decoded.get("serial_number"),
            "backed_up_at": dt_util.utcnow().isoformat(),
            "auto": auto_hex,
            "points": decoded.get("schedule_points") or [],
            "summary": decoded.get("schedule_summary"),
        }
        backups = await self.schedule_store.async_load() or {}
        backups[self.host] = backup
        await self.schedule_store.async_save(backups)
        return backup

    async def async_restore_schedule(self) -> None:
        """Restore the last persisted raw auto/schedule block for this device."""

        backups = await self.schedule_store.async_load() or {}
        backup = backups.get(self.host)
        if not backup or not backup.get("auto"):
            raise ValueError(f"no schedule backup stored for {self.device_name}")
        raw_auto = bytes.fromhex(backup["auto"])
        self.async_set_updated_data(
            await self.hass.async_add_executor_job(control, self.host, schedule_auto_update(raw_auto), self.port)
        )

    async def async_apply_lunar_config(
        self,
        *,
        enabled: bool | None = None,
        high_channels: list[int] | tuple[int, ...] | None = None,
        low_channels: list[int] | tuple[int, ...] | None = None,
        cycle_day: int | None = None,
    ) -> None:
        """Apply known lunar configuration fields while preserving the raw extension block."""

        if self.data is None or not self.data.decoded_data.get("other"):
            await self.async_request_refresh()
        if self.data is None:
            raise ValueError("device status is unavailable")
        other_hex = (self.data.decoded_data or {}).get("other")
        if not other_hex:
            raise ValueError("device status does not contain an extension block")
        updates = lunar_other_update(
            bytes.fromhex(other_hex),
            enabled=enabled,
            high_channels=high_channels,
            low_channels=low_channels,
            cycle_day=cycle_day,
        )
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

    schedule_store = Store(hass, 1, SCHEDULE_BACKUPS_STORAGE_KEY)

    for idx, device in enumerate(devices, start=1):
        host = device[CONF_HOST]
        name = device.get(CONF_NAME) or f"Maxspect Syna-G {idx}"
        port = int(device.get("port", DEFAULT_PORT))
        coordinator = MaxspectCoordinator(hass, name, host, port, schedule_store)
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _all_coordinators(hass: HomeAssistant) -> list[MaxspectCoordinator]:
    """Return all loaded Maxspect coordinators."""

    return [coordinator for entry_coordinators in hass.data.get(DOMAIN, {}).values() for coordinator in entry_coordinators]


def _matching_coordinators(hass: HomeAssistant, device: str | None) -> list[MaxspectCoordinator]:
    """Return loaded coordinators matching an optional device name or host."""

    coordinators = _all_coordinators(hass)
    if device:
        coordinators = [
            coordinator for coordinator in coordinators if coordinator.device_name == device or coordinator.host == device
        ]
    if not coordinators:
        raise ValueError(f"no Maxspect Syna-G devices matched {device!r}")
    return coordinators


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services once."""

    if hass.services.has_service(DOMAIN, SERVICE_APPLY_MANUAL_PRESET):
        return

    async def async_apply_manual_preset(call: ServiceCall) -> None:
        device = call.data.get("device")
        values = [call.data[channel] for channel in CHANNEL_NAMES]
        coordinators = _matching_coordinators(hass, device)
        await asyncio.gather(*(coordinator.async_apply_manual_preset(values) for coordinator in coordinators))

    async def async_backup_schedule(call: ServiceCall) -> None:
        device = call.data.get("device")
        coordinators = _matching_coordinators(hass, device)
        await asyncio.gather(*(coordinator.async_backup_schedule() for coordinator in coordinators))

    async def async_restore_schedule(call: ServiceCall) -> None:
        device = call.data.get("device")
        coordinators = _matching_coordinators(hass, device)
        await asyncio.gather(*(coordinator.async_restore_schedule() for coordinator in coordinators))

    async def async_apply_lunar_config(call: ServiceCall) -> None:
        device = call.data.get("device")
        coordinators = _matching_coordinators(hass, device)
        await asyncio.gather(
            *(
                coordinator.async_apply_lunar_config(
                    enabled=call.data.get("enabled"),
                    high_channels=call.data.get("high_channels"),
                    low_channels=call.data.get("low_channels"),
                    cycle_day=call.data.get("cycle_day"),
                )
                for coordinator in coordinators
            )
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_MANUAL_PRESET,
        async_apply_manual_preset,
        schema=SERVICE_APPLY_MANUAL_PRESET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKUP_SCHEDULE,
        async_backup_schedule,
        schema=DEVICE_OPTIONAL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE_SCHEDULE,
        async_restore_schedule,
        schema=DEVICE_OPTIONAL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_LUNAR_CONFIG,
        async_apply_lunar_config,
        schema=SERVICE_APPLY_LUNAR_CONFIG_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok

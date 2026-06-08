"""Sensors for Maxspect Syna-G Local."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MaxspectCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensors."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    sensors: list[SensorEntity] = []
    for coordinator in coordinators:
        sensors.extend(
            [
                MaxspectDiagnosticSensor(coordinator, "last command", "last_command", lambda d: f"{d.last_command:04x}" if d.last_command is not None else None),
                MaxspectDiagnosticSensor(coordinator, "status payload length", "status_payload_length", lambda d: d.status_payload_length),
                MaxspectDiagnosticSensor(coordinator, "elapsed ms", "elapsed_ms", lambda d: d.elapsed_ms),
                MaxspectDiagnosticSensor(coordinator, "error", "error", lambda d: d.error or None),
                MaxspectDiagnosticSensor(coordinator, "payload preview", "payload_preview", lambda d: d.last_payload_hex or None),
            ]
        )
    async_add_entities(sensors)


class MaxspectDiagnosticSensor(CoordinatorEntity[MaxspectCoordinator], SensorEntity):
    """Diagnostic sensor for probe data."""

    _attr_entity_category = "diagnostic"

    def __init__(self, coordinator: MaxspectCoordinator, label: str, key: str, getter: Callable[[Any], Any]) -> None:
        super().__init__(coordinator)
        self._label = label
        self._key = key
        self._getter = getter
        self._attr_name = f"{coordinator.device_name} {label}"
        self._attr_unique_id = f"{coordinator.host}_{key}"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self._getter(self.coordinator.data)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

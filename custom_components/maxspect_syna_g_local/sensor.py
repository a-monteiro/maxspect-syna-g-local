"""Sensors for Maxspect Syna-G Local."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MaxspectCoordinator
from .const import DOMAIN


@dataclass(frozen=True)
class SensorDescription:
    label: str
    key: str
    getter: Callable[[Any], Any]
    icon: str | None = None
    native_unit_of_measurement: str | None = None
    entity_category: EntityCategory | None = None
    enabled_default: bool = True


def _decoded(key: str, default: Any = None) -> Callable[[Any], Any]:
    return lambda d: (d.decoded_data or {}).get(key, default)


def _channels_summary(d: Any) -> str | None:
    decoded = d.decoded_data or {}
    channels = [decoded.get(f"channel_{idx}") for idx in range(1, 7)]
    if any(value is None for value in channels):
        return None
    return ", ".join(str(value) for value in channels)


SENSORS: list[SensorDescription] = [
    SensorDescription("mode", "mode", _decoded("MODE"), icon="mdi:tune"),
    SensorDescription("channels", "channels", _channels_summary, icon="mdi:lightbulb-multiple"),
    SensorDescription("schedule", "schedule", _decoded("schedule_summary"), icon="mdi:calendar-clock"),
    SensorDescription("device time", "device_time", _decoded("device_time"), icon="mdi:clock-outline"),
    SensorDescription("serial number", "serial_number", _decoded("serial_number"), icon="mdi:identifier", entity_category=EntityCategory.DIAGNOSTIC),
    *[
        SensorDescription(
            f"channel {idx}",
            f"channel_{idx}",
            _decoded(f"channel_{idx}"),
            icon="mdi:brightness-percent",
            native_unit_of_measurement=PERCENTAGE,
        )
        for idx in range(1, 7)
    ],
    SensorDescription("special mode", "special_mode", _decoded("special_mode"), icon="mdi:star-cog", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("identification", "identification", _decoded("identification"), icon="mdi:crosshairs-question", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("temperature alert", "temperature_alert", _decoded("temperature_alert"), icon="mdi:thermometer-alert", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("password configured", "password_configured", _decoded("password_configured"), icon="mdi:form-textbox-password", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("last command", "last_command", lambda d: f"{d.last_command:04x}" if d.last_command is not None else None, entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("status payload length", "status_payload_length", lambda d: d.status_payload_length, entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("elapsed ms", "elapsed_ms", lambda d: d.elapsed_ms, native_unit_of_measurement="ms", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("error", "error", lambda d: d.error or None, icon="mdi:alert-circle", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDescription("payload preview", "payload_preview", lambda d: d.last_payload_hex or None, entity_category=EntityCategory.DIAGNOSTIC, enabled_default=False),
    SensorDescription("device time hex", "time_hex", _decoded("time_hex"), icon="mdi:code-tags", entity_category=EntityCategory.DIAGNOSTIC, enabled_default=False),
    SensorDescription("auto raw", "auto", _decoded("auto"), icon="mdi:code-json", entity_category=EntityCategory.DIAGNOSTIC, enabled_default=False),
    SensorDescription("display raw", "display", _decoded("display"), icon="mdi:code-json", entity_category=EntityCategory.DIAGNOSTIC, enabled_default=False),
    SensorDescription("quick display raw", "quick_display", _decoded("quick_display"), icon="mdi:code-json", entity_category=EntityCategory.DIAGNOSTIC, enabled_default=False),
    SensorDescription("other raw", "other", _decoded("other"), icon="mdi:code-json", entity_category=EntityCategory.DIAGNOSTIC, enabled_default=False),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up sensors."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    sensors: list[SensorEntity] = []
    for coordinator in coordinators:
        sensors.extend(MaxspectDiagnosticSensor(coordinator, description) for description in SENSORS)
    async_add_entities(sensors)


class MaxspectDiagnosticSensor(CoordinatorEntity[MaxspectCoordinator], SensorEntity):
    """State/diagnostic sensor for Maxspect probe data."""

    def __init__(self, coordinator: MaxspectCoordinator, description: SensorDescription) -> None:
        super().__init__(coordinator)
        self.description = description
        self._attr_name = f"{coordinator.device_name} {description.label}"
        self._attr_unique_id = f"{coordinator.host}_{description.key}"
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_entity_category = description.entity_category
        self._attr_entity_registry_enabled_default = description.enabled_default

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.description.getter(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        if self.description.key != "schedule" or self.coordinator.data is None:
            return None
        return {"points": (self.coordinator.data.decoded_data or {}).get("schedule_points", [])}

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

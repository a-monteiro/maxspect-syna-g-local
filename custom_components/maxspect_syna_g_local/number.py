"""Number entities for Maxspect Syna-G Local controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MaxspectCoordinator
from .const import DOMAIN
from .gagent import CHANNEL_LABELS, CHANNEL_NAMES


@dataclass(frozen=True)
class ControlNumberDescription:
    """Description for a Maxspect number entity."""

    key: str
    label: str
    value: Callable[[dict[str, Any]], int | None]
    set_value: Callable[[MaxspectCoordinator, int], Any]
    icon: str = "mdi:brightness-percent"
    native_min_value: int = 0
    native_max_value: int = 100
    native_unit_of_measurement: str | None = PERCENTAGE


def _decoded_int(key: str) -> Callable[[dict[str, Any]], int | None]:
    def getter(decoded: dict[str, Any]) -> int | None:
        value = decoded.get(key)
        return int(value) if value is not None else None

    return getter


def _lunar_list_value(key: str, index: int) -> Callable[[dict[str, Any]], int | None]:
    def getter(decoded: dict[str, Any]) -> int | None:
        values = decoded.get(key) or []
        return int(values[index]) if len(values) > index else None

    return getter


def _replace_lunar_value(values: list[int] | None, index: int, value: int) -> list[int]:
    current = list(values or [0, 0, 0])
    while len(current) < 3:
        current.append(0)
    current[index] = value
    return current[:3]


def _set_manual_channel(channel: str) -> Callable[[MaxspectCoordinator, int], Any]:
    return lambda coordinator, value: coordinator.async_set_channel(channel, value)


def _set_lunar_high(index: int) -> Callable[[MaxspectCoordinator, int], Any]:
    async def setter(coordinator: MaxspectCoordinator, value: int) -> None:
        decoded = (coordinator.data.decoded_data if coordinator.data else {}) or {}
        await coordinator.async_apply_lunar_config(
            high_channels=_replace_lunar_value(decoded.get("lunar_high_channels"), index, value)
        )

    return setter


def _set_lunar_low(index: int) -> Callable[[MaxspectCoordinator, int], Any]:
    async def setter(coordinator: MaxspectCoordinator, value: int) -> None:
        decoded = (coordinator.data.decoded_data if coordinator.data else {}) or {}
        await coordinator.async_apply_lunar_config(
            low_channels=_replace_lunar_value(decoded.get("lunar_low_channels"), index, value)
        )

    return setter


NUMBERS: tuple[ControlNumberDescription, ...] = (
    *(
        ControlNumberDescription(
            key=f"{name}_manual_level",
            label=f"{CHANNEL_LABELS[name]} channel",
            value=_decoded_int(name),
            set_value=_set_manual_channel(name),
        )
        for name in CHANNEL_NAMES
    ),
    *(
        ControlNumberDescription(
            key=f"lunar_high_{idx + 1}",
            label=f"Lunar high {label}",
            value=_lunar_list_value("lunar_high_channels", idx),
            set_value=_set_lunar_high(idx),
            icon="mdi:brightness-7",
        )
        for idx, label in enumerate(("blue", "white", "moon"))
    ),
    *(
        ControlNumberDescription(
            key=f"lunar_low_{idx + 1}",
            label=f"Lunar low {label}",
            value=_lunar_list_value("lunar_low_channels", idx),
            set_value=_set_lunar_low(idx),
            icon="mdi:brightness-2",
        )
        for idx, label in enumerate(("blue", "white", "moon"))
    ),
    ControlNumberDescription(
        key="lunar_cycle_day",
        label="Lunar cycle day",
        value=_decoded_int("lunar_cycle_day"),
        set_value=lambda coordinator, value: coordinator.async_apply_lunar_config(cycle_day=value),
        icon="mdi:moon-waning-crescent",
        native_max_value=29,
        native_unit_of_measurement=None,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up number entities."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    numbers: list[NumberEntity] = []
    for coordinator in coordinators:
        numbers.extend(MaxspectControlNumber(coordinator, description) for description in NUMBERS)
    async_add_entities(numbers)


class MaxspectControlNumber(CoordinatorEntity[MaxspectCoordinator], NumberEntity):
    """Number control for one Maxspect light setting."""

    _attr_native_step = 1

    def __init__(self, coordinator: MaxspectCoordinator, description: ControlNumberDescription) -> None:
        super().__init__(coordinator)
        self.description = description
        self._attr_name = f"{coordinator.device_name} {description.label}"
        self._attr_unique_id = f"{coordinator.host}_{description.key}"
        self._attr_icon = description.icon
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.description.value(self.coordinator.data.decoded_data or {})

    async def async_set_native_value(self, value: float) -> None:
        """Set this numeric control."""

        await self.description.set_value(self.coordinator, round(value))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

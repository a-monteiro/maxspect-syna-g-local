"""Number entities for Maxspect Syna-G Local manual channel controls."""

from __future__ import annotations

from dataclasses import dataclass

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
class ChannelNumberDescription:
    """Description for a manual channel number entity."""

    channel: str
    label: str


CHANNEL_NUMBERS: tuple[ChannelNumberDescription, ...] = tuple(
    ChannelNumberDescription(channel=name, label=CHANNEL_LABELS[name]) for name in CHANNEL_NAMES
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up manual channel number entities."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    numbers: list[NumberEntity] = []
    for coordinator in coordinators:
        numbers.extend(MaxspectChannelNumber(coordinator, description) for description in CHANNEL_NUMBERS)
    async_add_entities(numbers)


class MaxspectChannelNumber(CoordinatorEntity[MaxspectCoordinator], NumberEntity):
    """Manual brightness control for one Maxspect light channel."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:brightness-percent"

    def __init__(self, coordinator: MaxspectCoordinator, description: ChannelNumberDescription) -> None:
        super().__init__(coordinator)
        self.description = description
        self._attr_name = f"{coordinator.device_name} {description.label} channel"
        self._attr_unique_id = f"{coordinator.host}_{description.channel}_manual_level"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        value = (self.coordinator.data.decoded_data or {}).get(self.description.channel)
        return int(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set this channel's manual brightness percentage."""

        await self.coordinator.async_set_channel(self.description.channel, round(value))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

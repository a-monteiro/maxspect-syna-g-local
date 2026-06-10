"""Switch entities for Maxspect Syna-G Local lunar controls."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MaxspectCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up lunar switches."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MaxspectLunarEnabledSwitch(coordinator) for coordinator in coordinators)


class MaxspectLunarEnabledSwitch(CoordinatorEntity[MaxspectCoordinator], SwitchEntity):
    """Enable/disable the known lunar cycle flag."""

    _attr_icon = "mdi:moon-full"

    def __init__(self, coordinator: MaxspectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.device_name} Lunar enabled"
        self._attr_unique_id = f"{coordinator.host}_lunar_enabled_switch"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None:
            return None
        value = (self.coordinator.data.decoded_data or {}).get("lunar_enabled")
        return bool(value) if value is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        """Enable lunar cycle output."""

        await self.coordinator.async_apply_lunar_config(enabled=True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable lunar cycle output."""

        await self.coordinator.async_apply_lunar_config(enabled=False)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

"""Select entities for Maxspect Syna-G Local spectrum presets."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MaxspectCoordinator
from .const import DOMAIN
from .gagent import SPECTRUM_PRESET_OPTIONS

SPECTRUM_OPTIONS = list(SPECTRUM_PRESET_OPTIONS.keys())


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up spectrum preset selects."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MaxspectSpectrumPresetSelect(coordinator) for coordinator in coordinators)


class MaxspectSpectrumPresetSelect(CoordinatorEntity[MaxspectCoordinator], SelectEntity):
    """Apply APK-derived R6 spectrum/CCT presets."""

    _attr_icon = "mdi:palette"
    _attr_options = SPECTRUM_OPTIONS

    def __init__(self, coordinator: MaxspectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = f"{coordinator.device_name} Spectrum preset"
        self._attr_unique_id = f"{coordinator.host}_spectrum_preset"
        self._current_option: str | None = None

    @property
    def current_option(self) -> str | None:
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        """Apply the selected spectrum preset."""

        if option not in SPECTRUM_OPTIONS:
            raise ValueError(f"unknown spectrum preset {option}")
        await self.coordinator.async_apply_spectrum_preset(option)
        self._current_option = option

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

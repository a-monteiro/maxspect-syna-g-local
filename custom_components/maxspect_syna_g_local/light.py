"""Light entities for Maxspect Syna-G Local."""

from __future__ import annotations

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MaxspectCoordinator
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up light entities."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MaxspectSynaGLight(coordinator) for coordinator in coordinators)


class MaxspectSynaGLight(CoordinatorEntity[MaxspectCoordinator], LightEntity):
    """Guarded on/off facade for a Maxspect Syna-G light."""

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(self, coordinator: MaxspectCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = coordinator.device_name
        self._attr_unique_id = f"{coordinator.host}_light"

    @property
    def is_on(self) -> bool | None:
        if self.coordinator.data is None or not self.coordinator.data.online:
            return None
        decoded = self.coordinator.data.decoded_data or {}
        mode = decoded.get("MODE")
        if mode == 1:
            # Auto mode includes the controller's lunar/night cycle even when
            # raw channel datapoints do not mirror the actual dim moon output.
            return True
        return any(int(decoded.get(f"channel_{idx}") or 0) > 0 for idx in range(1, 7))

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return None
        decoded = self.coordinator.data.decoded_data or {}
        return {
            "mode": decoded.get("MODE"),
            "lighting_phase": decoded.get("lighting_phase"),
            "channels": {f"channel_{idx}": decoded.get(f"channel_{idx}") for idx in range(1, 7)},
            "channel_labels": decoded.get("channel_labels"),
            "channels_labeled_summary": decoded.get("channels_labeled_summary"),
            "schedule_summary": decoded.get("schedule_summary"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Resume the stored automatic/lunar schedule."""

        await self.coordinator.async_resume_auto()

    async def async_turn_off(self, **kwargs) -> None:
        """Set all six manual channel outputs to zero."""

        await self.coordinator.async_turn_channels_off()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

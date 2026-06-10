"""Buttons for explicit Maxspect Syna-G Local control actions."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MaxspectCoordinator
from .const import DOMAIN


@dataclass(frozen=True)
class ButtonDescription:
    """Description for an explicit Maxspect control button."""

    label: str
    key: str
    icon: str
    press: Callable[[MaxspectCoordinator], Coroutine[Any, Any, None]]
    entity_category: EntityCategory | None = EntityCategory.CONFIG


BUTTONS: tuple[ButtonDescription, ...] = (
    ButtonDescription(
        label="resume automatic schedule",
        key="resume_auto",
        icon="mdi:calendar-sync",
        press=lambda coordinator: coordinator.async_resume_auto(),
    ),
    ButtonDescription(
        label="manual all channels off",
        key="manual_all_channels_off",
        icon="mdi:lightbulb-off-outline",
        press=lambda coordinator: coordinator.async_turn_channels_off(),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up explicit control buttons."""

    coordinators: list[MaxspectCoordinator] = hass.data[DOMAIN][entry.entry_id]
    buttons: list[ButtonEntity] = []
    for coordinator in coordinators:
        buttons.extend(MaxspectControlButton(coordinator, description) for description in BUTTONS)
    async_add_entities(buttons)


class MaxspectControlButton(CoordinatorEntity[MaxspectCoordinator], ButtonEntity):
    """Explicit action button for a Maxspect Syna-G light."""

    def __init__(self, coordinator: MaxspectCoordinator, description: ButtonDescription) -> None:
        super().__init__(coordinator)
        self.description = description
        self._attr_name = f"{coordinator.device_name} {description.label}"
        self._attr_unique_id = f"{coordinator.host}_{description.key}"
        self._attr_icon = description.icon
        self._attr_entity_category = description.entity_category

    async def async_press(self) -> None:
        """Run the explicit control action."""

        await self.description.press(self.coordinator)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.host)},
            "name": self.coordinator.device_name,
            "manufacturer": "Maxspect",
            "model": "Syna-G / Jump (Gizwits local)",
        }

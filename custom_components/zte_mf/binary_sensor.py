"""Binary sensors for the ZTE MF LTE modem integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import MODEM_STATES_ONLINE, PPP_STATE_CONNECTED
from .coordinator import ZteMfConfigEntry, ZteMfCoordinator
from .entity import ZteMfEntity


@dataclass(frozen=True, kw_only=True)
class ZteMfBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one binary sensor and how to read it out of a poll result."""

    field: str
    is_on_fn: Callable[[str], bool]


BINARY_SENSORS: tuple[ZteMfBinarySensorDescription, ...] = (
    ZteMfBinarySensorDescription(
        key="connection",
        translation_key="connection",
        field="ppp_status",
        is_on_fn=lambda raw: raw == PPP_STATE_CONNECTED,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    ZteMfBinarySensorDescription(
        key="registered",
        translation_key="registered",
        field="modem_main_state",
        is_on_fn=lambda raw: raw in MODEM_STATES_ONLINE,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZteMfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the modem's binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(ZteMfBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class ZteMfBinarySensor(ZteMfEntity, BinarySensorEntity):
    """One yes/no reading from the modem."""

    entity_description: ZteMfBinarySensorDescription

    def __init__(
        self, coordinator: ZteMfCoordinator, description: ZteMfBinarySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the state, or None while the modem reports nothing at all."""
        raw = self._raw(self.entity_description.field)
        if not raw:
            return None
        return self.entity_description.is_on_fn(raw)

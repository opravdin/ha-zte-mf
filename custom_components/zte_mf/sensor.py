"""Sensors for the ZTE MF LTE modem integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import ipaddress
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ZteMfConfigEntry, ZteMfCoordinator
from .entity import ZteMfEntity


@dataclass(frozen=True, kw_only=True)
class ZteMfSensorDescription(SensorEntityDescription):
    """Describes one sensor and how to read it out of a poll result."""

    field: str
    value_fn: Callable[[str], Any] = lambda raw: raw
    attrs_fn: Callable[[str], dict[str, Any]] | None = None


def _to_int(raw: str) -> int | None:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def _to_float(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _ip_attrs(raw: str) -> dict[str, Any]:
    """Flag a carrier-grade NAT address.

    Worth surfacing: on a CGNAT address no port forward and no inbound
    connection can ever work, and the uplink is usually policed as well. That
    turns "why can I not reach home" from a guess into a visible fact.
    """
    try:
        addr = ipaddress.ip_address(raw)
    except ValueError:
        return {}
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    return {
        "is_private": addr.is_private,
        "is_cgnat": addr in cgnat or addr.is_private,
    }


SENSORS: tuple[ZteMfSensorDescription, ...] = (
    ZteMfSensorDescription(
        key="rsrp",
        translation_key="rsrp",
        field="lte_rsrp",
        value_fn=_to_int,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZteMfSensorDescription(
        key="rsrq",
        translation_key="rsrq",
        field="lte_rsrq",
        value_fn=_to_int,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZteMfSensorDescription(
        key="sinr",
        translation_key="sinr",
        field="lte_snr",
        value_fn=_to_float,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZteMfSensorDescription(
        key="rssi",
        translation_key="rssi",
        field="rssi",
        value_fn=_to_int,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZteMfSensorDescription(
        key="signal_bars",
        translation_key="signal_bars",
        field="signalbar",
        value_fn=_to_int,
        icon="mdi:signal",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ZteMfSensorDescription(
        key="band",
        translation_key="band",
        field="wan_active_band",
        icon="mdi:radio-tower",
    ),
    ZteMfSensorDescription(
        key="network_type",
        translation_key="network_type",
        field="network_type",
        icon="mdi:network",
    ),
    ZteMfSensorDescription(
        key="provider",
        translation_key="provider",
        field="network_provider",
        icon="mdi:domain",
    ),
    ZteMfSensorDescription(
        key="modem_state",
        translation_key="modem_state",
        field="modem_main_state",
        icon="mdi:cellphone-wireless",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZteMfSensorDescription(
        key="wan_ip",
        translation_key="wan_ip",
        field="wan_ipaddr",
        icon="mdi:ip-network",
        attrs_fn=_ip_attrs,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZteMfSensorDescription(
        key="realtime_tx",
        translation_key="realtime_tx",
        field="realtime_tx_thrpt",
        value_fn=_to_int,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ZteMfSensorDescription(
        key="realtime_rx",
        translation_key="realtime_rx",
        field="realtime_rx_thrpt",
        value_fn=_to_int,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ZteMfSensorDescription(
        key="monthly_tx",
        translation_key="monthly_tx",
        field="monthly_tx_bytes",
        value_fn=_to_int,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ZteMfSensorDescription(
        key="monthly_rx",
        translation_key="monthly_rx",
        field="monthly_rx_bytes",
        value_fn=_to_int,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ZteMfSensorDescription(
        key="total_tx",
        translation_key="total_tx",
        field="total_tx_bytes",
        value_fn=_to_int,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZteMfSensorDescription(
        key="total_rx",
        translation_key="total_rx",
        field="total_rx_bytes",
        value_fn=_to_int,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZteMfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the modem's sensors."""
    coordinator = entry.runtime_data
    async_add_entities(ZteMfSensor(coordinator, desc) for desc in SENSORS)


class ZteMfSensor(ZteMfEntity, SensorEntity):
    """One reading from the modem."""

    entity_description: ZteMfSensorDescription

    def __init__(
        self, coordinator: ZteMfCoordinator, description: ZteMfSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the reading, or None when the modem sent an empty field."""
        raw = self._raw(self.entity_description.field)
        if not raw:
            return None
        return self.entity_description.value_fn(raw)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return derived detail, where a description asks for it."""
        if (attrs_fn := self.entity_description.attrs_fn) is None:
            return None
        raw = self._raw(self.entity_description.field)
        return attrs_fn(raw) if raw else None

"""Shared entity base for the ZTE MF LTE modem integration."""

from __future__ import annotations

import re

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZteMfCoordinator

# Firmware strings look like "MF823_GENERAL_V1.0.0B05" — the leading token is
# the only place the model name appears anywhere in the API.
_RE_MODEL = re.compile(r"\b(MF\w+?)(?:[_-]|\b)")


class ZteMfEntity(CoordinatorEntity[ZteMfCoordinator]):
    """Common device wiring for every entity of one modem."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZteMfCoordinator, key: str) -> None:
        super().__init__(coordinator)
        raw = coordinator.device_info_raw
        identity = raw.get("modem_imei") or coordinator.client.host

        self._attr_unique_id = f"{identity}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            manufacturer="ZTE",
            model=_model_from(raw.get("wa_inner_version") or raw.get("cr_version")),
            name="ZTE LTE modem",
            sw_version=raw.get("wa_inner_version") or None,
            hw_version=raw.get("hardware_version") or None,
            configuration_url=f"http://{coordinator.client.host}/",
            serial_number=raw.get("modem_imei") or None,
        )

    @property
    def available(self) -> bool:
        """Report unavailable when the last poll failed outright."""
        return self.coordinator.last_update_success

    def _raw(self, field: str) -> str:
        """Return a field with the modem's padding stripped."""
        return str((self.coordinator.data or {}).get(field, "")).strip()


def _model_from(firmware: str | None) -> str:
    """Best-effort model name; the API never states it outright."""
    if firmware and (match := _RE_MODEL.search(firmware)):
        return match.group(1)
    return "MF series"

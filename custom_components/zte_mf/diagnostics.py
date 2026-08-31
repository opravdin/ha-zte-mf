"""Diagnostics support for the ZTE MF LTE modem integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import ZteMfConfigEntry

# The modem's IMEI, MSISDN and public address identify a person's SIM and line,
# so they are stripped from anything meant to be pasted into a bug report.
TO_REDACT = {
    CONF_PASSWORD,
    "modem_imei",
    "msisdn",
    "wan_ipaddr",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZteMfConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "device": async_redact_data(coordinator.device_info_raw, TO_REDACT),
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
    }

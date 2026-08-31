"""Polling coordinator for the ZTE MF LTE modem integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    ZteMfAuthError,
    ZteMfClient,
    ZteMfConnectionError,
    ZteMfError,
    ZteMfLockedError,
)
from .const import DEVICE_FIELDS, DOMAIN, POLL_FIELDS

_LOGGER = logging.getLogger(__name__)

# If these come back blank the answer is not "the modem has no signal" but
# "nobody is logged in": an anonymous request returns every key present and
# empty. Picking radio and traffic together avoids mistaking a genuinely
# detached modem for a dropped session.
_SESSION_WITNESS_FIELDS = ("lte_rsrp", "monthly_rx_bytes")

type ZteMfConfigEntry = ConfigEntry["ZteMfCoordinator"]


class ZteMfCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Keeps one modem's readings fresh and its single session alive."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZteMfConfigEntry,
        client: ZteMfClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {client.host}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.client = client
        self.device_info_raw: dict[str, str] = {}

    async def async_load_device_info(self) -> None:
        """Read the identity fields once, for the device registry entry."""
        try:
            self.device_info_raw = await self.client.async_get(DEVICE_FIELDS)
        except ZteMfError as err:
            _LOGGER.debug("could not read device identity: %s", err)
            self.device_info_raw = {}

    async def _async_update_data(self) -> dict[str, str]:
        try:
            data = await self.client.async_get(POLL_FIELDS)

            # Blank readings mean either the session expired or the modem really
            # is detached. One cheap probe tells which, and only the first case
            # is ours to fix — re-logging in on a detached modem would spend
            # login attempts to no purpose.
            if _looks_anonymous(data) and not await self.client.async_is_logged_in():
                _LOGGER.debug("session gone, logging back in")
                await self.client.async_login()
                data = await self.client.async_get(POLL_FIELDS)

        except ZteMfAuthError as err:
            # Surfaces in the UI as "reconfigure", which is right: nothing this
            # integration does on its own will make a wrong password work.
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZteMfLockedError as err:
            raise UpdateFailed(
                f"modem locked out logins for another {err.seconds_left}s"
            ) from err
        except ZteMfConnectionError as err:
            raise UpdateFailed(str(err)) from err

        return {key: str(value) for key, value in data.items()}


def _looks_anonymous(data: dict[str, str]) -> bool:
    """Return whether the answer carries none of the session-only fields."""
    return all(
        not str(data.get(field, "")).strip() for field in _SESSION_WITNESS_FIELDS
    )

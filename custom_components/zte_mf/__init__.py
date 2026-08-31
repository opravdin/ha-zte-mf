"""The ZTE MF LTE modem integration."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    ZteMfAuthError,
    ZteMfClient,
    ZteMfError,
    ZteMfUnsupportedError,
)
from .const import DEFAULT_SCAN_INTERVAL
from .coordinator import ZteMfConfigEntry, ZteMfCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ZteMfConfigEntry) -> bool:
    """Set up one modem from a config entry."""
    # A private cookie jar, and an unsafe one at that: aiohttp discards cookies
    # from hosts addressed by bare IP unless told otherwise, and this modem is
    # only ever reachable as 192.168.0.1. Without unsafe=True the stok cookie is
    # silently dropped and every reading comes back empty.
    #
    # auto_cleanup=False because this entry owns the session and closes it on
    # unload. Left to Home Assistant's cleanup the session would only be closed
    # at shutdown, so every reload of this entry would leak one.
    session = async_create_clientsession(
        hass,
        verify_ssl=False,
        auto_cleanup=False,
        cookie_jar=aiohttp.CookieJar(unsafe=True),
    )

    client = ZteMfClient(
        session,
        entry.data[CONF_HOST],
        entry.data[CONF_PASSWORD],
    )

    try:
        await client.async_assert_supported()
        await client.async_login()
    except ZteMfAuthError as err:
        await session.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except ZteMfUnsupportedError as err:
        # Retrying cannot help: the firmware speaks a scheme this client does
        # not implement. Say so once rather than looping on ConfigEntryNotReady.
        await session.close()
        raise ConfigEntryAuthFailed(str(err)) from err
    except ZteMfError as err:
        # Covers the busy and locked cases too: both clear up on their own,
        # so the right answer is to let Home Assistant retry the setup.
        await session.close()
        raise ConfigEntryNotReady(str(err)) from err

    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    coordinator = ZteMfCoordinator(hass, entry, client, scan_interval)
    coordinator.session = session
    await coordinator.async_load_device_info()
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await session.close()
        raise

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZteMfConfigEntry) -> bool:
    """Tear down a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and (session := entry.runtime_data.session) is not None:
        await session.close()
    return unloaded


async def _async_options_updated(hass: HomeAssistant, entry: ZteMfConfigEntry) -> None:
    """Apply a changed poll interval by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)

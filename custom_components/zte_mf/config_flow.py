"""Config flow for the ZTE MF LTE modem integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import voluptuous as vol

from .api import (
    ZteMfAuthError,
    ZteMfClient,
    ZteMfConnectionError,
    ZteMfLockedError,
    ZteMfUnsupportedError,
)
from .const import DEFAULT_HOST, DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def _async_probe(hass, host: str, password: str) -> dict[str, str]:
    """Log in once and return the modem's identity fields.

    Deliberately a full login rather than a reachability check: on this hardware
    a wrong password is the failure that matters, and it is better discovered
    here than as a config entry that never loads.
    """
    session = async_create_clientsession(
        hass, verify_ssl=False, cookie_jar=aiohttp.CookieJar(unsafe=True)
    )
    client = ZteMfClient(session, host, password)
    try:
        await client.async_assert_supported()
        await client.async_login()
        return await client.async_get(("modem_imei", "wa_inner_version"))
    finally:
        await session.close()


class ZteMfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setting up one modem."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the modem address and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                info = await _async_probe(self.hass, host, user_input[CONF_PASSWORD])
            except ZteMfAuthError:
                errors["base"] = "invalid_auth"
            except ZteMfLockedError:
                errors["base"] = "locked"
            except ZteMfUnsupportedError:
                errors["base"] = "unsupported_firmware"
            except ZteMfConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("unexpected error probing %s", host)
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.get("modem_imei") or host)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=f"ZTE modem ({host})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start over when the stored password stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password only."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await _async_probe(
                    self.hass, entry.data[CONF_HOST], user_input[CONF_PASSWORD]
                )
            except ZteMfAuthError:
                errors["base"] = "invalid_auth"
            except ZteMfLockedError:
                errors["base"] = "locked"
            except ZteMfConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("unexpected error during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_REAUTH_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options handler."""
        return ZteMfOptionsFlow()


class ZteMfOptionsFlow(OptionsFlow):
    """Let the poll interval be tuned after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and store the poll interval."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

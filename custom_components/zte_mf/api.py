"""Minimal async client for the ZTE MF-series goform web API.

The modem exposes a tiny CGI ("goform") that answers JSON. Two things about it
shape this whole module:

* Reading anything interesting requires a session. Without the ``stok`` cookie
  the modem still answers 200 with every field present but empty, so a missing
  session looks exactly like a healthy modem with no signal. Emptiness is
  therefore treated as "session lost", not as data.
* The modem keeps a single session and counts failed logins, locking itself for
  a while after a few. So the client logs in as rarely as it can get away with,
  and refuses to guess: a wrong password raises instead of being retried.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from typing import Any

import aiohttp

from .const import (
    FIELD_ATTEMPTS_LEFT,
    FIELD_LOGIN_STATE,
    FIELD_SESSION_TTL,
    LOGIN_RESULT_BAD_PASSWORD,
    LOGIN_RESULT_DUPLICATE,
    LOGIN_RESULT_FAIL,
    LOGIN_RESULTS_OK,
    URL_CONFIG_JS,
    URL_GET,
    URL_REFERER,
    URL_SET,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=15)

# config.js advertises which password encoding the firmware expects. Matching on
# it beforehand is cheaper than finding out by spending one of the few login
# attempts the modem grants.
_RE_ENCODE_NEW = re.compile(r"PASSWORD_ENCODE_NEW\s*:\s*(true|false)", re.IGNORECASE)
_RE_ENCODE = re.compile(r"PASSWORD_ENCODE\s*:\s*(true|false)", re.IGNORECASE)


class ZteMfError(Exception):
    """Base error for this integration."""


class ZteMfConnectionError(ZteMfError):
    """The modem could not be reached or answered something unparsable."""


class ZteMfAuthError(ZteMfError):
    """The modem rejected the password."""


class ZteMfLockedError(ZteMfError):
    """The modem has run out of login attempts and stopped accepting them."""


class ZteMfBusyError(ZteMfError):
    """Another client holds the modem's single session."""


class ZteMfUnsupportedError(ZteMfError):
    """The firmware expects a password encoding this client does not implement."""


class ZteMfClient:
    """Talks to one modem."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, password: str
    ) -> None:
        self._session = session
        self._host = host
        self._password = password
        self._referer = URL_REFERER.format(host=host)
        self._url_get = URL_GET.format(host=host)
        self._url_set = URL_SET.format(host=host)
        # One in-flight login at a time: several entities refreshing at once must
        # not each decide the session is gone and race three logins into a lockout.
        self._login_lock = asyncio.Lock()

    @property
    def host(self) -> str:
        """Return the modem address."""
        return self._host

    async def async_get(self, fields: tuple[str, ...] | list[str]) -> dict[str, str]:
        """Fetch a set of fields. Values may be empty strings; callers judge that."""
        params = {
            "isTest": "false",
            "multi_data": "1",
            "cmd": ",".join(fields),
        }
        return await self._request_json(self._url_get, params=params)

    async def async_get_one(self, field: str) -> str:
        """Fetch a single field, returning an empty string when absent."""
        params = {"isTest": "false", "cmd": field}
        data = await self._request_json(self._url_get, params=params)
        return str(data.get(field, ""))

    async def async_is_logged_in(self) -> bool:
        """Return whether the current cookie still buys us a session."""
        return await self.async_get_one(FIELD_LOGIN_STATE) == "ok"

    async def async_session_state(self) -> tuple[int, int]:
        """Return (login attempts left, seconds left on the current session).

        Both numbers come from fields whose names mislead; see const.py. The
        session TTL is reported as -1 when there is no session, normalised to 0
        here so callers can treat it as "no time left".
        """
        data = await self.async_get([FIELD_ATTEMPTS_LEFT, FIELD_SESSION_TTL])
        return (
            _as_int(data.get(FIELD_ATTEMPTS_LEFT), 5),
            max(0, _as_int(data.get(FIELD_SESSION_TTL), 0)),
        )

    async def async_login(self) -> None:
        """Establish a session, refusing to burn attempts on a hopeless password."""
        async with self._login_lock:
            attempts_left, _ = await self.async_session_state()
            if attempts_left <= 0:
                raise ZteMfLockedError("modem has no login attempts left")

            payload = {
                "isTest": "false",
                "goformId": "LOGIN",
                "password": base64.b64encode(self._password.encode()).decode(),
            }
            data = await self._request_json(self._url_set, data=payload)
            result = str(data.get("result", ""))

            if result in LOGIN_RESULTS_OK:
                _LOGGER.debug("logged in to %s (result %s)", self._host, result)
                return
            if result == LOGIN_RESULT_DUPLICATE:
                # Someone opened the modem's web UI. It keeps one session, so
                # this is a "come back later", not a credentials problem.
                raise ZteMfBusyError("another client holds the modem session")
            if result in (LOGIN_RESULT_BAD_PASSWORD, LOGIN_RESULT_FAIL):
                raise ZteMfAuthError("modem rejected the password")
            raise ZteMfAuthError(f"unexpected login result {result!r}")

    async def async_assert_supported(self) -> None:
        """Check the firmware wants base64 passwords before we try to log in.

        Newer ZTE firmware hashes the password with a server-supplied challenge.
        Sending base64 to such a modem is not merely wrong, it costs one of the
        few login attempts available, so bail out with a clear error instead.
        """
        try:
            async with self._session.get(
                URL_CONFIG_JS.format(host=self._host),
                headers={"Referer": self._referer},
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status != 200:
                    return
                body = await resp.text(errors="replace")
        except (aiohttp.ClientError, TimeoutError):
            # config.js is a nicety. If it cannot be read, carry on and let the
            # login itself be the judge.
            return

        match_new = _RE_ENCODE_NEW.search(body)
        if match_new and match_new.group(1).lower() == "true":
            raise ZteMfUnsupportedError(
                "firmware uses the newer hashed password scheme"
            )
        match_plain = _RE_ENCODE.search(body)
        if match_plain and match_plain.group(1).lower() == "false":
            raise ZteMfUnsupportedError("firmware expects an unencoded password")

    async def _request_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {"Referer": self._referer}
        try:
            if data is None:
                ctx = self._session.get(
                    url, params=params, headers=headers, timeout=_TIMEOUT
                )
            else:
                ctx = self._session.post(
                    url, data=data, headers=headers, timeout=_TIMEOUT
                )
            async with ctx as resp:
                if resp.status != 200:
                    raise ZteMfConnectionError(f"HTTP {resp.status} from {url}")
                # The modem labels JSON as text/html, so the content type check
                # has to be switched off rather than worked around downstream.
                payload = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ZteMfConnectionError(f"cannot reach {self._host}: {err}") from err
        except ValueError as err:
            raise ZteMfConnectionError(f"malformed answer from {self._host}") from err

        if not isinstance(payload, dict):
            raise ZteMfConnectionError(f"unexpected answer shape from {self._host}")
        return payload


def _as_int(value: Any, default: int) -> int:
    """Parse the modem's stringly-typed numbers without raising."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default

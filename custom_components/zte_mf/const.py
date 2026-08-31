"""Constants for the ZTE MF LTE modem integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "zte_mf"

CONF_VERIFY_FIELDS: Final = "verify_fields"

DEFAULT_HOST: Final = "192.168.0.1"
DEFAULT_SCAN_INTERVAL: Final = 60
MIN_SCAN_INTERVAL: Final = 15

# The modem answers on plain HTTP only; there is no TLS on this hardware.
URL_GET: Final = "http://{host}/goform/goform_get_cmd_process"
URL_SET: Final = "http://{host}/goform/goform_set_cmd_process"
URL_REFERER: Final = "http://{host}/index.html"
URL_CONFIG_JS: Final = "http://{host}/js/config/config.js"

# Fields polled on every update. Keep this list in sync with SENSORS/BINARY_SENSORS:
# the modem returns exactly what is asked for, so a field missing here silently
# turns its entity into "unknown".
#
# The lte_ prefix is not cosmetic. On MF823 firmware the bare "rsrp"/"rsrq" keys
# exist but are always empty, while "lte_rsrp"/"lte_rsrq" carry the real values.
# Asking for both and picking whichever is non-empty would look defensive but
# would in fact hide a firmware mismatch behind a plausible-looking number.
POLL_FIELDS: Final[tuple[str, ...]] = (
    "lte_rsrp",
    "lte_rsrq",
    "lte_snr",
    "rssi",
    "wan_active_band",
    "network_type",
    "network_provider",
    "signalbar",
    "modem_main_state",
    "ppp_status",
    "wan_ipaddr",
    "realtime_tx_thrpt",
    "realtime_rx_thrpt",
    "monthly_tx_bytes",
    "monthly_rx_bytes",
    "total_tx_bytes",
    "total_rx_bytes",
)

# Read once at setup for the device registry entry.
DEVICE_FIELDS: Final[tuple[str, ...]] = (
    "modem_imei",
    "wa_inner_version",
    "cr_version",
    "hardware_version",
    "msisdn",
)

# Cheap "is my session still alive" probe: one field, answers "ok" or "no".
FIELD_LOGIN_STATE: Final = "loginfo"

# Lockout bookkeeping. The modem allows a handful of failed logins and then
# refuses to talk for a while; login_lock_time counts the remaining seconds
# and is -1 when nothing is locked.
FIELD_FAIL_COUNT: Final = "psw_fail_num_str"
FIELD_LOCK_TIME: Final = "login_lock_time"

# goform_set_cmd_process returns a bare {"result": "..."} for LOGIN.
LOGIN_RESULT_OK: Final = "0"
LOGIN_RESULT_WRONG_PASSWORD: Final = "3"
LOGIN_RESULT_LOCKED: Final = "4"

# States of modem_main_state that mean "radio is up and attached".
MODEM_STATES_ONLINE: Final = frozenset(
    {"modem_init_complete", "modem_online", "modem_registered"}
)

PPP_STATE_CONNECTED: Final = "ppp_connected"

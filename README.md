# ZTE MF LTE modem — Home Assistant integration

Signal quality and traffic counters from ZTE MF-series LTE modems (the small USB
sticks and MiFi boxes with the old `goform` web interface), as local-polling
Home Assistant entities.

[![Validate](https://github.com/opravdin/ha-zte-mf/actions/workflows/validate.yml/badge.svg)](https://github.com/opravdin/ha-zte-mf/actions/workflows/validate.yml)

## Why this exists

There are several ZTE integrations for Home Assistant already, and none of them
fit this hardware. `Kajkac/ZTE-MC-Home-assistant-repo`, `rosenrot00/ha-zte-ng-router`
and friends target the modern 5G CPE units (MC801A, MC888, G5), which
authenticate with a SHA-256 challenge (`LD`/`RD`/`AD`). The MF-series sticks are
a decade older: they send the password as plain base64 and hand back a `stok`
session cookie. The code has nothing in common, so this is a separate
integration rather than a patch to one of those.

A plain `rest:` sensor does not work either, which is the other reason this
exists. Without a session the modem still answers `200 OK` with **every field
present and empty** — a dropped session is indistinguishable from a modem with
no signal unless something keeps the session alive and knows the difference.
That logic is the substance of this integration.

## Supported devices

| Model | Status |
| --- | --- |
| **MF823** | Verified — developed against firmware reporting `WebServer-Webs/2.5.0` |
| MF831, MF910, MF920, other `goform` MF units | Expected to work, **untested** |
| MC801A, MC888, MC889, G5 series | **Not supported** — different login scheme, use [ZTE-MC-Home-assistant-repo](https://github.com/Kajkac/ZTE-MC-Home-assistant-repo) |
| F6640, F6600P and other fibre routers | **Not supported** — use [zte_tracker](https://github.com/juacas/zte_tracker) |

If your firmware announces `PASSWORD_ENCODE_NEW: true` in `/js/config/config.js`,
setup stops with a clear error instead of guessing. That check is deliberate:
the modem locks logins after a handful of failures, so a wrong guess is
expensive.

## Entities

**Sensors** — RSRP, RSRQ, SINR, RSSI, signal bars, band, network type, provider,
modem state, WAN IP, realtime upload/download rate, monthly upload/download,
lifetime upload/download.

**Binary sensors** — connection (`ppp_status`), registered (`modem_main_state`).

Two details worth knowing:

* **SINR comes from `lte_snr`.** There is no `lte_sinr` field on this hardware;
  the modem's own web UI relabels `lte_snr` as SINR, and so does this
  integration.
* **The WAN IP sensor carries an `is_cgnat` attribute.** On a carrier-grade NAT
  address no port forward and no inbound connection will ever work, and the
  uplink is usually policed as well. Having that visible as a fact saves a lot
  of guessing.

## Installation

### HACS

1. HACS → three-dot menu → **Custom repositories**
2. Repository `https://github.com/opravdin/ha-zte-mf`, category **Integration**
3. Install, restart Home Assistant
4. **Settings → Devices & services → Add integration → ZTE MF LTE modem**

### Manual

Copy `custom_components/zte_mf` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

Address (default `192.168.0.1`) and the modem's web password. The poll interval
is under **Configure** after setup; the default is 60 seconds and the minimum is
15.

## Things this hardware does that will surprise you

**One session at a time.** Logging in from Home Assistant can sign you out of
the modem's web UI, and signing in to the web UI can drop Home Assistant's
session. The integration handles the second case — it notices the empty answers,
verifies with a cheap `loginfo` probe and logs back in — but expect the web UI to
kick you out while Home Assistant is polling.

**Failed logins lock the modem.** The firmware counts wrong passwords and then
refuses to talk for a while. This integration checks `login_lock_time` before
every login attempt, never retries a rejected password, and raises a
re-authentication prompt instead of hammering the device.

**Cookies from a bare IP address.** `aiohttp` discards cookies set by hosts
addressed by IP unless the jar is created with `unsafe=True`. Without that the
`stok` cookie vanishes and every reading comes back empty. If you are writing
your own client, this is the trap.

**Fields are strings, and inapplicable ones are `""`.** Not `null`, not absent.
A 3G-only field on an LTE connection is an empty string, which is why entities
report `unknown` rather than `0`.

## Entity naming note

The `realtime_tx` / `realtime_rx` sensors keep English names in every
translation, on purpose. They change on every single poll and are the natural
candidates for a `recorder:` exclusion, and a glob like `sensor.*_realtime_*`
only works if the entity id is predictable regardless of the user's language.

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.*_realtime_*
```

## Development

```bash
ruff check .
ruff format --check .
```

`hassfest` and the HACS validator run in CI on every push and weekly.

## License

MIT — see [LICENSE](LICENSE).

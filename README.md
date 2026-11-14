# CUL Weather

Home Assistant custom integration for LaCrosse/Technoline weather sensors via compatible CUL/JeeLink receivers.

![CUL Weather logo](assets/cul-weather.svg)

## Features

- a-culfw CUL/CUBe through local TCP/IP (`host:port`)
- USB serial CUL and supported JeeLink HMS receivers
- Multiple independent receivers as Home Assistant config entries
- LaCrosse IT+ temperature, humidity and low-battery entities
- Optional stable Home Assistant entity identity for a *single* TX29 sensor when its temporary radio ID changes after a battery replacement
- Reconfigure LAN address, TCP port, mode, and USB serial settings without deleting the hub
- Mark a sensor inactive after five days without reports (configurable, **never delete automatically**)
- Deduplicate matching radio IDs seen by multiple receivers, while preserving an existing owner's device ID
- Manually map a changed TX29 radio ID onto a known device after changing batteries

**Important:** There is no permanent sensor hardware identifier in the supported TX29 radio messages. The single-sensor option assumes only one matching sensor is heard by that receiver. A different sensor could be associated incorrectly if this assumption is false.

Automatic receiver deduplication is based on identical radio IDs, **not** on a unique transmitter serial number. If different physical sensors send the same ID, they cannot be distinguished reliably. A battery change may generate a new ID; only the explicit assignment (`new ID=old ID`) or the carefully constrained single-sensor mode can retain the prior logical identity. Never assume a new random ID identifies the old physical sensor.

## Installation

On Home Assistant 2026.11 or newer, choose **Settings → Marketplace → Add from link** and add the public repository URL. Install the integration, then restart Home Assistant.

For manual installation, copy `custom_components/cul_weather/` into your Home Assistant configuration directory and restart.

Back up an existing `custom_components/cul_weather/` directory before upgrading. The integration domain stays `cul_weather`.

## Setup

Go to **Settings → Devices & services → Add integration → CUL Weather**, then choose either LAN/TCP or USB. For a TX29DTH-IT on a-culfw choose `IT+ 17.241 kbit/s` (mode `it1`). The default TCP port is `2323`; enter the actual receiver address yourself. Close other programs using the receiver while adding it.

For a USB receiver, select the matching serial port and firmware/mode. Paths under `/dev/serial/by-id/` are preferred.

## Edit settings and inactive sensors

- Open **Settings → Devices & services → CUL Weather** and use the hub's three-dot menu **Reconfigure** to edit connection details such as its IP address and TCP port. Existing entity IDs remain associated with the same hub configuration entry.
- Choose **Configure** / **Options** to change the inactivity threshold (default **5 days**), enable/disable radio-ID deduplication, set single-sensor behavior, or map a changed ID.
- An `Inactive` diagnostic entity per detected transmitter turns on after the configured period since the last valid report. Temperature, humidity, and low-battery entities may show **Unavailable** earlier (after 10 minutes without an updated measurement). **No sensor is automatically deleted**, even after months without reports. Removal in the Home Assistant UI is a separate, manual choice.
- An available low-battery flag is a **binary warning**, not a battery percentage. If the radio packet provides no battery status, no percentage can be inferred.
- When adding a second receiver, add a second CUL Weather hub and keep **Merge matching radio IDs** enabled on both. A known radio ID is assigned to one hub. Two unrelated transmitters using the same ID are not distinguishable. The shared radio ID mapping is local to the Home Assistant instance and is not a general-purpose cross-device fingerprint.

Configuration and last-seen timestamps are stored only in Home Assistant's local configuration and storage; do not commit those private files or real device logs to a public GitHub repository.

## Releases

### 0.4.0

- Reconfigure LAN/USB connection settings after initial setup.
- Add editable options for inactivity, receiver merging, and explicit new-to-old radio ID mapping.
- Add a diagnostic inactive flag after five days without messages; **never auto-remove a sensor**.
- Persist last-seen timestamps and readings across Home Assistant restarts; previously restored measurements are not presented as fresh.
- Deduplicate the same radio ID seen by multiple configured receivers.
- Preserve binary low-battery reporting; no fictitious battery percentage.

**Verification:** Protocol unit tests and syntax/JSON checks pass; full hardware and HAOS UI end-to-end testing is not yet claimed.

### 0.3.0

- Added LAN/TCP receiver connection and reconnection support.
- Preserved existing USB and JeeLink receiver support.
- Added multi-receiver configuration flow.
- Added opt-in stable entity mapping for one IT+ TX29 sensor.

**Status:** Initial community release candidate. Syntax and sample protocol decoding were tested; end-to-end tests with hardware and Home Assistant are still needed.


# CUL Weather

Home Assistant custom integration for LaCrosse/Technoline weather sensors via compatible CUL/JeeLink receivers.

![CUL Weather logo](assets/cul-weather.svg)

## Features

- a-culfw CUL/CUBe through local TCP/IP (`host:port`)
- USB serial CUL and supported JeeLink HMS receivers
- Multiple independent receivers as Home Assistant config entries
- LaCrosse IT+ temperature, humidity and low-battery entities
- Optional stable Home Assistant entity identity for a *single* TX29 sensor when its temporary radio ID changes after a battery replacement

**Important:** There is no permanent sensor hardware identifier in the supported TX29 radio messages. The single-sensor option assumes only one matching sensor is heard by that receiver. A different sensor could be associated incorrectly if this assumption is false.

## Installation

On Home Assistant 2026.11 or newer, choose **Settings → Marketplace → Add from link** and add the public repository URL. Install the integration, then restart Home Assistant.

For manual installation, copy `custom_components/cul_weather/` into your Home Assistant configuration directory and restart.

Back up an existing `custom_components/cul_weather/` directory before upgrading. The integration domain stays `cul_weather`.

## Setup

Go to **Settings → Devices & services → Add integration → CUL Weather**, then choose either LAN/TCP or USB. For a TX29DTH-IT on a-culfw choose `IT+ 17.241 kbit/s` (mode `it1`). The default TCP port is `2323`; enter the actual receiver address yourself. Close other programs using the receiver while adding it.

For a USB receiver, select the matching serial port and firmware/mode. Paths under `/dev/serial/by-id/` are preferred.

## Releases

### 0.3.0

- Added LAN/TCP receiver connection and reconnection support.
- Preserved existing USB and JeeLink receiver support.
- Added multi-receiver configuration flow.
- Added opt-in stable entity mapping for one IT+ TX29 sensor.

**Status:** Initial community release candidate. Syntax and sample protocol decoding were tested; end-to-end tests with hardware and Home Assistant are still needed.


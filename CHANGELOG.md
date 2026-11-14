# Changelog

## 0.3.1

- Add a Home Assistant-compatible `brand/icon.png` so the integration has its own icon.
- Place English and German translations in Home Assistant's expected `translations/` folder.

## 0.3.0

First public release of CUL Weather.

- Connect to a-culfw CUL/CUBe devices over local TCP/IP.
- Keep existing USB CUL and JeeLink HMS receiver support.
- Configure multiple independent receivers in Home Assistant.
- Decode supported LaCrosse IT+ temperature, humidity and battery information.
- Optional stable Home Assistant entity identity for a single TX29 sensor after a radio-ID change.

**Note:** The single-sensor option must not be used with multiple matching sensors on the same receiver. This release is not yet hardware-tested across all supported receivers.

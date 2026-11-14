# Changelog

All changes in this repository are recorded in Git commits. Releases summarize the corresponding changes.

## 0.4.0 — 2026-11-14

### Added
- In-place reconfiguration of LAN host, TCP port and radio mode, or USB path, speed and mode.
- Options for inactivity threshold (default five days), merging matching radio IDs from multiple hubs, single-sensor mode, and explicit new-ID-to-old-ID mapping.
- Per-sensor `Inactive` diagnostic and `last_seen_utc` attribute.
- Local persistence of the last received time and last values; measurements restored from storage start unavailable until new reports arrive.
- Unit tests using exclusively synthetic example frames and radio IDs.

### Changed
- Matching radio IDs from multiple receivers elect one deterministic Home Assistant device owner where receiver merging is enabled.
- Loss of a connection no longer discards the receiver's previous measurements immediately; each field keeps its normal freshness timeout.
- German and English user-interface strings cover new configuration and diagnostic options.

### Data retention and privacy
- **Never automatically delete inactive sensors**, regardless of how long they are silent. Device deletion is a separate manual action.
- The integration exposes the transmitted low-battery indicator only as a binary state; no battery percentage is fabricated.
- No user IP addresses, device IDs, private logs or credentials are included in this release.

### Known limitations
- TX29 sensor identity after a battery replacement is not provable from its changing radio ID alone. An explicit mapping or one-sensor constraint is required.
- Two different transmitters with the same radio ID cannot be reliably differentiated.
- Receiver and Home Assistant OS hardware integration testing remains pending; static checks and unit tests are not a hardware certification.

## 0.3.1

- Earlier LAN/USB integration, multi-receiver setup, logo and release packaging.

"""Decode documented CUL weather reports without Home Assistant dependencies."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Reading:
    address: str
    temperature: float | None = None
    humidity: float | None = None
    battery_low: bool | None = None


def crc8(data: bytes) -> int:
    crc = 0
    for octet in data:
        crc ^= octet
        for _ in range(8):
            crc = ((crc << 1) ^ (0x31 if crc & 0x80 else 0)) & 0xFF
    return crc


def decode(line: bytes, mode: str) -> Reading | None:
    """Decode a complete serial report from the selected receiver mode."""
    if mode == "jeelink_hms":
        # Original LaCrosseITPlusReader.10.1g_HMS_mod3 debug output.
        # HMS output loses the second-channel flag of TX25; use raw RF instead.
        match = re.fullmatch(rb"End receiving, HEX raw data: ((?:[0-9A-Fa-f]{1,2} ){4,63}[0-9A-Fa-f]{1,2})", line.strip())
        if match is None:
            return None
        payload = bytes(int(value, 16) for value in match[1].split())
        line = b"N01" + payload.hex().encode("ascii")
        mode = "it1"

    if mode == "tx":
        # X01 disables the optional RSSI suffix. The firmware validates RF
        # integrity before reporting and omits the RF checksum nibble.
        if not re.fullmatch(rb"t[aA][0eE][0-9A-Fa-f]{2}[0-9]{5}", line):
            return None
        address = int(line[3:5], 16) >> 1
        if line[5:7] != line[8:10]:
            return None
        value = int(line[5:8])
        if line[2:3] == b"0":
            return Reading(f"tx-{address:02x}", temperature=(value - 500) / 10)
        if value <= 1000:
            return Reading(f"tx-{address:02x}", humidity=value / 10)
        return None

    prefix = {"it1": b"N01", "it2": b"N02"}.get(mode)
    if prefix is None:
        return None
    if not re.fullmatch(prefix + rb"(?:[0-9A-Fa-f]{2}){5,64}", line):
        return None
    payload = bytes.fromhex(line[3:13].decode("ascii"))
    first, second, third, flags, checksum = payload
    if first >> 4 != 9 or crc8(payload[:4]) != checksum:
        return None
    tens, ones, tenths = second & 15, third >> 4, third & 15
    if max(tens, ones, tenths) > 9:
        return None
    humidity = flags & 127
    if humidity > 100 and humidity not in (106, 125):
        return None
    address = ((first & 15) << 2) | (second >> 6)
    if humidity == 125:
        address |= 64
    return Reading(
        f"{mode}-{address:02x}",
        temperature=(100 * tens + 10 * ones + tenths - 400) / 10,
        humidity=humidity if humidity <= 100 else None,
        battery_low=bool(flags & 128),
    )


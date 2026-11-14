"""Serial negotiation and receive loop."""

import asyncio
from contextlib import asynccontextmanager
import logging
import re

from serial_asyncio_fast import open_serial_connection

from .protocol import decode

LOGGER = logging.getLogger(__name__)
MODES = {"tx": b"X01", "it1": b"Nr1", "it2": b"Nr2"}


class FirmwareError(OSError):
    """The firmware did not confirm the requested command."""


async def expect(reader, pattern):
    async with asyncio.timeout(2):
        while line := await reader.readline():
            line = line.strip()
            LOGGER.debug("CUL handshake RX: %r", line)
            if re.fullmatch(pattern, line):
                return line
            if line.startswith(b"?"):
                break
    raise FirmwareError("Unerwartete Antwort der CUL-Firmware")


@asynccontextmanager
async def connect(port, baud, mode):
    try:
        reader, writer = await open_serial_connection(
            url=port, baudrate=baud, exclusive=True, limit=1024
        )
    except (OSError, ValueError) as err:
        LOGGER.warning("Cannot open CUL port %s at %s baud: %s", port, baud, err)
        raise
    try:
        # Opening some Arduino-based receivers resets their bootloader.
        await asyncio.sleep(2)
        if mode == "jeelink_hms":
            writer.write(b"v\n")
            version = await expect(
                reader, rb"\[LaCrosseITPlusReader\.10\.1g_HMS_mod3 [ -~]*\]"
            )
            LOGGER.info("JeeLink %s: %s", port, version.decode("ascii"))
            # The original HMS mod3 drops TX25's second-channel marker in
            # HMS output. Its documented debug output preserves the complete
            # RF payload, allowing us to validate CRC and retain both channels.
            # Receive at 17.241 kbit/s, no toggling and no RF relay.
            writer.write(b"0t 0r 0y 1d v\n")
            await expect(reader, rb"\[LaCrosseITPlusReader\.10\.1g_HMS_mod3 [ -~]*@17241 kbps / [0-9]+ kHz\]")
        else:
            writer.write(b"V\n")
            version = await expect(reader, rb"V\s+[0-9][ -~]*")
            LOGGER.debug("CUL %s: %s", port, version)
            writer.write(MODES[mode] + b"\n")
            if mode != "tx":
                await expect(reader, b"01" if mode == "it1" else b"02")
        yield reader
    finally:
        writer.close()
        try:
            async with asyncio.timeout(2):
                await writer.wait_closed()
        except (OSError, TimeoutError):
            pass


@asynccontextmanager
async def connect_tcp(host, tcp_port, mode):
    """Use the same command and report format over a CUBe TCP socket."""
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, tcp_port), 7)
    try:
        writer.write(b"V\n")
        await writer.drain()
        version = await expect(reader, rb"V\s+[0-9][ -~]*")
        LOGGER.info("LAN CUL %s:%s: %s", host, tcp_port, version.decode("ascii", "replace"))
        writer.write(MODES[mode] + b"\n")
        await writer.drain()
        if mode != "tx":
            await expect(reader, b"01" if mode == "it1" else b"02")
        yield reader
    finally:
        writer.close()
        try:
            async with asyncio.timeout(2):
                await writer.wait_closed()
        except (OSError, TimeoutError):
            pass


async def receive(port, baud, mode, on_reading, on_disconnect):
    """Reconnect after a serial disconnect or unsuccessful handshake."""
    while True:
        try:
            async with connect(port, baud, mode) as reader:
                while line := await reader.readline():
                    line = line.strip()
                    LOGGER.debug("CUL %s RX: %r", port, line)
                    if reading := decode(line, mode):
                        on_reading(reading)
                raise OSError("Serieller Anschluss geschlossen")
        except (OSError, ValueError) as err:
            LOGGER.warning("CUL %s: %s. Neuer Versuch in 10 Sekunden", port, err)
            on_disconnect()
            await asyncio.sleep(10)


async def receive_tcp(host, tcp_port, mode, on_reading, on_disconnect):
    """Reconnect on connection loss; initialize RF mode on each reconnect."""
    endpoint = f"{host}:{tcp_port}"
    while True:
        try:
            async with connect_tcp(host, tcp_port, mode) as reader:
                while line := await reader.readline():
                    LOGGER.debug("LAN CUL %s RX: %r", endpoint, line.strip())
                    if reading := decode(line.strip(), mode):
                        on_reading(reading)
                raise OSError("TCP connection closed")
        except (OSError, ValueError, TimeoutError, FirmwareError) as err:
            LOGGER.warning("LAN CUL %s: %s; reconnecting in 10s", endpoint, err)
            on_disconnect()
            await asyncio.sleep(10)


"""Direct CUL USB weather receiver for Home Assistant."""

import asyncio
from contextlib import suppress

from homeassistant.const import Platform

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass, entry):
    from .hub import Hub

    entry.runtime_data = Hub(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.runtime_data.start()
    return True


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    task = entry.runtime_data.task
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    return True

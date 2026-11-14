"""CUL Weather receivers and shared LaCrosse measurements."""

import asyncio
from contextlib import suppress

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass, entry):
    from .hub import Hub

    entry.runtime_data = Hub(hass, entry)
    await entry.runtime_data.async_load()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.runtime_data.start()
    return True


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    entry.runtime_data.stop()
    task = entry.runtime_data.task
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    return True


async def async_remove_config_entry_device(hass, entry, device_entry: dr.DeviceEntry) -> bool:
    """Allow manual removal of long-inactive sensors, never remove automatically."""
    hub = entry.runtime_data
    for domain, identifier in device_entry.identifiers:
        prefix = f"{entry.entry_id}-"
        if domain == "cul_weather" and identifier.startswith(prefix):
            return hub.inactive(identifier[len(prefix):])
    return False

"""Track individual measurements and notify Home Assistant platforms."""

from datetime import timedelta
from time import monotonic

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .receiver import receive, receive_tcp

DOMAIN = "cul_weather"
STALE_AFTER = 600


class Hub:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.values = {}
        self.listeners = []
        self.connected = False
        self.primary_radio_id = None
        self.primary_last_seen = None

    @callback
    def start(self):
        data = self.entry.data
        if data.get("connection", "usb") == "lan":
            coro = receive_tcp(data["host"], data["tcp_port"], data["mode"], self.update, self.disconnect)
        else:
            coro = receive(data["port"], data["baud"], data["mode"], self.update, self.disconnect)
        self.task = self.entry.async_create_background_task(
            self.hass,
            coro,
            "CUL weather receiver",
        )

    @callback
    def update(self, reading):
        self.connected = True
        now = monotonic()
        address = reading.address
        if self.entry.data.get("single_sensor", False) and address.startswith(("it1-", "it2-")):
            # The TX29 changes its RF id on a battery replacement. A single
            # sensor may be reassigned after it has been silent for 5 minutes.
            # Multiple sensors on one frequency MUST disable this option.
            if self.primary_radio_id is None:
                self.primary_radio_id = address
            elif address != self.primary_radio_id:
                if self.primary_last_seen is not None and now - self.primary_last_seen < 300:
                    return
                self.primary_radio_id = address
            self.primary_last_seen = now
            address = f"{self.entry.data['mode']}-single"
        values = self.values.setdefault(address, {})
        for field in ("temperature", "humidity", "battery_low"):
            value = getattr(reading, field)
            if value is not None:
                values[field] = (value, now)
        for listener in self.listeners:
            listener(address)

    @callback
    def disconnect(self):
        if self.connected:
            self.connected = False
            # Keep RF identity across transient TCP failures.
            # Old measurements should not become available again on reconnect.
            for values in self.values.values():
                for field, (value, _) in values.items():
                    values[field] = (value, float("-inf"))
            for address in self.values:
                for listener in self.listeners:
                    listener(address)

    @callback
    def attach(self, entry, add_entities, fields, entity_class):
        entities = {}

        @callback
        def update(address):
            for field in fields.keys() & self.values[address].keys():
                key = (address, field)
                if key in entities:
                    entity = entities[key]
                    if entity.ready:
                        entity.async_write_ha_state()
                else:
                    entity = entities[key] = entity_class(self, address, field, fields[field])
                    add_entities([entity])

        self.listeners.append(update)
        entry.async_on_unload(lambda: self.listeners.remove(update))
        for address in self.values:
            update(address)


class CulEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub, address, field, description):
        self.ready = False
        self.hub = hub
        self.address = address
        self.field = field
        self.entity_description = description
        identifier = f"{hub.entry.entry_id}-{address}"
        self._attr_unique_id = f"{identifier}-{field}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=f"LaCrosse {address.upper()}",
            model="LaCrosse IT+" if address.startswith("it") else "LaCrosse TX",
        )

    @property
    def reading(self):
        return self.hub.values[self.address][self.field]

    @property
    def available(self):
        return self.hub.connected and monotonic() - self.reading[1] < STALE_AFTER

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.ready = True
        self.async_on_remove(self.mark_removed)

        @callback
        def check_availability(_now):
            if not self.available:
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_time_interval(self.hass, check_availability, timedelta(seconds=30))
        )

    @callback
    def mark_removed(self):
        self.ready = False

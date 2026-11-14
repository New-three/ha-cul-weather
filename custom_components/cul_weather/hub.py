"""Track weather readings, receiver ownership and long-term inactivity."""

from datetime import datetime, timedelta, timezone
from time import monotonic, time

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo, async_entries_for_config_entry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .protocol import parse_aliases
from .receiver import receive, receive_tcp

DOMAIN = "cul_weather"
STALE_AFTER = 600  # Individual measurements become unavailable after 10 minutes.


class Hub:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.values = {}
        self.last_seen = {}
        self.listeners = []
        self.connected = False
        self.primary_radio_id = None
        self.primary_last_seen = None
        self.store = Store(hass, 1, f"cul_weather_{entry.entry_id}")
        self._cancel_timer = None

    async def async_load(self):
        """Restore last-seen times; never restore stale measurements as live."""
        saved = await self.store.async_load() or {}
        self.last_seen = saved.get("last_seen", {})
        for address, fields in saved.get("values", {}).items():
            self.values[address] = {
                field: (value, float("-inf"))
                for field, value in fields.items()
                if field in ("temperature", "humidity", "battery_low")
            }
            self._update_inactive(address)
        self.hass.data.setdefault(DOMAIN, {})[self.entry.entry_id] = self

    def _save_data(self):
        return {
            "last_seen": self.last_seen,
            "values": {
                address: {field: pair[0] for field, pair in values.items()
                          if field in ("temperature", "humidity", "battery_low")}
                for address, values in self.values.items()
            },
        }

    @callback
    def start(self):
        data = self.entry.data
        if data.get("connection", "usb") == "lan":
            coro = receive_tcp(data["host"], data["tcp_port"], data["mode"], self.update, self.disconnect)
        else:
            coro = receive(data["port"], data["baud"], data["mode"], self.update, self.disconnect)
        self.task = self.entry.async_create_background_task(self.hass, coro, "CUL weather receiver")
        self._cancel_timer = async_track_time_interval(self.hass, self._check_inactivity, timedelta(hours=1))

    @callback
    def stop(self):
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        self.hass.data.get(DOMAIN, {}).pop(self.entry.entry_id, None)

    @callback
    def _check_inactivity(self, _now):
        for address in self.last_seen:
            old = self.values.get(address, {}).get("inactive", (None, 0))[0]
            self._update_inactive(address)
            if old != self.values[address]["inactive"][0]:
                self._notify(address)

    def inactive(self, address):
        latest = self.last_seen.get(address)
        if latest is None:
            return False
        days = self.entry.options.get("inactive_days", 5)
        return time() - latest >= days * 86400

    def _update_inactive(self, address):
        self.values.setdefault(address, {})["inactive"] = (self.inactive(address), monotonic())

    def _notify(self, address):
        for listener in self.listeners:
            listener(address)

    def _owner(self, address):
        """Elect one stable owner for a radio ID across all active receivers."""
        if not self.entry.options.get("merge_receivers", True):
            return self
        hubs = self.hass.data.get(DOMAIN, {})
        candidates = [hub for hub in hubs.values()
                      if hub.entry.options.get("merge_receivers", True)]
        # Prefer a hub that already owns a matching logical device. Sorting is
        # deterministic even if two previously independent hubs saw it first.
        registry = dr.async_get(self.hass)
        registered = []
        for hub in candidates:
            identifier = (DOMAIN, f"{hub.entry.entry_id}-{address}")
            if any(identifier in device.identifiers for device in async_entries_for_config_entry(registry, hub.entry.entry_id)):
                registered.append(hub)
        if registered:
            return min(registered, key=lambda hub: hub.entry.entry_id)
        known = [hub for hub in candidates if address in hub.values]
        return min(known, key=lambda hub: hub.entry.entry_id) if known else self

    @callback
    def update(self, reading):
        self.connected = True
        address = reading.address
        # Explicit mappings preserve the prior logical ID after battery changes.
        aliases = parse_aliases(self.entry.options.get("id_aliases", ""))
        address = aliases.get(address, address)
        if self.entry.options.get("single_sensor", self.entry.data.get("single_sensor", False)) and address.startswith(("it1-", "it2-")):
            now = monotonic()
            if self.primary_radio_id is None:
                self.primary_radio_id = address
            elif address != self.primary_radio_id:
                if self.primary_last_seen is not None and now - self.primary_last_seen < 300:
                    return
                self.primary_radio_id = address
            self.primary_last_seen = now
            address = f"{self.entry.data['mode']}-single"
        owner = self._owner(address)
        owner._record(address, reading)

    @callback
    def _record(self, address, reading):
        now = monotonic()
        values = self.values.setdefault(address, {})
        for field in ("temperature", "humidity", "battery_low"):
            value = getattr(reading, field)
            if value is not None:
                values[field] = (value, now)
        self.last_seen[address] = time()
        self._update_inactive(address)
        self.store.async_delay_save(self._save_data, 10)
        self._notify(address)

    @callback
    def disconnect(self):
        # Keep values until their individual timeout. Another hub can relay
        # the same transmitter while this receiver is offline.
        self.connected = False

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
                    entities[key] = entity_class(self, address, field, fields[field])
                    add_entities([entities[key]])

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
        if self.field == "inactive":
            return True
        return monotonic() - self.reading[1] < STALE_AFTER

    @property
    def extra_state_attributes(self):
        last = self.hub.last_seen.get(self.address)
        return {"last_seen_utc": datetime.fromtimestamp(last, timezone.utc).isoformat() if last else None}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.ready = True
        self.async_on_remove(self.mark_removed)

        @callback
        def check_availability(_now):
            self.async_write_ha_state()

        self.async_on_remove(async_track_time_interval(self.hass, check_availability, timedelta(seconds=30)))

    @callback
    def mark_removed(self):
        self.ready = False

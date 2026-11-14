"""Low battery reports from LaCrosse IT+."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .hub import CulEntity

FIELDS = {
    "battery_low": BinarySensorEntityDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "inactive": BinarySensorEntityDescription(
        key="inactive",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        translation_key="inactive",
    ),
}


class CulBattery(CulEntity, BinarySensorEntity):
    @property
    def is_on(self):
        return self.reading[0]


async def async_setup_entry(hass, entry, async_add_entities):
    entry.runtime_data.attach(entry, async_add_entities, FIELDS, CulBattery)

"""Temperature and humidity entities."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature

from .hub import CulEntity

FIELDS = {
    "temperature": SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


class CulSensor(CulEntity, SensorEntity):
    @property
    def native_value(self):
        return self.reading[0]


async def async_setup_entry(hass, entry, async_add_entities):
    entry.runtime_data.attach(entry, async_add_entities, FIELDS, CulSensor)

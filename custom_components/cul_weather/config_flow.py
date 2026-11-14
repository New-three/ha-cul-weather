"""Configure USB and TCP/IP receivers."""
import logging
import os

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers import selector
import voluptuous as vol

from .receiver import connect, connect_tcp

DOMAIN = "cul_weather"
LOGGER = logging.getLogger(__name__)
USB_MODES = [
    {"value": "jeelink_hms", "label": "JeeLink HMS mod3 · TX25/TX29 (57600 Baud)"},
    {"value": "tx", "label": "SlowRF · TX2/TX3"},
    {"value": "it1", "label": "IT+ · 17.241 kbit/s (TX29)"},
    {"value": "it2", "label": "IT+ · 9.579 kbit/s"},
]
LAN_MODES = [item for item in USB_MODES if item["value"] != "jeelink_hms"]


def modes(items):
    return selector.SelectSelector(selector.SelectSelectorConfig(options=items))


class CulWeatherConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            if user_input["connection"] == "lan":
                return await self.async_step_lan()
            return await self.async_step_usb()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("connection", default="lan"): vol.In({"lan": "LAN / TCP", "usb": "USB / seriell"})}),
        )

    async def async_step_usb(self, user_input=None):
        errors = {}
        if user_input is not None:
            port = user_input["port"].strip()
            if not port.startswith("/dev/"):
                errors["port"] = "invalid_port"
            else:
                canonical = await self.hass.async_add_executor_job(os.path.realpath, port)
                for configured in self._async_current_entries():
                    other_port = configured.data.get("port")
                    if not other_port:
                        continue
                    other = await self.hass.async_add_executor_job(os.path.realpath, other_port)
                    if canonical == other:
                        return self.async_abort(reason="already_configured")
                await self.async_set_unique_id(f"usb:{canonical}")
                self._abort_if_unique_id_configured()
                data = {**user_input, "port": port, "connection": "usb"}
                try:
                    async with connect(port, data["baud"], data["mode"]):
                        pass
                except (OSError, ValueError, TimeoutError) as err:
                    LOGGER.warning("USB CUL setup failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=f"CUL USB · {os.path.basename(port)}", data=data)
        defaults = user_input or {"port": "", "baud": 38400, "mode": "tx", "single_sensor": False}
        return self.async_show_form(
            step_id="usb",
            data_schema=vol.Schema({
                vol.Required("port", default=defaults["port"]): str,
                vol.Required("baud", default=defaults["baud"]): vol.In([38400, 57600, 115200, 9600]),
                vol.Required("mode", default=defaults["mode"]): modes(USB_MODES),
                vol.Required("single_sensor", default=defaults["single_sensor"]): bool,
            }), errors=errors,
        )

    async def async_step_lan(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input["host"].strip()
            port = user_input["tcp_port"]
            if not host or any(char.isspace() for char in host):
                errors["host"] = "invalid_host"
            else:
                await self.async_set_unique_id(f"lan:{host.lower()}:{port}")
                self._abort_if_unique_id_configured()
                data = {**user_input, "host": host, "connection": "lan"}
                try:
                    async with connect_tcp(host, port, data["mode"]):
                        pass
                except (OSError, ValueError, TimeoutError) as err:
                    LOGGER.warning("LAN CUL setup failed for %s:%s: %s", host, port, err)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=f"CUL LAN · {host}:{port}", data=data)
        defaults = user_input or {"host": "", "tcp_port": 2323, "mode": "it1", "single_sensor": False}
        return self.async_show_form(
            step_id="lan",
            data_schema=vol.Schema({
                vol.Required("host", default=defaults["host"]): str,
                vol.Required("tcp_port", default=defaults["tcp_port"]): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required("mode", default=defaults["mode"]): modes(LAN_MODES),
                vol.Required("single_sensor", default=defaults["single_sensor"]): bool,
            }), errors=errors,
        )

"""Configure USB and TCP/IP receivers."""
import logging
import os

from homeassistant.config_entries import ConfigFlow, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .receiver import connect, connect_tcp
from .protocol import parse_aliases

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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CulWeatherOptionsFlow()

    async def async_step_reconfigure(self, user_input=None):
        """Edit connection details while retaining the config entry ID."""
        entry = self._get_reconfigure_entry()
        data = entry.data
        errors = {}
        if user_input is not None:
            try:
                if data.get("connection", "usb") == "lan":
                    host = user_input["host"].strip()
                    port = user_input["tcp_port"]
                    if not host or any(c.isspace() for c in host):
                        errors["host"] = "invalid_host"
                        raise ValueError("Invalid host")
                    if any(other.entry_id != entry.entry_id and other.data.get("connection") == "lan" and other.data.get("host", "").lower() == host.lower() and other.data.get("tcp_port") == port for other in self._async_current_entries()):
                        return self.async_abort(reason="already_configured")
                    async with connect_tcp(host, port, user_input["mode"]):
                        pass
                    changes = {**user_input, "host": host}
                    new_id = f"lan:{host.lower()}:{port}"
                    title = f"CUL LAN · {host}:{port}"
                else:
                    port = user_input["port"].strip()
                    if not port.startswith("/dev/"):
                        return self.async_show_form(step_id="reconfigure", data_schema=self._reconfigure_schema(data), errors={"port": "invalid_port"})
                    canonical = await self.hass.async_add_executor_job(os.path.realpath, port)
                    if any(other.entry_id != entry.entry_id and other.data.get("port") == port for other in self._async_current_entries()):
                        return self.async_abort(reason="already_configured")
                    async with connect(port, user_input["baud"], user_input["mode"]):
                        pass
                    changes = {**user_input, "port": port}
                    new_id = f"usb:{canonical}"
                    title = f"CUL USB · {os.path.basename(port)}"
            except (OSError, ValueError, TimeoutError, KeyError) as err:
                LOGGER.warning("CUL reconfiguration failed: %s", err)
                if not errors:
                    errors["base"] = "cannot_connect"
            else:
                # The entry ID stays unchanged, so existing HA IDs survive.
                self.hass.config_entries.async_update_entry(entry, title=title, unique_id=new_id)
                return self.async_update_reload_and_abort(entry, data_updates=changes)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._reconfigure_schema(data, user_input),
            errors=errors,
        )

    @staticmethod
    def _reconfigure_schema(data, values=None):
        current = values or data
        if data.get("connection", "usb") == "lan":
            return vol.Schema({
                vol.Required("host", default=current["host"]): str,
                vol.Required("tcp_port", default=current["tcp_port"]): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required("mode", default=current["mode"]): modes(LAN_MODES),
            })
        return vol.Schema({
            vol.Required("port", default=current["port"]): str,
            vol.Required("baud", default=current["baud"]): vol.In([38400, 57600, 115200, 9600]),
            vol.Required("mode", default=current["mode"]): modes(USB_MODES),
        })

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


class CulWeatherOptionsFlow(OptionsFlowWithReload):
    """Options for display, inactivity and explicit radio ID assignment."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                parse_aliases(user_input["id_aliases"])
            except ValueError:
                errors["id_aliases"] = "invalid_aliases"
            else:
                return self.async_create_entry(data=user_input)
        defaults = {"inactive_days": 5, "merge_receivers": True, "id_aliases": "", "single_sensor": self.config_entry.data.get("single_sensor", False)}
        defaults.update(self.config_entry.options)
        defaults.update(user_input or {})
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required("inactive_days", default=defaults["inactive_days"]): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
            vol.Required("merge_receivers", default=defaults["merge_receivers"]): bool,
            vol.Required("single_sensor", default=defaults["single_sensor"]): bool,
            vol.Required("id_aliases", default=defaults["id_aliases"]): str,
        }), errors=errors)

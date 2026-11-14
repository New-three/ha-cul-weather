"""Protocol and explicit alias tests, runnable without Home Assistant."""

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "cul_weather" / "protocol.py"
spec = importlib.util.spec_from_file_location("cul_weather_protocol", MODULE_PATH)
protocol = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


class ProtocolTests(unittest.TestCase):
    def test_synthetic_radio_report(self):
        payload = bytes((0x94, 0x05, 0x60, 0x44))
        line = b"N01" + (payload + bytes((protocol.crc8(payload),))).hex().encode()
        reading = protocol.decode(line, "it1")
        self.assertEqual(reading.address, "it1-10")
        self.assertEqual(reading.temperature, 16.0)
        self.assertEqual(reading.humidity, 68)
        self.assertFalse(reading.battery_low)

    def test_battery_flag_is_binary_not_percentage(self):
        payload = bytes((0x94, 0x05, 0x60, 0xC4))
        line = b"N01" + (payload + bytes((protocol.crc8(payload),))).hex().encode()
        reading = protocol.decode(line, "it1")
        self.assertTrue(reading.battery_low)

    def test_bad_crc_is_ignored(self):
        self.assertIsNone(protocol.decode(b"N019405604400", "it1"))

    def test_alias_validation(self):
        self.assertEqual(protocol.parse_aliases("# comment\nIT1-2A=IT1-4B\n"), {"it1-2a": "it1-4b"})
        for invalid in ("it1-2a:it1-4b", "it1-2a=it1-4b\nit1-4b=it1-20", "it1-2a=garbage"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                protocol.parse_aliases(invalid)


if __name__ == "__main__":
    unittest.main()

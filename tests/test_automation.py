import unittest
from pcide.core.automation import com_object, describe_window, hid_device, list_hid_devices, list_serial_ports, list_windows, serial_port, screenshot, uia_root
from pcide.core.paths import Paths


class AutomationTests(unittest.TestCase):
    def test_windows_com_uia(self):
        self.assertIsInstance(list_windows(), list)
        with com_object("Scripting.Dictionary") as dictionary:
            dictionary.Add("pcide", 42)
            self.assertEqual(dictionary.Item("pcide"), 42)
        self.assertEqual(len(uia_root()["rect"]), 4)
        with self.assertRaises(ValueError):
            describe_window(0)
        image = Paths().logs / "automation-screen.png"
        result = screenshot(image)
        self.assertFalse(result["simulated"])
        self.assertTrue(image.is_file())

    def test_serial_loopback_and_device_inventory(self):
        self.assertIsInstance(list_serial_ports(), list)
        with serial_port("loop://") as connection:
            connection.write(b"pcide")
            self.assertEqual(connection.read(5), b"pcide")
        self.assertFalse(connection.is_open)
        self.assertIsInstance(list_hid_devices(), list)
        with self.assertRaises(ValueError):
            with hid_device("invalid"):
                pass


if __name__ == "__main__":
    unittest.main()

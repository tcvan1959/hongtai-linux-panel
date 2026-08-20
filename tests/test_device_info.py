import json
import unittest

from hongtai_panel.device import DeviceInfo
from hongtai_panel.protocol import ProtocolError


class DeviceInfoTests(unittest.TestCase):
    def test_parse_verified_device_information(self) -> None:
        payload = json.dumps(
            {
                "status": 200,
                "uid": "SYNTHETIC-UID-0001",
                "model": "TXW818-ST7796-3.5inch-hor",
                "version": "3.2",
                "width": 480,
                "height": 320,
                "brightness": 80,
                "angle": 0,
            }
        ).encode()
        info = DeviceInfo.from_payload(payload)
        self.assertEqual(info.status, 200)
        self.assertEqual(info.uid, "SYNTHETIC-UID-0001")
        self.assertEqual(info.model, "TXW818-ST7796-3.5inch-hor")
        self.assertEqual((info.width, info.height), (480, 320))
        self.assertEqual(info.brightness, 80)

    def test_parse_tolerates_missing_optional_fields(self) -> None:
        info = DeviceInfo.from_payload(b'{"status": 200}')
        self.assertEqual(info.status, 200)
        self.assertIsNone(info.model)
        self.assertIsNone(info.width)

    def test_parse_verified_nested_firmware_schema(self) -> None:
        info = DeviceInfo.from_payload(
            b'{"cmd":"info","data":{"uid":"SYNTHETIC-UID-0001",'
            b'"model":"TXW818-ST7796-3.5inch-hor","version":"3.2",'
            b'"width":480,"height":320,"brightness":80,"angle":0}}'
        )
        self.assertEqual(info.uid, "SYNTHETIC-UID-0001")
        self.assertEqual(info.model, "TXW818-ST7796-3.5inch-hor")
        self.assertEqual((info.width, info.height), (480, 320))
        self.assertEqual(info.version, "3.2")

    def test_parse_rejects_invalid_nested_data(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "data field"):
            DeviceInfo.from_payload(b'{"data":[]}')

    def test_parse_rejects_invalid_json(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "JSON"):
            DeviceInfo.from_payload(b"not-json")

    def test_parse_rejects_non_object_json(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "object"):
            DeviceInfo.from_payload(b"[]")


if __name__ == "__main__":
    unittest.main()

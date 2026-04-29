import importlib.util
import os
import sys
import types
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakeTable:
    def __init__(self):
        self.items = []
        self.update_kwargs = []

    def put_item(self, Item):
        self.items.append(Item)

    def update_item(self, **kwargs):
        self.update_kwargs.append(kwargs)


class FakeDynamo:
    def __init__(self, table):
        self.table = table

    def Table(self, name):
        return self.table


def install_aws_fakes(table):
    boto3 = types.ModuleType("boto3")
    boto3.client = lambda *args, **kwargs: object()
    boto3.resource = lambda *args, **kwargs: FakeDynamo(table)

    conditions = types.ModuleType("boto3.dynamodb.conditions")
    conditions.Key = object
    dynamodb_module = types.ModuleType("boto3.dynamodb")
    dynamodb_module.conditions = conditions
    boto3.dynamodb = dynamodb_module

    botocore = types.ModuleType("botocore")
    exceptions = types.ModuleType("botocore.exceptions")

    class ClientError(Exception):
        pass

    exceptions.ClientError = ClientError
    botocore.exceptions = exceptions

    sys.modules["boto3"] = boto3
    sys.modules["boto3.dynamodb"] = dynamodb_module
    sys.modules["boto3.dynamodb.conditions"] = conditions
    sys.modules["botocore"] = botocore
    sys.modules["botocore.exceptions"] = exceptions


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        install_aws_fakes(self.table)

        sys.modules["telegram_notify"] = types.SimpleNamespace(
            send_telegram_message=lambda text: True
        )
        sys.modules["rekognition_service"] = types.SimpleNamespace(
            get_face_match_result=lambda *args, **kwargs: {}
        )
        sys.modules["thumbnail_service"] = types.SimpleNamespace(
            generate_and_upload_thumbnail=lambda *args, **kwargs: None
        )
        sys.modules["notification_rules"] = types.SimpleNamespace(
            should_notify=lambda *args, **kwargs: (False, ""),
            build_notification_message=lambda *args, **kwargs: {},
        )

    def test_heartbeat_update_removes_none_values_and_uses_camel_case(self):
        module = load_module(
            "heartbeat_handler_test",
            ROOT / "backend/lambdas/device_health_check/heartbeat_handler.py",
        )

        values = module._build_update_values(
            body={"deviceId": "cam-01", "status": "online"},
            device_id="cam-01",
            status="online",
            alert_state="online",
            last_seen="2026-04-28T00:00:00+00:00",
        )
        module._update_device(self.table, "cam-01", values)

        kwargs = self.table.update_kwargs[-1]
        self.assertIn("REMOVE", kwargs["UpdateExpression"])
        self.assertNotIn(None, kwargs.get("ExpressionAttributeValues", {}).values())
        self.assertIn("#alertState", kwargs["ExpressionAttributeNames"])
        self.assertNotIn("#alert_state", kwargs["ExpressionAttributeNames"])
        self.assertNotIn("#last_error", kwargs["ExpressionAttributeNames"])

    def test_health_check_online_update_removes_last_error(self):
        module = load_module(
            "health_handler_test",
            ROOT / "backend/lambdas/device_health_check/handler.py",
        )

        module._update_device_state(
            self.table,
            "cam-01",
            status="online",
            alert_state="online",
            last_error=None,
            extra={"offlineSince": None},
        )

        kwargs = self.table.update_kwargs[-1]
        self.assertIn("alertState", kwargs["ExpressionAttributeNames"].values())
        self.assertIn("REMOVE", kwargs["UpdateExpression"])
        self.assertNotIn(None, kwargs.get("ExpressionAttributeValues", {}).values())

    def test_detection_save_sets_ttl(self):
        os.environ["DETECTIONS_TABLE"] = "detections"
        os.environ["DETECTION_TTL_DAYS"] = "90"
        module = load_module(
            "process_image_handler_test",
            ROOT / "backend/lambdas/process_image/handler.py",
        )

        item = module._save_detection(
            device_id="cam-01",
            timestamp="2026-04-28T00:00:00+00:00",
            status="unknown",
            person_id=None,
            confidence=0,
            face_count=1,
            raw_image_key="s3://bucket/key.jpg",
            thumbnail_key=None,
        )

        self.assertIn("ttl", item)
        self.assertIsInstance(item["ttl"], int)
        self.assertGreater(item["ttl"], 0)
        self.assertIsInstance(item["confidence"], Decimal)


if __name__ == "__main__":
    unittest.main()

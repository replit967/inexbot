import hashlib
import hmac
import importlib
import os
import unittest
import urllib.parse
from unittest.mock import patch

from fastapi import HTTPException


TOKEN = "webapp-test-token"
with patch.dict(os.environ, {"BOT_TOKEN": TOKEN, "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS": "3600"}):
    import webapp.server as server
    server = importlib.reload(server)


def signed_init_data(fields):
    pairs = dict(fields)
    data_check = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(pairs)


class InitDataValidationTests(unittest.TestCase):
    def test_valid_recent_init_data_is_accepted(self):
        payload = signed_init_data({"auth_date": "1000", "user": '{"id":123}'})
        result = server.verify_init_data(payload, now=1200)
        self.assertEqual(result["user"]["id"], 123)

    def test_expired_init_data_is_rejected(self):
        payload = signed_init_data({"auth_date": "1000", "user": '{"id":123}'})
        with self.assertRaises(HTTPException) as raised:
            server.verify_init_data(payload, now=4601)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "Expired initData")

    def test_future_auth_date_is_rejected(self):
        payload = signed_init_data({"auth_date": "2000", "user": '{"id":123}'})
        with self.assertRaises(HTTPException) as raised:
            server.verify_init_data(payload, now=1900)
        self.assertEqual(raised.exception.status_code, 403)

    def test_missing_auth_date_is_rejected(self):
        payload = signed_init_data({"user": '{"id":123}'})
        with self.assertRaises(HTTPException) as raised:
            server.verify_init_data(payload, now=1200)
        self.assertEqual(raised.exception.detail, "Missing or invalid auth_date")

    def test_duplicate_fields_are_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            server.verify_init_data("auth_date=1000&auth_date=1001&hash=abc", now=1200)
        self.assertEqual(raised.exception.detail, "Duplicate initData fields")

    def test_malformed_query_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            server.verify_init_data("auth_date", now=1200)
        self.assertEqual(raised.exception.detail, "Malformed initData")

    def test_invalid_signature_is_rejected(self):
        payload = signed_init_data({"auth_date": "1000", "user": '{"id":123}'})
        payload = payload.replace("hash=", "hash=bad")
        with self.assertRaises(HTTPException) as raised:
            server.verify_init_data(payload, now=1200)
        self.assertEqual(raised.exception.detail, "Bad initData signature")


if __name__ == "__main__":
    unittest.main()

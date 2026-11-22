import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer

import mini_intranet  # noqa: F401
from lapisite.webhooks import compute_signature
from mini_intranet import receiver

SECRET = "whsec_" + "test" * 8  # built at runtime: not a real secret


class ReceiverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = []
        cls.server = HTTPServer(("127.0.0.1", 0), receiver.make_handler(SECRET, cls.events.append))
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, body, *, stamp=None, signature=None):
        stamp = int(time.time()) if stamp is None else stamp
        if signature is None:
            signature = "v1=" + compute_signature(SECRET, stamp, body)
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/lapisite",
            data=body,
            method="POST",
            headers={"Lapisite-Webhook-Timestamp": str(stamp), "Lapisite-Webhook-Signature": signature},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as answer:
                return answer.status
        except urllib.error.HTTPError as error:
            return error.code

    def body(self, event_id="evt_" + "0" * 24):
        return json.dumps({"id": event_id, "type": "job.succeeded", "site": 7}).encode()

    def test_signed_body_accepted(self):
        before = len(self.events)
        self.assertEqual(self.post(self.body("evt_" + "a" * 24)), 204)
        self.assertEqual(self.events[before]["type"], "job.succeeded")

    def test_duplicate_event_handled_once(self):
        body = self.body("evt_" + "b" * 24)
        before = len(self.events)
        self.assertEqual(self.post(body), 204)
        self.assertEqual(self.post(body), 204)
        self.assertEqual(len(self.events), before + 1)

    def test_tampered_body_rejected(self):
        body = self.body("evt_" + "c" * 24)
        stamp = int(time.time())
        signature = "v1=" + compute_signature(SECRET, stamp, body)
        self.assertEqual(self.post(body + b" ", stamp=stamp, signature=signature), 400)

    def test_stale_timestamp_rejected(self):
        self.assertEqual(self.post(self.body("evt_" + "d" * 24), stamp=int(time.time()) - 3600), 400)

    def test_missing_signature_rejected(self):
        self.assertEqual(self.post(self.body(), signature="nonsense"), 400)


if __name__ == "__main__":
    unittest.main()

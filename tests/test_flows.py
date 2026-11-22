import unittest

import mini_intranet  # noqa: F401
from mini_intranet import flows


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


class FakeStudio:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.created = []

    def get_job(self, job_id):
        return {"id": job_id, "status": self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]}

    def create_site(self, *, body, idempotency_key=None):
        self.created.append(body)
        return {"id": 7}

    def generate_site(self, site_id, *, idempotency_key=None):
        return {"id": 99, "site": site_id, "status": "queued"}


class FakeClient:
    def __init__(self, statuses=("succeeded",)):
        self.studio = FakeStudio(statuses)


class FollowTest(unittest.TestCase):
    def test_polls_with_backoff_until_done(self):
        clock = Clock()
        client = FakeClient(["queued", "running", "running", "succeeded"])
        job = flows.follow_job(client, 99, sleep=clock.sleep, clock=clock.now, first_delay=1, factor=2, max_delay=3)
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(clock.sleeps, [1, 2, 3])

    def test_failed_is_a_result_not_an_exception(self):
        clock = Clock()
        job = flows.follow_job(FakeClient(["running", "failed"]), 1, sleep=clock.sleep, clock=clock.now)
        self.assertEqual(job["status"], "failed")

    def test_timeout(self):
        clock = Clock()
        with self.assertRaises(flows.FollowTimeout):
            flows.follow_job(FakeClient(["running"]), 1, timeout=5, sleep=clock.sleep, clock=clock.now)

    def test_create_site_uses_fictional_data_and_starts_generation(self):
        client = FakeClient()
        result = flows.create_site(client)
        self.assertEqual(result["job"]["id"], 99)
        self.assertTrue(client.studio.created[0]["domain"].endswith(".example"))


if __name__ == "__main__":
    unittest.main()

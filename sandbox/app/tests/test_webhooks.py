import unittest

from webhooks import backoff_seconds, should_retry


class WebhooksTest(unittest.TestCase):
    def test_server_errors_are_retried(self):
        self.assertTrue(should_retry(503))
        self.assertFalse(should_retry(404))

    def test_backoff_grows(self):
        self.assertEqual([backoff_seconds(n) for n in (1, 2, 3)], [1, 4, 16])

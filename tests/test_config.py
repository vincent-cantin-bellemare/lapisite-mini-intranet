import unittest

import mini_intranet  # noqa: F401  (puts vendor/ on sys.path)
from mini_intranet import cli, config


class KeyGuardTest(unittest.TestCase):
    def test_missing_key(self):
        with self.assertRaises(config.ConfigError):
            config.require_test_key({})

    def test_non_test_key_refused(self):
        with self.assertRaises(config.ConfigError):
            config.require_test_key({"LAPISITE_API_KEY": "lps_" + "live_" + "x" * 8})

    def test_test_key_accepted(self):
        self.assertEqual(config.require_test_key({"LAPISITE_API_KEY": "lps_test_abc"}), "lps_test_abc")

    def test_default_base_is_test_api(self):
        self.assertEqual(config.api_base({}), "https://api-test.lapisite.com")
        self.assertEqual(config.api_base({"LAPISITE_API_BASE": "http://x"}), "http://x")

    def test_cli_refuses_bad_key(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"LAPISITE_API_KEY": "nope"}, clear=True), \
                mock.patch.object(config, "load_dotenv"):
            self.assertEqual(cli.main(["create-site"]), 2)


if __name__ == "__main__":
    unittest.main()

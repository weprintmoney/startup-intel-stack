import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import apify  # noqa: E402


class _Resp(io.BytesIO):
    """Minimal stand-in for urlopen's response context manager."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _json_resp(obj):
    return _Resp(json.dumps(obj).encode())


class TestActorPath(unittest.TestCase):
    def test_slash_to_tilde(self):
        self.assertEqual(apify.actor_path("harvestapi/linkedin-profile-search"), "harvestapi~linkedin-profile-search")

    def test_tilde_passthrough(self):
        self.assertEqual(apify.actor_path("compass~crawler-google-places"), "compass~crawler-google-places")

    def test_bad_slug(self):
        with self.assertRaises(apify.ApifyError):
            apify.actor_path("just-a-name")


class TestForbiddenKeys(unittest.TestCase):
    def test_clean_input(self):
        self.assertEqual(apify.forbidden_input_keys({"locations": ["Springfield"], "maxItems": 5}), [])

    def test_li_at_nested(self):
        found = apify.forbidden_input_keys({"proxy": {}, "auth": {"li_at": "x"}})
        self.assertEqual(found, ["auth.li_at"])

    def test_session_cookie_case_insensitive(self):
        self.assertEqual(apify.forbidden_input_keys({"sessionCookie": "abc"}), ["sessionCookie"])

    def test_start_run_refuses(self):
        with mock.patch.dict(os.environ, {"APIFY_API_KEY": "t"}):
            with self.assertRaises(apify.ApifyError):
                apify.start_run("u/a", {"cookies": []})


class TestRequests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"APIFY_API_KEY": "test-token", "APIFY_TOKEN": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_missing_token_raises(self):
        with mock.patch.dict(os.environ, {"APIFY_API_KEY": "", "APIFY_TOKEN": ""}):
            with self.assertRaises(apify.ApifyError):
                apify.get_run("r1")

    def test_legacy_token_name_accepted(self):
        with mock.patch.dict(os.environ, {"APIFY_API_KEY": "", "APIFY_TOKEN": "legacy"}):
            self.assertEqual(apify._token(), "legacy")

    def test_start_run_parses_id_and_dataset(self):
        with mock.patch("apify.urllib.request.urlopen") as uo:
            uo.return_value = _json_resp({"data": {"id": "run1", "defaultDatasetId": "ds1", "status": "RUNNING"}})
            out = apify.start_run("u/a", {"x": 1}, timeout_s=60)
            self.assertEqual(out, {"run_id": "run1", "dataset_id": "ds1", "status": "RUNNING"})
            req = uo.call_args[0][0]
            self.assertIn("/acts/u~a/runs", req.full_url)
            self.assertIn("timeout=60", req.full_url)
            self.assertEqual(req.get_header("Authorization"), "Bearer test-token")

    def test_wait_polls_until_terminal(self):
        statuses = iter(["RUNNING", "RUNNING", "SUCCEEDED"])
        with mock.patch("apify.urllib.request.urlopen") as uo:
            uo.side_effect = lambda *a, **k: _json_resp({"data": {"status": next(statuses), "defaultDatasetId": "ds1"}})
            slept = []
            data = apify.wait_for_run("run1", poll_s=5, max_wait_s=60, sleep=slept.append)
            self.assertEqual(data["status"], "SUCCEEDED")
            self.assertEqual(slept, [5, 5])

    def test_wait_failed_raises(self):
        with mock.patch("apify.urllib.request.urlopen") as uo:
            uo.return_value = _json_resp({"data": {"status": "FAILED"}})
            with self.assertRaises(apify.ApifyError):
                apify.wait_for_run("run1", poll_s=1, max_wait_s=5, sleep=lambda s: None)

    def test_wait_times_out(self):
        with mock.patch("apify.urllib.request.urlopen") as uo:
            uo.side_effect = lambda *a, **k: _json_resp({"data": {"status": "RUNNING"}})
            with self.assertRaises(apify.ApifyError):
                apify.wait_for_run("run1", poll_s=10, max_wait_s=20, sleep=lambda s: None)

    def test_fetch_items_paginates_and_caps(self):
        pages = [[{"i": n} for n in range(3)], [{"i": n} for n in range(3, 6)], [{"i": 6}]]
        calls = []
        with mock.patch("apify.urllib.request.urlopen") as uo:
            def fake(req, timeout=None):
                calls.append(req.full_url)
                return _json_resp(pages[len(calls) - 1])
            uo.side_effect = fake
            items = apify.fetch_items("ds1", max_items=5, page=3)
            self.assertEqual([x["i"] for x in items], [0, 1, 2, 3, 4])
            self.assertEqual(len(calls), 2)
            self.assertIn("limit=3&offset=0", calls[0])
            self.assertIn("limit=2&offset=3", calls[1])

    def test_fetch_items_stops_on_short_page(self):
        with mock.patch("apify.urllib.request.urlopen") as uo:
            uo.return_value = _json_resp([{"i": 1}])
            items = apify.fetch_items("ds1", max_items=100, page=50)
            self.assertEqual(items, [{"i": 1}])
            self.assertEqual(uo.call_count, 1)

    def test_http_error_wrapped(self):
        import urllib.error
        with mock.patch("apify.urllib.request.urlopen") as uo:
            uo.side_effect = urllib.error.HTTPError("u", 401, "nope", {}, io.BytesIO(b"bad token"))
            with self.assertRaises(apify.ApifyError) as cm:
                apify.get_run("run1")
            self.assertIn("HTTP 401", str(cm.exception))


class TestCli(unittest.TestCase):
    def _input_file(self, obj):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(obj, f)
        f.close()
        return f.name

    def test_missing_token_exits_1(self):
        path = self._input_file({"maxItems": 1})
        env = {"APIFY_API_KEY": "", "APIFY_TOKEN": ""}
        with mock.patch.dict(os.environ, env), mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = apify._cli(["run", "--actor", "u/a", "--input-file", path])
        self.assertEqual(rc, 1)
        self.assertIn("APIFY_API_KEY not set", out.getvalue())

    def test_dry_run_no_network(self):
        path = self._input_file({"locations": ["Springfield"]})
        with mock.patch("apify.urllib.request.urlopen") as uo, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = apify._cli(["run", "--actor", "u/a", "--input-file", path, "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(uo.call_count, 0)
        self.assertIn("/acts/u~a/runs", out.getvalue())

    def test_forbidden_key_exits_1_before_network(self):
        path = self._input_file({"li_at": "secret"})
        with mock.patch.dict(os.environ, {"APIFY_API_KEY": "t"}), mock.patch("apify.urllib.request.urlopen") as uo, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = apify._cli(["run", "--actor", "u/a", "--input-file", path])
        self.assertEqual(rc, 1)
        self.assertEqual(uo.call_count, 0)
        self.assertIn("refused", out.getvalue())


if __name__ == "__main__":
    unittest.main()

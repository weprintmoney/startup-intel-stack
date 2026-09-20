import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

if "requests" not in sys.modules:
    sys.modules["requests"] = types.ModuleType("requests")
_requests_mod = sys.modules["requests"]
if not hasattr(_requests_mod, "Response"):
    _requests_mod.Response = type("Response", (), {})
if not hasattr(_requests_mod, "get"):
    _requests_mod.get = lambda *a, **k: None
if not hasattr(_requests_mod, "post"):
    _requests_mod.post = lambda *a, **k: None


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import warmup  # noqa: E402


def _resp(status_code=200, text="ok"):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    return r


class TestDayNumber(unittest.TestCase):
    def test_empty_log_dir_is_day_1(self, tmp_path=None):
        with self._tmp_dir() as d:
            self.assertEqual(warmup.day_number(d), 1)

    def test_existing_logs_increment(self):
        with self._tmp_dir() as d:
            (d / "2026-01-01.json").write_text("{}")
            (d / "2026-01-02.json").write_text("{}")
            self.assertEqual(warmup.day_number(d), 3)

    def _tmp_dir(self):
        import contextlib
        import shutil
        import tempfile

        @contextlib.contextmanager
        def cm():
            p = Path(tempfile.mkdtemp())
            try:
                yield p
            finally:
                shutil.rmtree(p, ignore_errors=True)

        return cm()


class TestDailyCapForDay(unittest.TestCase):
    def test_day_1_is_20(self):
        self.assertEqual(warmup.daily_cap_for_day(1), 20)

    def test_day_7_boundary_is_20(self):
        self.assertEqual(warmup.daily_cap_for_day(7), 20)

    def test_day_8_is_40(self):
        self.assertEqual(warmup.daily_cap_for_day(8), 40)

    def test_day_14_boundary_is_40(self):
        self.assertEqual(warmup.daily_cap_for_day(14), 40)

    def test_day_15_is_50(self):
        self.assertEqual(warmup.daily_cap_for_day(15), 50)

    def test_day_28_is_50(self):
        self.assertEqual(warmup.daily_cap_for_day(28), 50)


class TestSetWarmupComplete(unittest.TestCase):
    @patch("warmup.subprocess.run")
    def test_check_true_passed_through(self, mock_run):
        warmup.set_warmup_complete("acme/startup-intel-stack", check=True)
        self.assertTrue(mock_run.call_args.kwargs["check"])

    @patch("warmup.subprocess.run")
    def test_check_false_passed_through(self, mock_run):
        warmup.set_warmup_complete("acme/startup-intel-stack", check=False)
        self.assertFalse(mock_run.call_args.kwargs["check"])

    @patch("warmup.subprocess.run")
    def test_command_shape(self, mock_run):
        warmup.set_warmup_complete("acme/startup-intel-stack", check=True)
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd[0], "gh")
        self.assertIn("repos/acme/startup-intel-stack/actions/variables/WARMUP_COMPLETE", cmd)


class TestSendWarmupBatch(unittest.TestCase):
    @patch("warmup.requests.post")
    def test_success_recorded(self, mock_post):
        mock_post.return_value = _resp(200)
        results = warmup.send_warmup_batch(
            ["a@x.com"], 1, 20, "key", "outreach@mail.example.com",
            sender_name="Acme Outreach", company_name="Acme",
        )
        self.assertEqual(results, [{"to": "a@x.com", "success": True, "error": None}])

    @patch("warmup.requests.post")
    def test_non_200_recorded_as_failure_with_body(self, mock_post):
        mock_post.return_value = _resp(500, "server error")
        results = warmup.send_warmup_batch(
            ["a@x.com"], 1, 20, "key", "outreach@mail.example.com",
            sender_name="Acme Outreach", company_name="Acme",
        )
        self.assertEqual(results, [{"to": "a@x.com", "success": False, "error": "server error"}])

    @patch("warmup.requests.post", side_effect=Exception("boom"))
    def test_exception_recorded_as_failure(self, mock_post):
        results = warmup.send_warmup_batch(
            ["a@x.com"], 1, 20, "key", "outreach@mail.example.com",
            sender_name="Acme Outreach", company_name="Acme",
        )
        self.assertEqual(results, [{"to": "a@x.com", "success": False, "error": "boom"}])

    @patch("warmup.requests.post")
    def test_cap_truncates_addresses(self, mock_post):
        mock_post.return_value = _resp(200)
        addrs = [f"a{i}@x.com" for i in range(5)]
        results = warmup.send_warmup_batch(
            addrs, 1, 2, "key", "outreach@mail.example.com",
            sender_name="Acme Outreach", company_name="Acme",
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(mock_post.call_count, 2)

    @patch("warmup.requests.post")
    def test_payload_shape(self, mock_post):
        mock_post.return_value = _resp(200)
        warmup.send_warmup_batch(
            ["a@x.com"], 3, 20, "key", "outreach@mail.example.com",
            sender_name="Acme Outreach", company_name="Acme",
        )
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["to"], ["a@x.com"])
        self.assertIn("day 3", kwargs["json"]["subject"])
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer key")


class TestRun(unittest.TestCase):
    def _tmp_dir(self):
        import contextlib
        import shutil
        import tempfile

        @contextlib.contextmanager
        def cm():
            p = Path(tempfile.mkdtemp())
            try:
                yield p
            finally:
                shutil.rmtree(p, ignore_errors=True)

        return cm()

    @patch("warmup.set_warmup_complete")
    def test_day_over_28_self_terminates_with_check_true(self, mock_set):
        with self._tmp_dir() as d:
            for i in range(29):
                (d / f"log{i}.json").write_text("{}")
            rc = warmup.run(
                d, seed_addresses=["a@x.com"], api_key="k", from_address="f@mail.example.com",
                repo="acme/startup-intel-stack", today="2026-09-12",
                sender_name="Acme Outreach", company_name="Acme",
            )
            self.assertEqual(rc, 0)
            mock_set.assert_called_once_with("acme/startup-intel-stack", check=True)
            self.assertEqual(sorted(d.glob("*.json")), sorted(d / f"log{i}.json" for i in range(29)))

    @patch("warmup.set_warmup_complete")
    def test_no_seed_addresses_skips_without_writing_log(self, mock_set):
        with self._tmp_dir() as d:
            rc = warmup.run(
                d, seed_addresses=[], api_key="k", from_address="f@mail.example.com",
                repo="acme/startup-intel-stack", today="2026-09-12",
                sender_name="Acme Outreach", company_name="Acme",
            )
            self.assertEqual(rc, 0)
            mock_set.assert_not_called()
            self.assertEqual(list(d.glob("*.json")), [])

    @patch("warmup.set_warmup_complete")
    @patch("warmup.requests.post")
    def test_normal_day_writes_log_and_does_not_set_complete(self, mock_post, mock_set):
        mock_post.return_value = _resp(200)
        with self._tmp_dir() as d:
            rc = warmup.run(
                d, seed_addresses=["a@x.com", "b@x.com"], api_key="k", from_address="f@mail.example.com",
                repo="acme/startup-intel-stack", today="2026-09-12",
                sender_name="Acme Outreach", company_name="Acme",
            )
            self.assertEqual(rc, 0)
            mock_set.assert_not_called()
            log = json.loads((d / "2026-09-12.json").read_text())
            self.assertEqual(log["day_number"], 1)
            self.assertEqual(log["daily_cap"], 20)
            self.assertEqual(log["sent"], 2)
            self.assertEqual(len(log["results"]), 2)

    @patch("warmup.set_warmup_complete")
    @patch("warmup.requests.post")
    def test_day_28_sets_complete_with_check_false_after_logging(self, mock_post, mock_set):
        mock_post.return_value = _resp(200)
        with self._tmp_dir() as d:
            for i in range(27):
                (d / f"log{i}.json").write_text("{}")
            rc = warmup.run(
                d, seed_addresses=["a@x.com"], api_key="k", from_address="f@mail.example.com",
                repo="acme/startup-intel-stack", today="2026-09-12",
                sender_name="Acme Outreach", company_name="Acme",
            )
            self.assertEqual(rc, 0)
            mock_set.assert_called_once_with("acme/startup-intel-stack", check=False)
            self.assertTrue((d / "2026-09-12.json").exists())

    @patch("warmup.set_warmup_complete")
    @patch("warmup.requests.post")
    def test_day_27_does_not_set_complete(self, mock_post, mock_set):
        mock_post.return_value = _resp(200)
        with self._tmp_dir() as d:
            for i in range(26):
                (d / f"log{i}.json").write_text("{}")
            warmup.run(
                d, seed_addresses=["a@x.com"], api_key="k", from_address="f@mail.example.com",
                repo="acme/startup-intel-stack", today="2026-09-12",
                sender_name="Acme Outreach", company_name="Acme",
            )
            mock_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()

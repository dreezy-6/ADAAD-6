import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adaad6.assurance.doctor import run_doctor
from adaad6.config import AdaadConfig, ResourceTier
from adaad6.provenance.ledger import read_events


class DoctorTest(unittest.TestCase):
    @patch("adaad6.assurance.doctor._run_pytest_check", autospec=True, return_value={"ok": True})
    def test_run_doctor_reports_schema_version_and_ledger_skip(self, _run_pytest_mock) -> None:
        cfg = AdaadConfig(ledger_enabled=False, log_schema_version="9")

        report = run_doctor(cfg=cfg)

        self.assertEqual("9", report["schema_version"])
        self.assertTrue(report["checks"]["config"]["ok"])
        self.assertTrue(report["checks"]["health"]["ok"])
        self.assertTrue(report["checks"]["ledger"]["skipped"])
        self.assertFalse(report["ledger_event"]["appended"])
        self.assertTrue(report["run_id"])
        _run_pytest_mock.assert_called_once_with(cfg)
        self.assertTrue(report["ok"])

    @patch("adaad6.assurance.doctor.append_event", autospec=True)
    @patch("adaad6.assurance.doctor.ensure_ledger")
    @patch("adaad6.assurance.doctor._run_pytest_check", autospec=True, return_value={"ok": True})
    def test_run_doctor_checks_ledger_when_enabled(self, _run_pytest_mock, ensure_ledger_mock, append_event_mock) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_path = Path(tmpdir) / ".adaad" / "ledger" / "events.jsonl"
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text("", encoding="utf-8")
            ensure_ledger_mock.return_value = ledger_path
            append_event_mock.return_value = {"event_id": "id", "hash": "h"}
            cfg = AdaadConfig(ledger_enabled=True, resource_tier=ResourceTier.EDGE, home=tmpdir)

            report = run_doctor(cfg=cfg)

            ensure_ledger_mock.assert_called_once()
            append_event_mock.assert_called_once()
            args, kwargs = append_event_mock.call_args
            self.assertEqual(cfg, kwargs["cfg"])
            self.assertEqual("doctor", kwargs["event_type"])
            self.assertEqual("doctor", kwargs["actor"])
            payload = kwargs["payload"]
            self.assertEqual("doctor", payload["action"])
            self.assertTrue(payload["overall_ok"])
            self.assertTrue(payload["run_id"])
            self.assertEqual(cfg.resource_tier.value, payload["resource_tier"])
            self.assertIn("checks_summary", payload)
            self.assertTrue(report["checks"]["ledger"]["ok"])
            self.assertTrue(report["checks"]["static_scan"]["ok"])
            self.assertTrue(report["ledger_event"]["appended"])
            self.assertEqual(payload["run_id"], report["run_id"])
            _run_pytest_mock.assert_called_once_with(cfg)
            self.assertTrue(report["ok"])

    @patch("adaad6.assurance.doctor._run_pytest_check", autospec=True, return_value={"ok": True})
    def test_static_scan_detects_forbidden_modules(self, _run_pytest_mock) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "module.py").write_text("import socket\n", encoding="utf-8")
            self.assertTrue((root / "module.py").exists())
            cfg = AdaadConfig(ledger_enabled=False, resource_tier=ResourceTier.MOBILE)

            report = run_doctor(cfg=cfg, scan_root=root)

            static_scan = report["checks"]["static_scan"]
            self.assertFalse(static_scan["ok"])
            self.assertEqual([{"module": "socket", "path": "module.py"}], static_scan["forbidden"])
            self.assertEqual(cfg.resource_tier.value, static_scan["tier"])
            _run_pytest_mock.assert_called_once_with(cfg)

    @patch("adaad6.assurance.doctor._run_pytest_check", autospec=True, return_value={"ok": True})
    def test_run_doctor_appends_event_to_ledger(self, _run_pytest_mock) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            ledger_path = home / ".adaad" / "ledger" / "events.jsonl"
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text("", encoding="utf-8")
            cfg = AdaadConfig(
                home=str(home),
                ledger_enabled=True,
                ledger_dir=".adaad/ledger",
                ledger_filename="events.jsonl",
                resource_tier=ResourceTier.EDGE,
            )

            report = run_doctor(cfg=cfg, scan_root=home)

            self.assertTrue(report["ok"])
            self.assertTrue(report["ledger_event"]["appended"])
            events = read_events(cfg)
            doctor_events = [e for e in events if e.get("type") == "doctor"]
            self.assertTrue(len(doctor_events) >= 1)
            self.assertEqual("doctor", doctor_events[-1]["actor"])
            self.assertTrue(doctor_events[-1]["payload"]["overall_ok"])
            self.assertEqual(report["run_id"], doctor_events[-1]["payload"].get("run_id"))
            _run_pytest_mock.assert_called_once_with(cfg)

    def test_run_doctor_fails_when_telemetry_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = AdaadConfig(
                home=tmpdir,
                ledger_enabled=False,
                telemetry_exports=("telemetry/metrics.jsonl",),
            )

            report = run_doctor(cfg=cfg, scan_root=Path(tmpdir))

            self.assertFalse(report["ok"])
            self.assertFalse(report["checks"]["health"]["ok"])
            self.assertTrue(report["checks"]["ledger"]["ok"])
            self.assertFalse(report["checks_summary"]["health"]["ok"])
            self.assertTrue(report["checks_summary"]["ledger"]["ok"])

            telemetry_path = Path(tmpdir) / "telemetry" / "metrics.jsonl"
            telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            telemetry_path.write_text("{}", encoding="utf-8")

            recovered = run_doctor(cfg=cfg, scan_root=Path(tmpdir))

            self.assertTrue(recovered["ok"])
            self.assertTrue(recovered["checks"]["health"]["ok"])

    @patch("adaad6.assurance.doctor.run_doctor", autospec=True, return_value={"ok": True, "run_id": "lazy"})
    def test_lazy_run_doctor_export_calls_real_impl(self, doctor_mock) -> None:
        import adaad6.assurance as assurance

        result = assurance.run_doctor(cfg="cfg")

        doctor_mock.assert_called_once_with(cfg="cfg")
        self.assertEqual("lazy", result["run_id"])


if __name__ == "__main__":
    unittest.main()

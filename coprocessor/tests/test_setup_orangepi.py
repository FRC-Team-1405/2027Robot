"""Exercise the installer in a PTY with fake apt/systemd/sudo, never touching /etc.

Run: python3 -m unittest discover -s coprocessor/tests -v
"""
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / "setup-orangepi.sh"
MOCK = r'''#!/usr/bin/python3
import os, pathlib, subprocess, sys
root = pathlib.Path(os.environ["TEST_ROOT"])
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / "commands").open("a") as log:
    log.write(name + " " + " ".join(args) + "\n")
def mapped(value):
    return str(root / "etc" / value[5:]) if value.startswith("/etc/") else value
if name == "sudo":
    if args == ["-v"]: sys.exit(0)
    if args[0] == "test":
        sys.exit(0 if pathlib.Path(mapped(args[-1])).is_file() else 1)
    sys.exit(subprocess.call([mapped(x) for x in args]))
if name == "apt-get" or name == "sleep": sys.exit(0)
if name == "id":
    print(os.environ.get("MOCK_LOGIN", "pi")); sys.exit(0)
if name == "journalctl":
    print("MOCK JOURNAL: " + " ".join(args)); sys.exit(0)
if name == "systemctl":
    unit = next((x for x in args if x.endswith(".service")), "")
    template = "orangepi-vision-recorder@.service" if "recorder@" in unit else unit
    installed = unit == "photonvision.service" or (root / "etc/systemd/system" / template).is_file()
    failed = os.environ.get("FAIL_UNIT") == unit
    if args[0] == "show":
        if "LoadState" in args: print("loaded" if installed else "not-found")
        elif "NRestarts" in args:
            counter = root / "restart_count"
            count = int(counter.read_text()) if counter.exists() else 0
            if os.environ.get("RESTART_LOOP") == unit:
                count += 1; counter.write_text(str(count))
            print(count)
        else: print("ExecStart=mock venv; NRestarts=0")
    elif args[0] in ("is-active", "is-enabled"):
        sys.exit(0 if installed and not failed else 3)
    elif "status" in args:
        print("Active: " + ("failed" if failed else "active (running)"))
    sys.exit(0)
if name == "python3":
    if args[:2] == ["-m", "venv"]:
        bindir = pathlib.Path(args[2]) / "bin"; bindir.mkdir(parents=True, exist_ok=True)
        shutil = __import__("shutil")
        shutil.copy2(sys.argv[0], bindir / "python3"); sys.exit(0)
    if args[:2] == ["-m", "pip"]:
        if "install" in args:
            if os.environ.get("FAIL_PIP"): sys.exit(1)
            (root / "ntcore-installed").touch()
        sys.exit(0)
    if args[:1] == ["-c"]:
        if not (root / "ntcore-installed").exists(): sys.exit(1)
        print("ntcore import: OK"); sys.exit(0)
    if args[:1] == ["-"]:
        # Keep stream checks deterministic/offline; source/quoting is checked separately.
        print("Stream responds: mock raw MJPEG")
        sys.exit(1 if os.environ.get("FAIL_STREAM") else 0)
sys.exit(2)
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="orangepi-setup-"))
        self.source = self.root / "coprocessor"
        self.source.mkdir()
        (self.root / "etc/systemd/system").mkdir(parents=True)
        for file in SCRIPT.parent.iterdir():
            if file.is_file():
                shutil.copy2(file, self.source / file.name)
        # Some containers map only uid 0. Remove only the root guard in this
        # isolated fixture; production refusal is tested separately below.
        if os.getuid() == 0:
            fixture = self.source / SCRIPT.name
            guard = "[[ $EUID -ne 0 ]] || die 'Run bash setup-orangepi.sh as SSH user pi, without sudo.'"
            self.assertIn(guard, fixture.read_text())
            fixture.write_text(fixture.read_text().replace(guard, ": # root-only test fixture"))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        mock = self.bin / "mock"
        mock.write_text(MOCK)
        mock.chmod(0o755)
        for command in ("sudo", "apt-get", "python3", "systemctl", "journalctl", "sleep", "id"):
            (self.bin / command).symlink_to(mock)
        self.env = dict(os.environ, HOME=str(self.root), TEST_ROOT=str(self.root),
                        PATH=f"{self.bin}:/usr/bin:/bin")

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_script(self, args=(), replies=()):
        master, slave = pty.openpty()
        proc = subprocess.Popen(["bash", str(self.source / SCRIPT.name), *args],
                                stdin=slave, stdout=slave, stderr=slave,
                                env=self.env)
        os.close(slave)
        output = b""
        deadline = time.monotonic() + 15
        pending = list(replies)
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                if pending and pending[0][0].encode() in output:
                    _, reply = pending.pop(0)
                    os.write(master, (reply + "\n").encode())
                if proc.poll() is not None and not ready:
                    break
            try:
                rc = proc.wait(timeout=max(1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.fail(f"Installer timed out: {output.decode()}")
            return rc, output.decode()
        finally:
            os.close(master)

    def install(self, choice="1", cameras=()):
        replies = [("Install which services?", choice),
                   ("restart selected services?", "y")]
        replies.extend(cameras)
        return self.run_script(replies=replies)

    def commands(self):
        return (self.root / "commands").read_text()

    def test_metrics_fresh_install_renders_venv_and_boot_service(self):
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        unit = (self.root / "etc/systemd/system/orangepi-nt-publisher.service").read_text()
        self.assertIn(f"ExecStart={self.root}/.venv-ntpublisher/bin/python3 {self.root}/orangepi-nt-publisher.py", unit)
        self.assertIn("apt-get install -y python3-venv", self.commands())
        self.assertIn("python3 -m pip install pyntcore", self.commands())
        self.assertIn("systemctl enable orangepi-nt-publisher.service", self.commands())

    def test_both_cameras_then_rerun_preserves_configuration_and_works_offline(self):
        rc, out = self.install("3", [("URL for left", "http://localhost:1183/stream.mjpg"),
                                     ("URL for right", "http://localhost:1181/stream.mjpg")])
        self.assertEqual(rc, 0, out)
        envfile = self.root / "etc/orangepi-vision-recorder/left.env"
        self.assertIn(f"RECORDINGS_DIR={self.root}/vision-recordings", envfile.read_text())
        custom = "CAMERA_STREAM_URL=http://localhost:1200/stream.mjpg\nRECORDINGS_DIR=/mnt/custom\n"
        envfile.write_text(custom)
        (self.root / "commands").write_text("")
        rc, out = self.install("3")
        self.assertEqual(rc, 0, out)
        self.assertEqual(envfile.read_text(), custom)
        self.assertNotIn("apt-get ", self.commands())
        self.assertNotIn("pip install", self.commands())
        for camera in ("left", "right"):
            self.assertIn(f"systemctl restart orangepi-vision-recorder@{camera}.service", self.commands())

    def test_pip_failure_reports_phase_and_does_not_start_services(self):
        self.env["FAIL_PIP"] = "1"
        rc, out = self.install()
        self.assertNotEqual(rc, 0)
        self.assertIn("ERROR during Python virtual environment", out)
        self.assertIn("MOCK JOURNAL", out)
        self.assertNotIn("systemctl restart", self.commands())

    def test_other_login_is_rejected_before_installation(self):
        self.env["MOCK_LOGIN"] = "photon"
        rc, out = self.run_script()
        self.assertNotEqual(rc, 0)
        self.assertIn("correct SSH account is pi", out)
        self.assertNotIn("sudo ", self.commands())
        self.assertNotIn("apt-get", self.commands())

    def test_legacy_camera_config_gets_current_home_without_changing_url(self):
        folder = self.root / "etc/orangepi-vision-recorder"
        folder.mkdir()
        (folder / "left.env").write_text("CAMERA_STREAM_URL=http://localhost:1193/stream.mjpg\n")
        rc, out = self.install("2", [("URL for right", "")])
        self.assertEqual(rc, 0, out)
        content = (folder / "left.env").read_text()
        self.assertIn("CAMERA_STREAM_URL=http://localhost:1193/stream.mjpg", content)
        self.assertIn(f"RECORDINGS_DIR={self.root}/vision-recordings", content)

    def test_rerun_installs_changed_scripts_and_units_then_reloads_and_restarts(self):
        rc, out = self.install("3", [("URL for left", "http://localhost:1183/stream.mjpg"),
                                     ("URL for right", "http://localhost:1181/stream.mjpg")])
        self.assertEqual(rc, 0, out)
        for name in ("orangepi-nt-publisher", "orangepi-vision-recorder"):
            script = self.source / f"{name}.py"
            script.write_text(script.read_text() + "\n# Updated deployment revision\n")
            unit = self.source / (f"{name}@.service" if "recorder" in name else f"{name}.service")
            unit.write_text(unit.read_text().replace("[Service]", "[Service]\nEnvironment=DEPLOYMENT_REVISION=2"))
        (self.root / "commands").write_text("")
        rc, out = self.install("3")
        self.assertEqual(rc, 0, out)
        for name in ("orangepi-nt-publisher", "orangepi-vision-recorder"):
            self.assertEqual((self.root / f"{name}.py").read_text(), (self.source / f"{name}.py").read_text())
            filename = f"{name}@.service" if "recorder" in name else f"{name}.service"
            self.assertIn("Environment=DEPLOYMENT_REVISION=2", (self.root / "etc/systemd/system" / filename).read_text())
        commands = self.commands()
        reload_at = commands.index("systemctl daemon-reload")
        for unit in ("orangepi-nt-publisher", "orangepi-vision-recorder@left", "orangepi-vision-recorder@right"):
            self.assertGreater(commands.index(f"systemctl restart {unit}.service"), reload_at)
        self.assertNotIn("pip install", commands)

    def test_service_failure_reports_journal(self):
        self.env["FAIL_UNIT"] = "orangepi-nt-publisher.service"
        rc, out = self.install()
        self.assertNotEqual(rc, 0)
        self.assertIn("not active", out)
        self.assertIn("MOCK JOURNAL", out)
        self.assertNotIn("Setup checks passed", out)

    def test_restart_loop_is_detected(self):
        self.env["RESTART_LOOP"] = "orangepi-nt-publisher.service"
        rc, out = self.install()
        self.assertNotEqual(rc, 0)
        self.assertIn("restarted during startup", out)

    def test_status_and_logs_do_not_mutate_installation(self):
        rc, out = self.install()
        self.assertEqual(rc, 0, out)
        (self.root / "commands").write_text("")
        for mode in ("--status", "--logs"):
            rc, out = self.run_script((mode,))
            self.assertEqual(rc, 0, out)
        commands = self.commands()
        for forbidden in ("apt-get", "pip install", "systemctl restart", "systemctl enable", "sudo install"):
            self.assertNotIn(forbidden, commands)

    def test_bad_stream_can_be_skipped_without_starting_a_recorder(self):
        self.env["FAIL_STREAM"] = "1"
        rc, out = self.install("2", [("URL for left", "http://localhost:1183/stream.mjpg"),
                                     ("Install left anyway", "n"), ("URL for right", "")])
        self.assertEqual(rc, 0, out)
        self.assertIn("No services selected", out)
        self.assertNotIn("systemctl restart", self.commands())

    @unittest.skipUnless(os.getuid() == 0, "root guard applies only to root")
    def test_production_script_refuses_root_before_changes(self):
        result = subprocess.run(["bash", str(SCRIPT)], env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("without sudo", result.stderr)
        self.assertNotIn("sudo ", self.commands() if (self.root / "commands").exists() else "")


class StreamProbeTests(unittest.TestCase):
    def probe(self, env, content_type="multipart/x-mixed-replace", error=None):
        code = SCRIPT.read_text().split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "camera.env"
            path.write_text(env)
            response = MagicMock()
            response.__enter__.return_value.headers = {"Content-Type": content_type}
            with patch("sys.argv", ["probe", str(path)]), patch("urllib.request.urlopen", return_value=response, side_effect=error) as request:
                try:
                    exec(compile(code, "stream-check", "exec"), {})
                except SystemExit as exc:
                    return exc.code, request
                return 0, request

    def test_quoted_systemd_url_is_parsed_without_sourcing_shell(self):
        rc, request = self.probe('# comment\nCAMERA_STREAM_URL="http://localhost:1183/stream.mjpg"\nOTHER=$(false)\n')
        self.assertEqual(rc, 0)
        request.assert_called_once_with("http://localhost:1183/stream.mjpg", timeout=5)

    def test_html_is_not_a_camera_stream(self):
        rc, _ = self.probe("CAMERA_STREAM_URL=http://localhost:5800\n", "text/html")
        self.assertEqual(rc, 1)

    def test_timeout_returns_failure(self):
        rc, _ = self.probe("CAMERA_STREAM_URL=http://localhost:1183/stream.mjpg\n", error=TimeoutError("timed out"))
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()

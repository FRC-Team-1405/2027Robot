"""SSH and SCP to an Orange Pi, with the same options and team key Bootstrap-OrangePi.ps1 uses.

Uses the OpenSSH client (``ssh``/``scp``), which ships with Windows 10+, macOS and Linux. The team
key is ``~/.ssh/id_ed25519_orangepi``; the bootstrap copies it there on first use.

Remote paths are relative to the Pi user's home (``bench/code``), which both ssh and scp accept.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence

USER = "pi"
KEY = Path.home() / ".ssh" / "id_ed25519_orangepi"


class RemoteError(RuntimeError):
    pass


def ssh_options(key: Path = KEY) -> list[str]:
    return ["-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=15", "-i", str(key), "-o", "IdentitiesOnly=yes"]


class Pi:
    """One board. ``host`` is picked from the board's hosts on first use (the first that answers)."""

    def __init__(self, name: str, hosts: Sequence[str], user: str = USER, key: Path = KEY,
                 run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 popen: Callable[..., subprocess.Popen] = subprocess.Popen):
        self.name, self.hosts, self.user, self.key = name, list(hosts), user, key
        self._run, self._popen = run, popen
        self.host: str | None = None

    # ------------------------------------------------------------------ connection

    def connect(self) -> str:
        if self.host:
            return self.host
        if not self.key.exists():
            raise RemoteError(
                f"no SSH key at {self.key}. Run coprocessor/Bootstrap-OrangePi.ps1 once on this laptop "
                "(it copies the team key there), or copy coprocessor/ssh/id_ed25519_orangepi yourself.")
        if not shutil.which("ssh") or not shutil.which("scp"):
            raise RemoteError("ssh/scp not found (Windows: Settings > Optional features > OpenSSH Client)")
        tried = []
        for h in self.hosts:
            r = self._run(["ssh", *ssh_options(self.key), f"{self.user}@{h}", "true"],
                          capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                self.host = h
                return h
            tried.append(f"{h}: {(r.stderr or '').strip().splitlines()[-1:] or ['no answer']}")
        raise RemoteError(f"{self.name}: can't reach it over SSH ({'; '.join(tried)})")

    def _target(self) -> str:
        return f"{self.user}@{self.connect()}"

    # ------------------------------------------------------------------ commands

    def check(self, command: str, timeout: float = 60) -> str:
        """Runs a short command; raises with its output if it fails."""
        r = self._run(["ssh", *ssh_options(self.key), self._target(), command],
                      capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RemoteError(f"{self.name}: `{command}` failed ({r.returncode}): {(r.stderr or r.stdout).strip()}")
        return r.stdout

    def stream(self, command: str, log_path: Path | None = None, echo: Callable[[str], None] | None = None) -> int:
        """Runs a long command, printing its output as it comes and saving it to ``log_path``."""
        echo = echo or (lambda line: print(f"  [{self.name}] {line}", flush=True))
        p = self._popen(["ssh", *ssh_options(self.key), self._target(), command],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding="utf-8", errors="replace", bufsize=1)
        log = open(log_path, "w", encoding="utf-8") if log_path else None
        try:
            assert p.stdout is not None
            for line in p.stdout:
                line = line.rstrip("\n")
                echo(line)
                if log:
                    log.write(line + "\n")
            return p.wait()
        finally:
            if log:
                log.close()

    # ------------------------------------------------------------------ files

    def put_dir(self, local: Path, remote: str) -> None:
        """Replaces ``remote`` (relative to home) with a copy of ``local``."""
        parent = remote.rsplit("/", 1)[0] if "/" in remote else "."
        self.check(f"mkdir -p {parent} && rm -rf {remote}")
        r = self._run(["scp", *ssh_options(self.key), "-r", "-q", str(local), f"{self._target()}:{remote}"],
                      capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RemoteError(f"{self.name}: copying {local} failed: {r.stderr.strip()}")

    def get_dir(self, remote: str, local: Path) -> None:
        """Copies ``remote`` (relative to home) to ``local``, replacing what was there."""
        with tempfile.TemporaryDirectory(dir=local.parent if local.parent.exists() else None) as tmp:
            r = self._run(["scp", *ssh_options(self.key), "-r", "-q", f"{self._target()}:{remote}", tmp],
                          capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                raise RemoteError(f"{self.name}: fetching {remote} failed: {r.stderr.strip()}")
            got = Path(tmp) / remote.rstrip("/").rsplit("/", 1)[-1]
            if not got.exists():
                raise RemoteError(f"{self.name}: {remote} came back empty")
            if local.exists():
                shutil.rmtree(local)
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(got), str(local))


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)

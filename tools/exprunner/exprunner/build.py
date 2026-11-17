"""Builds the bench bundle that gets copied to each Pi: ``run.sh`` plus FrameCost compiled for Java 17.

FrameCost is compiled on the laptop against WPILib's jars (from the WPILib install or the Gradle cache,
both present on any laptop that builds the robot code). On the Pi it runs against PhotonVision's own
jar, which carries the same classes and the native libraries.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BENCH_SRC = REPO / "coprocessor" / "bench"
BUILD_DIR = Path(__file__).resolve().parents[1] / "build" / "bench"

# Compile-time dependencies of FrameCost.java: (artifact, path fragment that identifies it).
JARS = ("apriltag-java", "wpimath-java", "wpiutil-java", "wpiunits-java", "opencv-java")


class BuildError(RuntimeError):
    pass


def _wpilib_homes() -> list[Path]:
    roots = [Path("C:/Users/Public/wpilib"), Path.home() / "wpilib"]
    homes = []
    for r in roots:
        if r.is_dir():
            homes += sorted((p for p in r.iterdir() if p.is_dir() and p.name.isdigit()), reverse=True)
    return homes


def find_javac() -> str:
    exe = "javac.exe" if os.name == "nt" else "javac"
    candidates = []
    if os.environ.get("JAVAC"):
        candidates.append(Path(os.environ["JAVAC"]))
    candidates += [h / "jdk" / "bin" / exe for h in _wpilib_homes()]
    if os.environ.get("JAVA_HOME"):
        candidates.append(Path(os.environ["JAVA_HOME"]) / "bin" / exe)
    for c in candidates:
        if c.is_file():
            return str(c)
    found = shutil.which("javac")
    if found:
        return found
    raise BuildError("no javac found: install WPILib (it brings a JDK) or set JAVAC")


def _version_key(path: Path, artifact: str) -> tuple:
    m = re.search(re.escape(artifact) + r"-([0-9][0-9A-Za-z.\-]*)\.jar$", path.name)
    parts = re.findall(r"\d+", m.group(1)) if m else []
    return tuple(int(p) for p in parts)


def find_jars() -> list[str]:
    roots = [h / "maven" for h in _wpilib_homes()] + [Path.home() / ".gradle" / "caches" / "modules-2" / "files-2.1"]
    out = []
    for artifact in JARS:
        found: list[Path] = []
        for root in roots:
            if root.is_dir():
                found += [p for p in root.rglob(f"{artifact}-*.jar")
                          if not re.search(r"-(sources|javadoc)\.jar$", p.name)
                          and re.fullmatch(re.escape(artifact) + r"-[0-9][0-9.\-]*\.jar", p.name)]
        if not found:
            raise BuildError(f"{artifact} jar not found under {', '.join(map(str, roots))}; "
                             "build the robot code once (it downloads them) or install WPILib")
        out.append(str(max(found, key=lambda p: _version_key(p, artifact))))
    return out


def git_describe() -> dict:
    def git(*a: str) -> str:
        try:
            return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip()
        except OSError:
            return ""
    return {"sha": git("rev-parse", "--short=12", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(git("status", "--porcelain"))}


def stage(dest: Path = BUILD_DIR, log=print) -> Path:
    """Fresh bundle in ``dest``: run.sh, README.md, classes/, BUILD.txt. Returns ``dest``."""
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "classes").mkdir(parents=True)
    javac = find_javac()
    jars = find_jars()
    cmd = [javac, "--release", "17", "-nowarn", "-encoding", "UTF-8", "-cp", os.pathsep.join(jars),
           "-d", str(dest / "classes"), str(BENCH_SRC / "java" / "FrameCost.java")]
    log(f"compiling FrameCost with {javac}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    errors = [ln for ln in (r.stderr or "").splitlines() if "Visibility" not in ln and not ln.startswith("warning")
              and not re.match(r"^\d+ warnings?$", ln.strip())]
    if r.returncode != 0:
        raise BuildError("javac failed:\n" + "\n".join(errors))
    for name in ("run.sh", "README.md"):
        src = BENCH_SRC / name
        if src.exists():
            # LF line endings whatever the checkout did: bash on the Pi chokes on CR.
            (dest / name).write_bytes(src.read_bytes().replace(b"\r\n", b"\n"))
    g = git_describe()
    (dest / "BUILD.txt").write_text(
        f"built {datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} from {g['branch']} @ {g['sha']}"
        f"{' (uncommitted changes)' if g['dirty'] else ''}\njars: {', '.join(Path(j).name for j in jars)}\n",
        encoding="utf-8", newline="\n")
    return dest


if __name__ == "__main__":
    try:
        print(stage())
    except BuildError as e:
        sys.exit(str(e))

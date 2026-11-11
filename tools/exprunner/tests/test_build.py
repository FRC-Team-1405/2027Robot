"""Compiles the real bench program, so a broken FrameCost.java is caught on the laptop, not the Pi."""
import pytest

from exprunner import build


def _toolchain():
    try:
        return build.find_javac(), build.find_jars()
    except build.BuildError as e:
        pytest.skip(f"no Java toolchain here: {e}")


def test_stage_builds_bundle(tmp_path):
    _toolchain()
    out = build.stage(tmp_path / "bench", log=lambda m: None)
    assert (out / "classes" / "FrameCost.class").exists()
    run_sh = (out / "run.sh").read_bytes()
    assert run_sh.startswith(b"#!/usr/bin/env bash") and b"\r\n" not in run_sh
    assert "built" in (out / "BUILD.txt").read_text()


def test_find_jars_picks_newest(tmp_path, monkeypatch):
    root = tmp_path / "maven"
    for v in ("2026.1.1", "2026.2.1", "2025.3.2"):
        d = root / v
        d.mkdir(parents=True)
        for a in build.JARS:
            (d / f"{a}-{v}.jar").write_text("")
            (d / f"{a}-{v}-sources.jar").write_text("")
    # The search looks in <wpilib home>/maven and ~/.gradle; point both at the fake tree.
    monkeypatch.setattr(build, "_wpilib_homes", lambda: [tmp_path])
    monkeypatch.setattr(build.Path, "home", lambda: tmp_path / "nohome")
    jars = build.find_jars()
    assert all("2026.2.1" in j and "sources" not in j for j in jars)

"""Pytest fixtures bersama untuk ZYWtool.

Semua tes pakai tmp_path (terisolasi per test) -> tidak ada sisa state di disk
yang bikin tes flaky (masalah di test_gui.py lama).
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
HELPERS = os.path.join(ROOT, "tests", "helpers")
if HELPERS not in sys.path:
    sys.path.insert(0, HELPERS)

from make_fixture import (  # noqa: E402
    make_session,
)

from zywtool import handcheck, zyw_core  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_reports(tmp_path, monkeypatch):
    """Arahkan folder output proyek ke tmp_path supaya tes tidak menulis ke
    folder proyek (hand_check/reports, logs/) dan tidak flaky karena sisa state.

    Lokasi HARUS konsisten dengan env ZYWTOOL_* yang dipakai subprocess GUI
    (test_gui.gui_env): subprocess menulis ke <tmp>/... yang sama.
    """
    monkeypatch.setattr(handcheck, "REPORT_DIR", str(tmp_path / "hand_check" / "reports"))
    monkeypatch.setattr(zyw_core, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("ZYWTOOL_LOG_DIR", str(tmp_path / "logs"))
    yield
    monkeypatch.undo()


@pytest.fixture
def cfg(tmp_path):
    from zywtool import zyw_core as core

    c = core.load_config()
    # arahkan Excel ke tmp agar tidak menyentuh file pengguna
    c["excel_path"] = str(tmp_path / "out.xlsx")
    return c


@pytest.fixture
def make_sessions(tmp_path):
    """Buat N sesi sintetis di folder root; kembalikan (root, [path...])."""

    def _make(n=1, *, corrupt_idx=(), **kw):
        root = tmp_path / "scan_root"
        root.mkdir(exist_ok=True)
        paths = []
        for i in range(n):
            name = f"session_{i:05d}-fix{i}"
            paths.append(make_session(str(root), name=name, **kw))
        return str(root), paths

    return _make

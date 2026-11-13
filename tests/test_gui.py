"""Tes GUI headless + JobManager + alur scan->arrange->preview->handcheck->stop.

Isolasi penuh: folder logs/hand_check/reports/preview dialihkan ke tmp_path lewat env
ZWYTOOL_* (lihat zyw_core/handcheck/preview_frames/jobs) supaya tidak menulis ke proyek
dan tidak flaky karena sisa state disk. Tk hanya diakses dari thread utama.

Menggantikan test_gui.py lama (yang flaky karena menulis ke folder proyek).
PENTING: JobManager berjalan lewat root.after, jadi tes HARUS memompa event loop Tk
(helper pump) supaya _tick berjalan; time.sleep saja tidak cukup.
"""
import os
import shutil
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELPERS = os.path.join(ROOT, "tests", "helpers")
for p in (ROOT, HELPERS):
    if p not in sys.path:
        sys.path.insert(0, p)

from make_fixture import make_session  # noqa: E402


@pytest.fixture
def gui_env(tmp_path, monkeypatch):
    """Alihkan semua folder output proyek ke tmp_path sebelum import modul proyek."""
    t = str(tmp_path)
    monkeypatch.setenv("ZYWTOOL_LOG_DIR", os.path.join(t, "logs"))
    monkeypatch.setenv("ZYWTOOL_HAND_CHECK_DIR", os.path.join(t, "hand_check"))
    monkeypatch.setenv("ZYWTOOL_PREVIEW_DIR", os.path.join(t, "preview"))
    monkeypatch.setenv("ZYWTOOL_JOB_LOG_DIR", os.path.join(t, "jobs"))
    from zywtool import zywtool  # noqa: E402
    from zywtool import jobs  # noqa: E402
    from zywtool import handcheck  # noqa: E402
    import zyw_core  # noqa: E402
    return dict(zywtool=zywtool, jobs=jobs, handcheck=handcheck, zyw_core=zyw_core)


def _tk_env():
    """Root Tk tersembunyi + messagebox di-mock (jangan ada dialog yang memblokir)."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    calls = []
    ASK = {"v": False}

    _OrigTop = tk.Toplevel
    tk.Toplevel = lambda *a, **k: _OrigTop(*a, **k).withdraw()
    for n in ("showinfo", "showwarning", "showerror"):
        setattr(messagebox, n, lambda *a, n=n, **k: calls.append((n, " ".join(str(x) for x in a))))
    messagebox.askyesno = lambda *a, **k: (calls.append(("askyesno", " ".join(str(x) for x in a))) or ASK["v"])
    return root, calls, ASK


def _pump(root, timeout, pred=lambda: True):
    """Pompa event loop Tk sampai pred() benar atau timeout (dtk). Kembalikan pred()."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            root.update()
        except Exception:
            return pred()
        if pred():
            return True
        time.sleep(0.05)
    return pred()


def test_job_process_lifecycle(gui_env, tmp_path):
    import tkinter as tk

    root, _, _ = _tk_env()
    jobs = gui_env["jobs"]
    jm = jobs.JobManager(root)
    tgt = str(tmp_path / "datax")
    sleeper = [sys.executable, "-u", "-c", "import time;print('[1/3] a',flush=True);time.sleep(30)"]
    j1 = jm.start_process("handcheck", "Hand check", tgt, sleeper)
    assert _pump(root, 10, lambda: j1.progress == "1/3")
    assert j1.state == "running"
    with pytest.raises(jobs.JobConflict):
        jm.start_process("handcheck", "Hand check", tgt, sleeper)
    with pytest.raises(jobs.JobConflict):
        jm.start_process("handcheck", "Hand check", os.path.join(tgt, "sub"), sleeper)
    jm.stop(j1)
    assert _pump(root, 10, lambda: j1.state == "stopped")
    assert j1.proc.poll() is not None
    jm.stop_all()
    assert not jm.running()


def test_job_thread_lifecycle(gui_env):
    import tkinter as tk

    root, _, _ = _tk_env()
    jobs = gui_env["jobs"]
    jm = jobs.JobManager(root)
    done = []

    def work(job):
        for i in range(50):
            if job.cancel.is_set():
                return None
            time.sleep(0.02)
        return "ok"

    jt = jm.start_thread("scan", "Scan", r"C:\x", work,
                         lambda job, res, err: done.append((job.state, res, err)))
    _pump(root, 2)
    with pytest.raises(jobs.JobConflict):
        jm.start_thread("scan", "Scan", r"C:\y", work)
    jm.stop(jt)
    assert _pump(root, 10, lambda: bool(done))
    assert done[0][0] == "stopped"


def test_arrange_blocks_while_running(gui_env, tmp_path):
    import tkinter as tk

    root, _, _ = _tk_env()
    jobs = gui_env["jobs"]
    jm = jobs.JobManager(root)
    tgt = str(tmp_path / "datax")
    sleeper = [sys.executable, "-u", "-c", "import time;time.sleep(30)"]
    jm.start_process("handcheck", "Hand check", tgt, sleeper)
    assert jm.guard_arrange(os.path.dirname(tgt))
    assert jm.guard_arrange(r"C:\folder\lain") is None


def test_full_workflow_headless(gui_env, tmp_path):
    """Alur scan -> arrange -> preview -> hand check -> Stop, terisolasi di tmp."""
    import tkinter as tk

    root, calls, ASK = _tk_env()
    zywtool = gui_env["zywtool"]
    handcheck = gui_env["handcheck"]
    jobs = gui_env["jobs"]

    groot = tmp_path / "_uji_gui_root"
    groot.mkdir()
    N1, N2 = "session_00001-aaa", "session_00002-bbb"
    make_session(str(groot), name=N1, recorder="Fiktif A UPH", device="ZYW012",
                 location="MM3006", start_unix=1700000000 + 8 * 3600)
    make_session(str(groot), name=N2, recorder="Fiktif B UPH", device="ZYW012",
                 location="MM3006", start_unix=1700000000 + 8 * 3600 + 1)

    app = zywtool.App(root)
    app.path_var.set(str(groot))
    assert hasattr(app, "jobs_panel")

    # scan
    app.scan()
    sc = [j for j in app.jobs.jobs if j.kind == "scan"][-1]
    assert _pump(root, 40, lambda: sc.state != "running")
    assert sc.state == "done"
    assert len(app.sessions) == 2
    assert str(app.scan_btn.cget("state")) == "normal"

    # arrange
    ASK["v"] = True
    app.apply_org()
    s1, s2 = app.by_name[N1], app.by_name[N2]
    assert all(os.path.isdir(s.path) and os.path.dirname(s.path) != str(groot) for s in (s1, s2))
    group_name = os.path.basename(os.path.dirname(s1.path))

    # preview sesi terpilih setelah arrange
    app.tree.selection_set(N1)
    root.update()
    app.preview_frames()
    pj = [j for j in app.jobs.jobs if j.kind == "preview"][-1]
    assert not any(c[0] == "showerror" for c in calls)
    assert _pump(root, 60, lambda: pj.state != "running")
    assert pj.state == "done"
    # subprocess preview menulis ke ZYWTOOL_PREVIEW_DIR (= <tmp>/preview); cek langsung,
    # jangan baca OUT_ROOT dari modul (bisa sudah tergantikan dari import sebelumnya).
    assert os.path.exists(os.path.join(str(tmp_path), "preview", group_name, f"{N1}_cam0.png"))

    # hand check sesi terpilih -> Stop SAAT masih running (progres 1/1 = analisis baru mulai)
    calls.clear()
    app.hand_check_run()
    hj = [j for j in app.jobs.jobs if j.kind == "handcheck"][-1]
    assert hj.state == "running" and hj.target == s1.path
    assert _pump(root, 60, lambda: hj.progress == "1/1")
    app.jobs_panel.tree.selection_set(str(hj.id))
    root.update()
    app.jobs_panel.stop_selected()
    assert _pump(root, 15, lambda: hj.state != "running")
    assert hj.state == "stopped"
    rdir1 = handcheck.report_dir_for(s1.path, s1.path)
    assert not os.path.exists(os.path.join(rdir1, "handcheck_report.html"))

    # hand check sampai selesai
    app.hand_check_run()
    hj2 = [j for j in app.jobs.jobs if j.kind == "handcheck"][-1]
    assert _pump(root, 90, lambda: hj2.state != "running")
    assert hj2.state == "done"
    assert os.path.exists(os.path.join(rdir1, "handcheck_report.html"))
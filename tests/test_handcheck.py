"""Tes hand check: analisis, laporan sesi/grup/tsv, idempoten, stop di tengah.

Memakai fixture MCAP sintetis. Inferensi MediaPipe jalan (model sudah ada di disk);
pakai frames kecil supaya cepat.
"""
import os
from pathlib import Path

from make_fixture import make_session

from zywtool import handcheck

HC = {"frames": 4, "sample_every_s": 0, "report": True}


def _two_sessions(root):
    root = str(root)
    paths = []
    for i in range(2):
        paths.append(make_session(root, name=f"session_0000{i}-aaa",
                                 recorder="Fiktif A UPH", device="ZYW012",
                                 location="MM3006", start_unix=1700000000 + 8 * 3600 + i))
    return root, paths


def test_analyze_single_session(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    p = make_session(str(root), name="session_00001-aaa")
    r = handcheck.analyze_session(p, handcheck.get_cfg(HC), report_dir=str(tmp_path / "rep"))
    assert r["frames"] == 4
    # analyze_session menulis gambar sampel (json hasil ditulis oleh write_session_report)
    assert os.path.exists(str(tmp_path / "rep" / "handcheck_sample.png"))


def test_corrupt_skipped_in_check_sessions(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    good = make_session(str(root), name="session_00001-aaa")
    bad = make_session(str(root), name="session_00002-bbb", corrupt=True)
    items = [
        {"path": good, "name": "session_00001-aaa", "recorder": "", "location": "",
         "start": "", "duration_min": None, "health": "OK"},
        {"path": bad, "name": "session_00002-bbb", "recorder": "", "location": "",
         "start": "", "duration_min": None, "health": "CORRUPT", "skip": "dilewati (sesi CORRUPT)"},
    ]
    entries = handcheck.check_sessions(items, handcheck.get_cfg(HC), str(root))
    assert entries[0].get("hand") and entries[0]["hand"].get("frames")
    assert "skip" in entries[1]


def test_reports_follow_directory_structure(tmp_path):
    from zywtool import zyw_core as core

    rd = str(tmp_path / "root")
    os.makedirs(rd)
    _two_sessions(tmp_path / "root")
    cfg = core.load_config()
    # alur asli: scan -> arrange (buat folder grup) -> hand check
    sess = core.scan_all(rd)
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    core.arrange(sess, cfg, rd, apply=True)
    core.scan_all(rd, hand_check=True, hand_cfg=HC)
    rep_root = os.path.join(handcheck.REPORT_DIR, "root")
    # folder grup = hasil arrange (bukan session_), berisi laporan grup + laporan sesi
    grp = [d for d in os.listdir(rep_root) if os.path.isdir(os.path.join(rep_root, d))
           and not d.startswith("session_") and d != "_REJECTED"]
    assert grp, os.listdir(rep_root)
    g = grp[0]
    assert os.path.exists(os.path.join(rep_root, g, "handcheck_report.html"))
    assert os.path.exists(os.path.join(rep_root, g, "session_00000-aaa", "handcheck_report.html"))
    # ringkasan
    assert os.path.exists(os.path.join(rep_root, "_ringkasan.tsv"))


def test_no_extra_files_after_rerun(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _two_sessions(root)
    from zywtool import zyw_core as core
    rep_root = os.path.join(handcheck.REPORT_DIR, "root")

    def count_files():
        return sum(len(f) for _, _, f in os.walk(rep_root))

    core.scan_all(str(root), hand_check=True, hand_cfg=HC)
    n1 = count_files()
    core.scan_all(str(root), hand_check=True, hand_cfg=HC)
    n2 = count_files()
    assert n1 == n2, f"{n1} -> {n2}"
    # tidak ada tmp tersisa
    assert not [f for _, _, fs in os.walk(rep_root) for f in fs if f.endswith(".tmp")]


def test_stop_midway_keeps_finished_only(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _two_sessions(root)
    items = []
    for s in ("session_00000-aaa", "session_00001-aaa"):
        items.append({"path": os.path.join(str(root), s), "name": s, "recorder": "",
                     "location": "", "start": "", "duration_min": None, "health": "OK"})
    flag = {"stop": False}
    entries = handcheck.check_sessions(items, handcheck.get_cfg(HC), str(root),
                                       should_stop=lambda: flag["stop"],
                                       on_entry=lambda e, i, n: flag.update(stop=True))
    assert len(entries) == 1
    assert os.path.exists(entries[0]["report"])
    other = os.path.join(handcheck.report_dir_for(os.path.join(str(root), "session_00001-aaa"), str(root)),
                         "handcheck_report.html")
    assert not os.path.exists(other)


def test_scan_all_hand_check_fills_session_and_progress(tmp_path):
    """scan_all(hand_check=True) mengisi s.hand, melewati CORRUPT, dan mencatat
    progress '(hand check)' + LAST_HAND_REPORT (perilaku yang dipakai GUI)."""
    from zywtool import zyw_core as core

    rd = str(tmp_path / "root")
    os.makedirs(rd)
    make_session(rd, name="session_00000-aaa", recorder="Fiktif A UPH")
    make_session(rd, name="session_00002-bbb", recorder="Fiktif B UPH", corrupt=True)
    msgs = []
    core.LAST_HAND_REPORT = None
    sess = core.scan_all(rd, hand_check=True, hand_cfg=HC, progress=lambda i, n, name: msgs.append(name))
    g = next(s for s in sess if s.name == "session_00000-aaa")
    b = next(s for s in sess if s.name == "session_00002-bbb")
    assert g.hand and g.hand.get("frames")
    assert not b.hand
    assert any("(hand check)" in m for m in msgs), msgs
    assert os.path.join(handcheck.REPORT_DIR, "root") == core.LAST_HAND_REPORT


def test_group_report_links_and_embed(tmp_path):
    """Laporan grup (per orang) memuat link ke laporan sesi; laporan sesi menyemat
    gambar base64; folder _REJECTED menandai SKIP; _ringkasan.tsv = header + N baris."""
    from zywtool import zyw_core as core

    rd = str(tmp_path / "root")
    os.makedirs(rd)
    make_session(rd, name="session_00000-aaa", recorder="Fiktif A UPH")
    make_session(rd, name="session_00002-bbb", recorder="Fiktif B UPH", corrupt=True)
    cfg = core.load_config()
    sess = core.scan_all(rd)
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    core.arrange(sess, cfg, rd, apply=True)
    core.scan_all(rd, hand_check=True, hand_cfg=HC)

    rep_root = os.path.join(handcheck.REPORT_DIR, "root")
    grp = [d for d in os.listdir(rep_root) if os.path.isdir(os.path.join(rep_root, d))
           and not d.startswith("session_") and d != "_REJECTED"]
    g = grp[0]
    # cari nama sesi di dalam grup
    sess_dirs = [d for d in os.listdir(os.path.join(rep_root, g))
                 if os.path.isdir(os.path.join(rep_root, g, d))]
    grp_txt = Path(rep_root, g, "handcheck_report.html").read_text(encoding="utf-8")
    assert any(f"{d}/handcheck_report.html" in grp_txt for d in sess_dirs)
    sesi_html = Path(rep_root, g, sess_dirs[0], "handcheck_report.html").read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," in sesi_html
    # _REJECTED menandai SKIP
    rej_html = Path(rep_root, "_REJECTED", "handcheck_report.html").read_text(encoding="utf-8")
    assert "SKIP" in rej_html
    tsv = Path(rep_root, "_ringkasan.tsv").read_text(encoding="utf-8-sig").splitlines()
    assert len(tsv) == 3  # header + 2 sesi


def test_analyze_memory_streaming(tmp_path):
    """Frame tidak menumpuk di memori: pakai tracemalloc (tanpa psutil)."""
    import tracemalloc

    root = tmp_path / "root"
    root.mkdir()
    p = make_session(str(root), name="session_00001-aaa")
    tracemalloc.start()
    handcheck.analyze_session(p, handcheck.get_cfg(HC))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # ambang longgar (MB); hanya menjamin tidak bocor masif, bukan persis
    assert peak / 1e6 < 600, f"puncak memori {peak/1e6:.0f} MB terlalu tinggi"

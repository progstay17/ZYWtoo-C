"""Tes inti: ruangan, scan, arrange (idempoten/resolve/undo), Excel, shift.

Menggantikan bagian test_logic.py; semua data sintetis (tanpa H:/I:).
"""
import os
import shutil

import pytest
from make_fixture import make_session

from zywtool import handcheck
from zywtool import zyw_core as core

# ---------- a. nama ruangan ----------
ROOM_CASES = {
    "Living Room ZYW018 (2)": ("ZYW018", "Livingroom"),
    "Cleaning Kitchen ZYW13": ("ZYW013", "Kitchen"),
    "Bedroom 2 ZYW020": ("ZYW020", "Bedroom"),
    "Cleaning Livingroom ZYW5": ("ZYW005", "Livingroom"),
    "Ruang Tamu ZYW7": ("ZYW007", "Livingroom"),
    "Laundry ZYW9": ("ZYW009", "Laundry"),
    "Membersihkan Dan memasang tali sepatu": ("", "Membersihkan Dan memasang tali sepatu"),
}


@pytest.mark.parametrize("task,exp", list(ROOM_CASES.items()))
def test_room_parsing(task, exp):
    assert core._task_fields(task) == exp


def test_default_rooms_three():
    cfg = core.load_config()
    assert list(cfg["activities"].keys()) == ["Kitchen", "Livingroom", "Bedroom"]


def test_shift_gap_and_overtime_boundaries():
    shifts = core.DEFAULT_CONFIG["shifts"]
    # Mulai di celah 11:00 -> shift berikutnya; durasi melewati 16:00 = lembur.
    s = core.Session("x", "x", start=__import__("datetime").datetime(
        2026, 1, 1, 10, 45, tzinfo=core.WIB), duration_s=30 * 60)
    core.split_shifts(s, shifts)
    assert s.shift == "7 AM - 11 PM" and s.overtime_min == 15.0
    # Mulai 20:15 masih S4; setelah 20:30 dicatat lembur, bukan dipecah.
    s = core.Session("x", "x", start=__import__("datetime").datetime(
        2026, 1, 1, 20, 15, tzinfo=core.WIB), duration_s=30 * 60)
    core.split_shifts(s, shifts)
    assert s.shift == "6:30 PM - 8:80 PM" and s.overtime_min == 15.0
    # Mulai tepat 20:30 sudah di luar shift.
    s = core.Session("x", "x", start=__import__("datetime").datetime(
        2026, 1, 1, 20, 30, tzinfo=core.WIB), duration_s=30 * 60)
    core.split_shifts(s, shifts)
    assert s.shift == core.UNSHIFTED


# ---------- b. folder laporan mengikuti struktur asli ----------
def test_report_dir_mirror_root_group():
    rd = handcheck.report_dir_for(r"I:\data\GRUP\session_1", r"I:\data")
    assert rd == os.path.join(handcheck.REPORT_DIR, "data", "GRUP", "session_1")


def test_report_dir_single_session():
    rd = handcheck.report_dir_for(r"C:\x\tes upload\session_9", r"C:\x\tes upload\session_9")
    assert rd == os.path.join(handcheck.REPORT_DIR, "tes upload", "session_9")


# ---------- c/d. scan + arrange ----------
def _build_tree(root, *, corrupt=False):
    """2 sesi sehat + 1 rusak (terpotong)."""
    paths = []
    for i, (rec, dev, loc) in enumerate([
        ("Uji Satu UPH", "ZYW013", "MM3006"),
        ("Uji Dua UPH", "ZYW013", "MM3006"),
    ]):
        paths.append(make_session(str(root), name=f"session_{i:05d}-aaa", recorder=rec,
                                 device=dev, location=loc, start_unix=1700000000 + 8 * 3600))
    bad = make_session(str(root), name="session_00002-bbb", recorder="Uji Tiga UPH",
                       device="ZYW014", location="MM3006", start_unix=1700000000 + 8 * 3600,
                       corrupt=True)
    paths.append(bad)
    return paths


def test_scan_quick_find_three(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    assert len(sess) == 3
    bad = [s for s in sess if s.health == "CORRUPT"]
    good = [s for s in sess if s.health != "CORRUPT"]
    assert len(bad) == 1 and len(good) == 2


def test_scan_should_stop_immediately(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    assert core.scan_all(str(root), should_stop=lambda: True) == []


def test_corrupt_session_detected(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    p = make_session(str(root), name="session_00002-bbb", corrupt=True)
    s = core.scan_session(p)
    assert s.health == "CORRUPT"


def test_empty_mcap_corrupt(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    p = make_session(str(root), name="session_empty", empty_mcap=True)
    s = core.scan_session(p)
    assert s.health == "CORRUPT"


def test_arrange_moves_and_updates_path(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    plan = core.arrange(sess, cfg, str(root), apply=True)
    assert len(plan) == 3
    good = next(s for s in sess if s.health != "CORRUPT")
    assert os.path.isdir(good.path) and os.path.dirname(good.path) != str(root)
    bad = next(s for s in sess if s.health == "CORRUPT")
    assert os.path.basename(os.path.dirname(bad.path)) == "_REJECTED"


def test_arrange_idempotent(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    core.arrange(sess, cfg, str(root), apply=True)
    assert core.arrange(sess, cfg, str(root), apply=True) == []


def test_resolve_after_manual_move(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    good = next(s for s in sess if s.health != "CORRUPT")
    core.arrange(sess, cfg, str(root), apply=True)
    old = good.path
    manual = os.path.join(str(root), os.path.basename(old))
    shutil.move(old, manual)
    assert core.resolve_session_path(good, str(root)) == manual
    assert good.path == manual


def test_resolve_missing_session_returns_none(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    ghost = core.Session(name="session_99999-zzz", path=os.path.join(str(root), "hilang", "session_99999-zzz"))
    assert core.resolve_session_path(ghost, str(root)) is None


def test_arrange_log_written_for_undo(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    core.arrange(sess, cfg, str(root), apply=True)
    logs = [f for f in os.listdir(core.LOG_DIR) if f.startswith("arrange_")]
    assert logs, "log arrange (undo) tidak ditulis"


def test_undo_arrange_moves_sessions_back(tmp_path, cfg, monkeypatch):
    """UNDO: dry-run tidak memindah; apply memindah kembali; SKIP kalau tidak aman."""
    # arahkan LOG_DIR ke tmp agar tidak menulis ke proyek
    monkeypatch.setattr(core, "LOG_DIR", str(tmp_path / "logs"))
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    core.arrange(sess, cfg, str(root), apply=True)
    log_path = os.path.join(core.LOG_DIR,
                            sorted(f for f in os.listdir(core.LOG_DIR)
                                   if f.startswith("arrange_"))[-1])

    # dry-run: tidak memindah apa pun, semua DRY
    res = core.undo_arrange(log_path, apply=False)
    assert res and all(r[2] == "DRY" for r in res)
    assert all(os.path.isdir(r[1]) for r in res)  # folder grup masih ada

    # apply: semua kembali ke posisi asal
    res = core.undo_arrange(log_path, apply=True)
    assert res and all(r[2] == "OK" for r in res)
    for src, dst, _ in res:
        assert os.path.isdir(src) and not os.path.isdir(dst)

    # jalankan lagi: semua SKIP karena 'from' sudah terisi / 'to' sudah tidak ada
    res = core.undo_arrange(log_path, apply=True)
    assert all(r[2].startswith("SKIP") for r in res)


def test_excel_export_atomic_no_tmp_left(tmp_path, cfg):
    """Export Excel atomik: selesai tanpa sisa file .tmp.xlsx."""
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    cfg["excel_path"] = str(tmp_path / "x.xlsx")
    core.export_excel(sess, cfg)
    assert os.path.exists(cfg["excel_path"])
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp.xlsx")]


# ---------- g/h. Excel: dropdown + validasi pengguna + Cek File ----------
def test_excel_dropdown_and_user_validation(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    _build_tree(root)
    sess = core.scan_all(str(root))
    for s in sess:
        core.split_shifts(s, cfg["shifts"])
    cfg["excel_path"] = str(tmp_path / "x.xlsx")
    for _ in range(2):
        core.export_excel(sess, cfg)

    from openpyxl import load_workbook
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = load_workbook(cfg["excel_path"])
    dvs = wb["ZY White"].data_validations.dataValidation
    assert len(dvs) == 1, dvs
    assert dvs[0].formula1 == '"Kitchen,Livingroom,Bedroom"'
    assert not dvs[0].showErrorMessage

    hdr = [c.value for c in wb["Cek File"][1]]
    assert "Tangan error strict (%)" in hdr
    assert "Tangan error lenient (%)" in hdr
    assert "Tangan 0/1/2/3+" in hdr

    # validasi milik pengguna tidak boleh ikut terhapus
    ws = wb["ZY White"]
    mine = DataValidation(type="list", formula1='"Ya,Tidak"', allow_blank=True)
    ws.add_data_validation(mine)
    mine.add("D3:D500")
    wb.save(cfg["excel_path"])
    core.export_excel(sess, cfg)
    wb = load_workbook(cfg["excel_path"])
    sq = sorted(str(d.sqref) for d in wb["ZY White"].data_validations.dataValidation)
    assert sq == ["C3:C20000", "D3:D500"]


# ---------- i. Stop di dalam analisis ----------
def test_analyze_cancelled_throws(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    p = make_session(str(root), name="session_00001-aaa")
    rep = tmp_path / "rep_cancel"
    with pytest.raises(handcheck.Cancelled):
        handcheck.analyze_session(p, handcheck.get_cfg({"frames": 6, "sample_every_s": 0, "report": True}),
                                  report_dir=str(rep), should_stop=lambda: True)
    assert not os.path.exists(rep)


def test_analyze_no_report_dir_writes_no_images(tmp_path, cfg):
    root = tmp_path / "root"
    root.mkdir()
    p = make_session(str(root), name="session_00001-aaa")
    r = handcheck.analyze_session(p, handcheck.get_cfg({"frames": 6, "sample_every_s": 0}))
    assert r["frames"] > 0 and r["sheet"] == ""

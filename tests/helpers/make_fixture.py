"""Helper tes: buat sesi MCAP sintetis dengan frame H.265 hasil encode libx265.

Tidak butuh protobuf terpasang — field foxglove.CompressedVideo ditulis manual
(seperti parser minimal di preview_frames.parse_proto: 1=timestamp, 3=data, 4=format).
Semua nama orang/lokasi/device FIKTIF (Aturan Keras #4). Tes jalan di mana saja,
tanpa H: atau I:.

Encoder libx265 harus tersedia di PyAV. Kalau tidak ada, raise SkipFixture agar
tes bisa skip dengan penanda jelas (Tahap 1a).
"""
from __future__ import annotations

import io
import json
import os
import sys
from contextlib import suppress

import av

try:
    import av.logging as _avlog

    _avlog.set_level(_avlog.ERROR)  # bungkam banner x265 di output tes
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))


class SkipFixture(RuntimeError):
    """Encoder H.265 tidak tersedia di lingkungan ini."""


def _have_h265():
    try:
        with av.open(io.BytesIO(), "w", format="hevc"):
            pass
    except Exception:
        return False
    return True


def _encode_h265(width, height, n_frames, fps=30, keyint=None):
    """Kembalikan bytes HEVC (annexb) dari n_frames gambar berwarna gradien."""
    buf = io.BytesIO()
    out = av.open(buf, "w", format="hevc")
    st = out.add_stream("libx265", rate=fps)
    st.width, st.height, st.pix_fmt = width, height, "yuv420p"
    quiet = "log-level=error"
    if keyint:
        st.options = {"preset": "ultrafast", "x265-params": f"keyint={keyint}:min-keyint={keyint}:{quiet}"}
    else:
        st.options = {"preset": "ultrafast", "x265-params": quiet}
    fr = av.VideoFrame(width, height, "rgb24")
    for i in range(n_frames):
        arr = fr.to_ndarray()
        arr[:] = ((i * 11) % 256, (i * 7) % 256, (i * 5) % 256)
        vf = av.VideoFrame.from_ndarray(arr, format="rgb24").reformat(format="yuv420p")
        for pkt in st.encode(vf):
            out.mux(pkt)
    for pkt in st.encode(None):
        out.mux(pkt)
    out.close()
    return buf.getvalue()


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _field(fn, wire_type, payload):
    return _varint((fn << 3) | wire_type) + payload


def _compressed_video_pb(ts_ns, hevc_bytes):
    """foxglove.CompressedVideo minimal: 1=timestamp(ns), 3=data, 4=format."""
    return (
        _field(1, 0, _varint(ts_ns))
        + _field(3, 2, _varint(len(hevc_bytes)) + hevc_bytes)
        + _field(4, 2, _varint(4) + b"h265")
    )


def _write_mcap(path, frames, start_ns, step_ns):
    """Tulis satu file .mcap berisi frames CompressedVideo di topic kamera."""
    from mcap.writer import Writer

    schema = ("syntax = \"proto3\";\npackage foxglove;\nmessage CompressedVideo {"
              "\n  uint64 timestamp = 1;\n  bytes data = 3;\n  string format = 4;\n}\n")
    with open(path, "wb") as fh:
        w = Writer(fh)
        w.start()
        schema_id = w.register_schema("foxglove.CompressedVideo", "protobuf", schema.encode())
        chan = w.register_channel("/ego/camera/0", "protobuf", schema_id,
                                   metadata={"encoding": "h265"})
        for i, hevc in enumerate(frames):
            t = start_ns + i * step_ns
            w.add_message(chan, log_time=t, data=_compressed_video_pb(t, hevc), publish_time=t)
        w.finish()


def make_session(root, *, name="session_00001-fix", recorder="Fiktif A UPH",
                 location="MM9999", device="ZYW999", start_unix=1700000000,
                 duration_frames=20, fps=30, width=64, height=48, corrupt=False,
                 stop_cause="BUTTON", client_unix_us=None, drop_session_json=False,
                 empty_mcap=False):
    """Buat satu folder sesi sintetis di bawah root. Mengembalikan path folder.

    corrupt=True  -> file mcap dipotong (footer hilang), meniru ego_0012.mcap terpotong.
    empty_mcap=True -> file 0 byte.
    drop_session_json=True -> tanpa session.json (cek penanganan error).
    Semua data FIKTIF.
    """
    if not _have_h265():
        raise SkipFixture("libx265 tidak tersedia di PyAV di lingkungan ini")

    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)

    if not drop_session_json:
        sj = {
            "device_id": f"rec-{device}",
            "task": f"Cleaning Kitchen {device}",
            "location": location,
            "capturer": recorder,
            "stop_cause": stop_cause,
            "start_time_unix": start_unix,
        }
        if client_unix_us is not None:
            sj["client_unix_us"] = client_unix_us
        with open(os.path.join(folder, "session.json"), "w", encoding="utf-8") as f:
            json.dump(sj, f)

    mcap_path = os.path.join(folder, "ego_0000.mcap")
    if empty_mcap:
        open(mcap_path, "wb").close()
        return folder

    step_ns = int(1e9 / fps)
    hevc = _encode_h265(width, height, duration_frames, fps=fps, keyint=max(1, duration_frames // 2))
    frames = [hevc for _ in range(duration_frames)]
    _write_mcap(mcap_path, frames, int(start_unix * 1e9), step_ns)

    if corrupt:
        # potong beberapa byte terakhir -> footer summary hilang (file terpotong)
        size = os.path.getsize(mcap_path)
        with open(mcap_path, "rb") as f:
            blob = f.read()
        with open(mcap_path, "wb") as f:
            f.write(blob[: max(1, size - 200)])

    if not drop_session_json:
        # recorder menulis session.json saat sesi selesai; samakan mtime-nya
        # dengan (mulai + durasi) supaya cek kesehatan tidak menghasilkan warning palsu.
        dur_s = (duration_frames - 1) / fps
        sj_path = os.path.join(folder, "session.json")
        with suppress(OSError):
            os.utime(sj_path, (start_unix + dur_s, start_unix + dur_s))

    return folder

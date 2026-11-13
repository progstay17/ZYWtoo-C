# ZYWtool

> **English summary:** ZYWtool is a Windows desktop and CLI utility for scanning MCAP recording sessions, validating file health, exporting operational Excel reports, arranging session folders, generating preview contact sheets, and performing probabilistic MediaPipe hand checks. It is designed for local operational use and never renames session folders.

**Fadhil Ghifarion 法迪 for AIT**

[![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.14-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-37%20passed-brightgreen)](#pengembangan-dan-tes)
[![License](https://img.shields.io/badge/license-MIT-green)](#lisensi)

## Ringkas

ZYWtool membantu alur kerja rekaman MCAP:

```text
Scan  →  Excel  →  Arrange folder  →  Preview  →  Hand check
  └────────────── bisa dilakukan ulang dengan aman ──────────────┘
```

Folder `session_...` **tidak pernah di-rename**. Arrange hanya memindahkan folder sesi ke folder grup dan menulis log undo.

## Fitur

- Scan sesi MCAP cepat atau penuh; mendeteksi `OK`, `WARN`, dan `CORRUPT`.
- Validasi header/footer MCAP, statistik pesan, durasi, overlap, dan metadata `session.json`.
- Export workbook Excel dengan sheet `ZY White` dan `Cek File`.
- Sheet `Cek File` menampilkan status, alasan, lembur, serta hasil hand check **strict dan lenient berdampingan**.
- Arrange sesi ke nama folder grup deterministik; sesi corrupt masuk `_REJECTED`.
- Log pemindahan dan CLI undo yang aman/dry-run.
- Preview contact sheet frame kamera H.265.
- Hand check MediaPipe dengan sampling merata, frame penuh + empat crop, laporan HTML mandiri, JSON, PNG, dan TSV.
- Background jobs dengan pencegah proses dobel, progress, dan tombol Stop.
- Semua output kerja diarahkan ke disk lokal aplikasi; sumber rekaman bisa berada di drive lain.

## Instalasi Windows

Cara yang disarankan:

1. Ekstrak/copy proyek ke folder lokal, misalnya `Documents\ZYWtool`.
2. Jalankan `scripts\install.bat`.
3. Installer akan:
   - memeriksa Python dan Tkinter;
   - membuat `.venv`;
   - memasang versi dependensi yang dipin;
   - mengunduh model MediaPipe secara atomik;
   - memverifikasi SHA-256 model;
   - menjalankan `scripts\check_install.py`;
   - membuat `run_zywtool.bat` dan shortcut Desktop.
4. Jalankan `run_zywtool.bat` atau shortcut **ZYWtool**.

PowerShell langsung:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Jika Python tidak ditemukan, install Python 3.11–3.14 dari python.org dengan opsi **tcl/tk**. Python yang dipakai dan diuji pada audit ini adalah **3.14.8**.

## GUI

GUI menampilkan:

- Data Source dan mode `quick`/`full`;
- filter nomor sesi, waktu mulai, dan shift;
- metrik jumlah sesi, qualified, storage, dan durasi;
- tabel Session Explorer;
- Background Jobs untuk preview dan hand check;
- tombol Export, Arrange, Preview, Folder statistics, dan Hand check.

GUI sudah diuji sungguhan pada Windows dengan data sintetis: jendela 1440×900, scan empat sesi, status selesai, tabel, scrollbar, dan panel dashboard berhasil dirender.

## CLI

Scan/statistik folder:

```powershell
python zywtool.py --stats C:\Data\SyntheticRecordings
```

Hand check:

```powershell
python handcheck.py C:\Data\SyntheticRecordings
python handcheck.py C:\Data\SyntheticRecordings --rule lenient --every 15
python handcheck.py C:\Data\SyntheticRecordings --no-report --no-tiles
```

Preview:

```powershell
python preview_frames.py C:\Data\SyntheticRecordings --n 16 --cam 0
```

Undo arrange (selalu lihat dry-run dulu):

```powershell
python zyw_core.py --list-logs
python zyw_core.py --undo logs\arrange_YYYYMMDD_HHMMSS.json
python zyw_core.py --undo logs\arrange_YYYYMMDD_HHMMSS.json --apply
```

Root-level command di atas dipertahankan sebagai wrapper kompatibilitas; implementasi kanonis berada di package `zywtool/`.

## Konfigurasi

Salin `zyw_config.example.json` menjadi `zyw_config.json`, lalu sesuaikan path lokal. **Jangan commit `zyw_config.json` milik pengguna.**

| Kunci | Arti |
|---|---|
| `shifts` | Jam mulai, jam akhir, label dropdown, nomor shift |
| `excel_path` | File workbook output |
| `organized_root` | Root organisasi jika digunakan workflow eksternal |
| `activities` | Nama ruangan kanonik dan alias |
| `hand_check.rule` | Rule yang memicu FLAG: `strict` atau `lenient` |
| `hand_check.sample_every_s` | Jarak sampling kira-kira dalam detik |
| `hand_check.min_frames` / `max_frames` | Batas jumlah sampel |
| `hand_check.max_error_pct` | Batas FLAG |
| `hand_check.tiles` | Frame penuh + empat potongan |

Path lama absolut di config pengguna tetap dibaca untuk kompatibilitas. Default baru relatif ke folder aplikasi.

## Aturan shift

Label dipertahankan persis karena dicocokkan oleh dropdown/formula workbook:

| Label | Waktu | Kode |
|---|---:|---:|
| `7 AM - 11 PM` | 07:00–11:00 | S1 |
| `12 PM - 4 PM` | 12:00–16:00 | S2 |
| `4:10 PM - 6:30 PM` | 16:10–18:30 | S3 |
| `6:30 PM - 8:80 PM` | 18:30–20:30 | S4 |

Sesi ditentukan oleh **waktu mulai**. Mulai di celah masuk shift berikutnya; mulai setelah 20:30 menjadi `DI LUAR SHIFT`. Durasi yang melewati batas akhir dicatat sebagai lembur dan sesi tidak dipecah.

## Format folder grup

```text
yyyymmdd_LOKASI_NamaRecorderTanpaSpasi_ZYWxxx_Sn_Ruangan
```

Contoh fiktif:

```text
20261113_MM9999_FiktifRecorder_ZYW999_S2_Kitchen
```

Ruangan kanonik default: `Kitchen`, `Livingroom`, `Bedroom`. Teks yang tidak cocok tetap dipakai sebagai aktivitas kustom.

## Format laporan

- `ZY White`: blok tiga baris per recorder-shift; kolom manual seperti Status, QC, Qualified Sessions/Hours, Rejected Hours, dan Supervisor tetap kosong.
- `Cek File`: satu baris per sesi, status kesehatan, alasan, folder grup, lembur, strict %, lenient %, dan hitungan tangan 0/1/2/3+.
- Hand check per sesi: `handcheck_report.html`, `handcheck_result.json`, `handcheck_sample.png`, dan gambar error bila ada.
- Hand check per grup: laporan HTML berisi semua sesi dalam folder grup.
- `_ringkasan.tsv`: mudah ditempel ke Excel, dengan error strict dan lenient berdampingan.
- Semua laporan ditulis atomik atau ditimpa idempoten saat dijalankan ulang.

## Strict dan lenient

- **Strict:** error jika jumlah tangan bukan 2 atau ada titik tangan keluar frame.
- **Lenient:** error jika jumlah tangan 0, lebih dari 2, atau ada titik tangan keluar frame.
- Sesi ditandai FLAG bila persentase frame error melebihi batas konfigurasi.
- Nilai strict dan lenient selalu ditampilkan berdampingan; `rule` hanya menentukan nilai yang memicu FLAG.

## Keterbatasan dan troubleshooting

- Hand check bersifat probabilistik, bukan keputusan otomatis. Sampling bukan pemeriksaan semua frame.
- Jari kaki hanya terdeteksi bila kebetulan terbaca sebagai tangan ketiga atau lebih.
- Jika `I:` tidak terpasang, Scan menampilkan pesan folder tidak ditemukan; pasang drive atau pilih folder lain.
- File MCAP terpotong ditandai `CORRUPT`; jangan menimpa sumber asli.
- Jika Excel sedang terbuka, tutup workbook lalu export ulang.
- Jika MediaPipe gagal, jalankan ulang installer untuk memeriksa model dan hash.
- Resolusi/path Windows yang sangat panjang dapat dibatasi oleh Windows atau filesystem.
- UI saat ini masih mencampur Inggris dan Indonesia; standardisasi bahasa adalah pekerjaan lanjutan yang belum diputuskan.

## Data, privasi, dan repo publik

Repo publik tidak boleh berisi:

- rekaman/frame asli;
- nama recorder atau lokasi nyata;
- path pribadi, token, config pengguna, Excel pengguna;
- cache, model unduhan, preview, laporan, atau hasil scan.

Fixture dan contoh proyek memakai data fiktif. Screenshot dokumentasi harus berasal dari data sintetis atau diblur total.

## Pengembangan dan tes

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest tests/ -q
```

Audit terakhir: **37 tes lulus**, Ruff bersih, fixture MCAP H.265 sintetis, GUI headless, GUI nyata, export Excel, arrange, hand check, Stop, dan anti-dobel sudah diverifikasi.

Struktur:

```text
zywtool/             implementasi package
*.py                 wrapper CLI kompatibilitas
scripts/             installer dan smoke check
tests/               pytest + fixture sintetis
docs/                dokumentasi tambahan
Excel/               workbook lokal pengguna (jangan commit)
```

## Credits

- **Fadhil Ghifarion 法迪 for AIT** — pemilik workflow, domain rules, dan aplikasi.
- Parser/keyframe H.265 diadaptasi dari karya `mcap2mp4` milik Fadhil sendiri, repo `progstay17/Mcap2Mp4-converter-`; atribusi dipertahankan di kode.
- [MediaPipe](https://github.com/google-ai-edge/mediapipe)
- [PyAV](https://github.com/PyAV-Org/PyAV)
- [mcap](https://github.com/foxglove/mcap)
- [openpyxl](https://openpyxl.readthedocs.io/)
- [Pillow](https://python-pillow.org/)

## Lisensi

MIT — lihat [`LICENSE`](LICENSE).

Copyright (c) 2026 Fadhil Ghifarion 法迪 for AIT

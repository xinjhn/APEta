# Panduan Verifikasi Lokal APE (manual, langkah demi langkah)

Panduan ini untuk menjalankan ulang sendiri verifikasi yang sudah dilakukan,
di laptop ini, sebelum pindah ke VM. Semua perintah PowerShell, dijalankan
dari root proyek (`d:\TA\APE VM`).

> Catatan struktur: proyek ini sudah direstrukturisasi dari layout flat
> menjadi `core/`, `tests/`, `tools/`, `telemetry/` (lihat `core/__init__.py`
> dkk). Jangan kembalikan ke flat — `rest_server.py`/`graphql_server.py`
> butuh paket `core` untuk bisa start.

## 0. Buka 2 jendela terminal
Kamu butuh **2 terminal PowerShell terpisah**: satu untuk server REST, satu
untuk server GraphQL (keduanya berjalan sebagai proses foreground supaya log
error langsung kelihatan). Terminal ketiga (opsional) untuk menjalankan
perintah uji (curl/python) sambil kedua server hidup.

Di **setiap** terminal yang dipakai, jalankan dulu:
```powershell
cd "d:\TA\APE VM"
.venv\Scripts\Activate.ps1
```

## 1. Setup (sekali saja, kalau `.venv` belum ada)
```powershell
python --version                 # harus 3.10+ (lokal: 3.13.14)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # httpx2 (TestClient) & httpx (scratch/ liveness) sudah terpin di sini
```
Verifikasi versi terpasang cocok dengan `requirements.txt`:
```powershell
pip freeze | Select-String "fastapi|starlette|strawberry|uvicorn|psutil"
```

## 2. Buat data sintetis (HANYA untuk verifikasi, bukan data eksperimen)
```powershell
python tools\make_synthetic_pool.py --out scratch\synthetic.json --n 300 --seed 42
```
**Kriteria terima**: pesan `Ditulis 300 record sintetis ke ...` muncul, file
`scratch\synthetic.json` ada.

> Pakai path relatif (`scratch\synthetic.json`), bukan `/tmp/...` — di Git
> Bash, path gaya `/tmp/...` yang ditulis langsung di dalam skrip Python bisa
> salah diterjemahkan (Windows Python membacanya sebagai root drive, bukan
> folder Temp). Path relatif aman di PowerShell maupun Git Bash.

## 3. Jalankan uji paritas (paling penting — jangan lanjut kalau ini gagal)
```powershell
$env:APE_POOL_JSON = "d:\TA\APE VM\scratch\synthetic.json"
python tests\test_parity.py
```
**Kriteria terima**: keluaran tepat
```
Paritas: 48/48 kombinasi identik.
```
Kalau bukan 48/48, skrip akan mencetak `[MISMATCH] ...` untuk tiap kombinasi
yang gagal beserta isi respons REST vs GraphQL — laporkan itu, jangan lanjut
ke langkah berikutnya.

## 4. Jalankan server REST (Terminal #1, biarkan tetap terbuka)
```powershell
$env:APE_POOL_JSON = "d:\TA\APE VM\scratch\synthetic.json"
uvicorn rest_server:app --workers 1 --host 127.0.0.1 --port 8000
```
Biarkan jendela ini terbuka selama testing. Tekan `Ctrl+C` untuk berhenti.

## 5. Jalankan server GraphQL (Terminal #2, biarkan tetap terbuka)
```powershell
$env:APE_POOL_JSON = "d:\TA\APE VM\scratch\synthetic.json"
uvicorn graphql_server:app --workers 1 --host 127.0.0.1 --port 8001
```
> Di lokal boleh keduanya hidup bersamaan (port beda) untuk kemudahan testing.
> Di VM nanti mereka jalan **bergantian di port yang sama** — jangan jadikan
> kebiasaan "jalan bersamaan" ini sebagai asumsi di VM.

## 6. Smoke test REST (Terminal #3)
```powershell
$density = "high"; $seed = 5
foreach ($ep in "baseline","partial","filtered","aggregate") {
    Write-Host "=== /$ep ===" -ForegroundColor Cyan
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/$ep?density=$density&seed=$seed"
    Write-Host "status=$($r.StatusCode) X-Process-Time=$($r.Headers['X-Process-Time']) size=$($r.RawContentLength) bytes"
}
# Health check
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
# Kasus filter kosong (array kosong = valid, BUKAN error)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/filtered?density=low&seed=5&class_label=bus&min_confidence=0.95"
```
**Kriteria terima**:
- Semua status `200`.
- Header `X-Process-Time` ada di tiap respons.
- `partial` lebih kecil dari `baseline` (sekitar 44% lebih kecil pada data
  sintetis ini — partial membuang `bounding_box`).
- `aggregate` jauh lebih kecil dari `baseline` (ratusan byte vs ~11 KB).
- `/filtered` dengan `class_label=bus&min_confidence=0.95` boleh balas
  `"detections": []` — itu valid.

## 7. Smoke test GraphQL (Terminal #3)
```powershell
function Invoke-Gql($query) {
    $body = @{ query = $query } | ConvertTo-Json -Compress
    Invoke-WebRequest -Uri "http://127.0.0.1:8001/graphql" -Method Post -ContentType "application/json" -Body $body
}

$baseline = Invoke-Gql '{ image_detections(density:"high", seed:5) { image_id dimensions { width height } detections { class_label confidence_score bounding_box } } }'
$partial  = Invoke-Gql '{ image_detections(density:"high", seed:5) { image_id dimensions { width height } detections { class_label confidence_score } } }'
$filtered = Invoke-Gql '{ image_detections(density:"high", class_label:"car", min_confidence:0.5, seed:5) { image_id dimensions { width height } detections { class_label confidence_score bounding_box } } }'
$aggregate = Invoke-Gql '{ aggregate(density:"high", seed:5) { image_id class_counts { class_name count } } }'

foreach ($name in "baseline","partial","filtered","aggregate") {
    $r = Get-Variable -Name $name -ValueOnly
    Write-Host "=== $name === status=$($r.StatusCode) X-Process-Time=$($r.Headers['X-Process-Time']) size=$($r.RawContentLength)"
    if ($r.Content -match '"errors"') { Write-Host "  !! ADA ERRORS !!" -ForegroundColor Red }
}
```
**Kriteria terima**:
- Semua status `200`, tidak ada key `"errors"` di body manapun.
- Header `X-Process-Time` ada.
- Ukuran payload GraphQL sedikit lebih besar dari REST (selisih ~30 byte —
  itu cuma amplop `{"data":{...}}`, bukan bias).

## 8. Cross-check data REST vs GraphQL (Terminal #3)
Bandingkan isi data (bukan cuma ukuran) untuk density+seed yang sama:
```powershell
$restBaseline = (Invoke-RestMethod -Uri "http://127.0.0.1:8000/baseline?density=high&seed=5")
$gqlBaseline  = (Invoke-RestMethod -Uri "http://127.0.0.1:8001/graphql" -Method Post -ContentType "application/json" `
    -Body '{"query":"{ image_detections(density:\"high\", seed:5) { image_id dimensions { width height } detections { class_label confidence_score bounding_box } } }"}').data.image_detections

# Bandingkan sebagai JSON (urutan key boleh beda, isi harus sama)
$restJson = $restBaseline | ConvertTo-Json -Depth 10 -Compress
$gqlJson  = $gqlBaseline  | ConvertTo-Json -Depth 10 -Compress
if ($restJson -eq $gqlJson) { "MATCH" } else { "MISMATCH — periksa manual" }
```
Ulangi untuk `partial`, `filtered`, `aggregate` kalau mau lebih yakin (logika
sama seperti `tests/test_parity.py`, tapi di sini lewat server sungguhan).

## 9. Telemetri (Terminal #3, sambil REST/GraphQL hidup)
Cari PID server yang **benar-benar** memegang port (bukan PID proses
`uvicorn.exe` wrapper):
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
```
Pakai PID yang muncul, lalu jalankan sampler di terminal ini:
```powershell
Start-Process python -ArgumentList "telemetry\sampler.py --pid <PID_DARI_ATAS> --out scratch\telemetry.csv --interval 1.0" -NoNewWindow -PassThru
```
Di terminal yang sama, beri beban ringan beberapa detik:
```powershell
1..50 | ForEach-Object -Parallel {
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/baseline?density=high&seed=$_" -UseBasicParsing | Out-Null
} -ThrottleLimit 10
```
Tunggu ~5 detik, lalu hentikan sampler (`Get-Process python | Stop-Process`
kalau perlu, atau Ctrl+C bila dijalankan foreground), lalu cek:
```powershell
Get-Content scratch\telemetry.csv
```
**Kriteria terima**: kolom `unix_ts,pid,cpu_percent,rss_mb`, dan `cpu_percent`
naik di atas 0 selama window beban, lalu turun ke 0 saat idle lagi.

## 10. (Opsional) Liveness konkurensi — bukan benchmark
Skrip sudah dibuat di `scratch\concurrency_liveness.py`. Cukup jalankan
(REST & GraphQL harus hidup):
```powershell
python scratch\concurrency_liveness.py
```
**Kriteria terima**: `errors=0` dan `missing_header=0` untuk REST maupun
GraphQL. Jangan menyimpulkan siapa lebih cepat dari angka apa pun di sini —
itu baru valid lewat k6 + CPU pinning di VM.

## 11. Selesai — matikan server
Di Terminal #1 dan #2, tekan `Ctrl+C`. Atau dari terminal lain:
```powershell
Get-NetTCPConnection -LocalPort 8000,8001 -State Listen |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

## Troubleshooting cepat
| Gejala | Sebab kemungkinan | Solusi |
|---|---|---|
| `ModuleNotFoundError: No module named 'core'` | File belum berada di `core/` (ter-flatten lagi) | Pastikan struktur folder seperti di bagian atas dokumen ini |
| `Invoke-WebRequest`/`curl` connection refused | Server belum selesai start atau port salah | Cek log di Terminal #1/#2, pastikan `Uvicorn running on http://127.0.0.1:PORT` muncul |
| Sampler `psutil.NoSuchProcess` langsung keluar | PID yang dipakai bukan PID asli pemegang port | Pakai `Get-NetTCPConnection -LocalPort <port> -State Listen` untuk PID yang benar |

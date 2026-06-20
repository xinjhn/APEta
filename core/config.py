"""
core/config.py
==============
Konstanta terpusat untuk seluruh APE. Menyatukan keputusan desain yang sudah
dikunci agar tidak tersebar (dan tidak mungkin berbeda antar-protokol).

Rujukan keputusan:
- Tier densitas berbasis kuartil          -> Laporan Subbab IV.1.2 (Tabel IV.1)
- Spesifikasi kueri KONSTAN lintas tier    -> Keputusan 1 (anti-confounding;
  Montgomery, 2017). Lihat matriks justifikasi, Blok B.
- Whitelist field (skema VCD)              -> Laporan Cuplikan Kode IV.1
"""

# --- Nama tier densitas (urut naik; dipakai juga sebagai urutan uji tren JT) ---
DENSITY_TIERS = ("low", "medium", "high")

# --- Ambang kuartil default (DARI OUTPUT MODEL, Tabel IV.1) ---------------------
# CATATAN: angka ini WAJIB diverifikasi ulang dari distribusi jumlah deteksi
# output model setelah inferensi final (lih. PANDUAN Bagian 9). Pool dapat
# menghitung ulang Q1/Q3 langsung dari data via core.pool.compute_quartiles().
DEFAULT_Q1 = 42  # batas atas tier 'low'   (low  = count < Q1, mis. 1-41)
DEFAULT_Q3 = 96  # batas bawah tier 'high' (high = count > Q3, mis. >96)

# --- Field kanonik skema VCD (snake_case = sumber kebenaran tunggal) ------------
# Kedua server memakai penamaan identik ini. GraphQL DINONAKTIFKAN auto-camelCase
# (lihat graphql_server.py) supaya nama field -- dan karenanya UKURAN PAYLOAD --
# identik dengan REST. Ini menutup bias payload_size akibat 'classLabel' (10 char)
# vs 'class_label' (11 char). Lihat catatan fairness di README.
DETECTION_FIELDS = ("class_label", "confidence_score", "bounding_box")

# --- Spesifikasi 4 pola kueri (KONSTAN lintas ketiga tier densitas) -------------
# Inilah inti Keputusan 1: spesifikasi tidak boleh berubah mengikuti tier,
# agar 'densitas' menjadi faktor murni dan uji tren Jonckheere-Terpstra valid.
PATTERN_SPEC = {
    # S1: seluruh field, seluruh deteksi
    "baseline": {"fields": DETECTION_FIELDS, "filter": None},
    # S2: hanya class_label + confidence_score (membuang bounding_box yang berat)
    "partial": {"fields": ("class_label", "confidence_score"), "filter": None},
    # S3: predikat tetap class_label='car' AND confidence_score>=0.5
    #     (kelas 'car' sebaiknya dikonfirmasi empiris dari profiling kelas; lihat
    #      tools/profile_dataset.py. Array kosong adalah hasil VALID, bukan error.)
    "filtered": {
        "fields": DETECTION_FIELDS,
        "filter": {"class_label": "car", "min_confidence": 0.5},
    },
    # S4: ringkasan jumlah objek per kelas (payload minimal -> mengukur proses)
    "aggregate": {"fields": None, "filter": None},
}

# Nama header server-side processing time (dibaca k6). Simetris di kedua server.
PROCESS_TIME_HEADER = "X-Process-Time"

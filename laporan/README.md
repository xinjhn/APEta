# Laporan Workspace

Folder ini berisi workspace pendukung penyusunan laporan TA untuk penelitian
APE. Dokumen di sini bukan pengganti template Word resmi, melainkan master
content yang dapat dipindahkan ke template:

- Template resmi: `/home/ubuntu/APE/2026 Template Laporan TA JTK-[R]-STr TI (RevMei2026) (1).docx`
- Kode eksperimen: `/home/ubuntu/APE/APEta`
- Data dan pipeline YOLO/VisDrone: `/home/ubuntu/training` dan `/home/ubuntu/datasets`

Struktur:

- `REPORT_MAP.md`: peta isi laporan berdasarkan struktur template TA.
- `FIGURE_REGISTER.md`: daftar gambar yang relevan, dasar referensi, caption, dan file sumber.
- `REFERENCES_BASIS.md`: basis pustaka/standar untuk diagram dan narasi teknis.
- `figures/src/`: sumber diagram yang dapat dirender atau dipindahkan ke draw.io/Word.
- `reproducibility/`: catatan replikasi eksperimen dan inventaris workspace.

Konvensi caption awal:

> Sumber: diolah penulis berdasarkan implementasi sistem; notasi mengacu pada
> [basis referensi yang sesuai].

Catatan penting:

- Phase 1 tetap didokumentasikan sebagai studi pendahuluan/pilot yang memicu
  perbaikan metodologi.
- Phase 2 menjadi desain eksperimen utama karena sudah memasukkan kontrol
  caching, akses data relasional, APQ-over-GET, pola akses, bobot payload,
  entropi query, profil jaringan, dan orkestrasi yang lebih ketat.


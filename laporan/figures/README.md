# Figures

Folder ini menyimpan sumber gambar laporan.

- `src/*.mmd`: sumber Mermaid yang mudah direview.
- `export/`: tempat hasil render PNG/SVG jika renderer tersedia.

Konvensi:

- Nama file diawali `fig_XX_`.
- Setiap file sumber memuat komentar singkat: nomor rencana, tipe diagram,
  basis referensi, dan sumber caption.
- Diagram BPMN saat ini dibuat dalam bentuk "BPMN-style process" dengan
  Mermaid agar mudah direview. Untuk final Word, diagram tersebut dapat
  digambar ulang sebagai BPMN 2.0.2 penuh di draw.io/BPMN.io bila dosen
  meminta notasi BPMN strict.

Catatan rendering:

- Jika `mmdc` tersedia, file Mermaid dapat dirender ke SVG/PNG.
- Jika tidak tersedia, sumber `.mmd` dapat ditempel ke Mermaid Live Editor,
  draw.io, atau plugin Mermaid pada editor.


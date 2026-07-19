# Jawaban siap pakai: Mengapa SQLite, bukan MongoDB atau Neo4j?

SQLite dipilih bukan karena diasumsikan selalu lebih cepat, melainkan karena
tujuan eksperimen adalah mengisolasi pengaruh paradigma API REST dan GraphQL.
Kedua API mengakses file, skema, indeks, DAL, dan kueri SQLite yang sama. Dengan
demikian, basis data menjadi variabel kontrol dan tidak dapat menjelaskan
perbedaan antarprotokol.

Pilihan tersebut juga sesuai dengan karakteristik sistem yang benar-benar
diuji. Korpus berukuran sekitar 9,0 MiB dan berisi 2.846 image, 5.429 track,
serta 104.767 detection. Selama eksperimen API, korpus hanya dibaca, berada pada
host yang sama dengan satu proses server, dan tidak menerima penulisan konkuren.
Dokumentasi resmi SQLite menempatkan penyimpanan lokal, konkurensi penulis yang
rendah, dan data berukuran di bawah satu berkas lokal sebagai use case yang
sesuai. SQLite justru perlu dievaluasi ulang apabila data dipisahkan melalui
jaringan, aplikasi memakai beberapa server, atau terdapat banyak penulis
konkuren ([SQLite, Appropriate Uses](https://www.sqlite.org/whentouse.html)).

MongoDB tetap merupakan alternatif yang valid, khususnya apabila data detection
selalu dibaca bersama image. Model dokumen dapat menanamkan detection ke dalam
image agar satu kebutuhan baca diselesaikan dalam satu dokumen, sesuai panduan
resmi MongoDB. Namun, kebutuhan trajectory juga menyebabkan data detection perlu
direferensikan atau diduplikasi pada dokumen track. Hal itu menambah trade-off
konsistensi dan penyimpanan yang tidak memberi keuntungan fungsional pada korpus
relasional, kecil, dan read-only ini ([MongoDB, Embedded Data](https://www.mongodb.com/docs/manual/data-modeling/embedding/)).

Neo4j juga dapat memodelkan Sequence–Image–Detection–Track sebagai node dan
relationship. Keunggulan utama basis data graf relevan ketika pertanyaan sistem
berpusat pada traversal relasi yang dalam, path finding, atau pola hubungan yang
berubah-ubah. Skenario M1–M6 penelitian ini hanya memakai point lookup, agregasi,
dan traversal satu atau dua hop dengan window yang dibatasi. Karena itu,
kemampuan graf tidak menjadi faktor yang sedang diuji, sedangkan server Java,
driver Bolt, serta model graf menambah variabel operasional
([Neo4j, Graph Database](https://neo4j.com/docs/getting-started/graph-database/)).

Untuk menguji keputusan tersebut secara empiris, dibuat eksperimen sensitivitas
basis data yang menjalankan lima operasi logis M1–M6 pada SQLite, MongoDB, dan
Neo4j. Kasus permintaan dibuat deterministik dan distratifikasi menurut density,
window, serta ukuran batch. Hasil setiap backend harus identik berdasarkan hash
kanonik sebelum latensi boleh dianalisis. Urutan backend diacak per kasus dan
hasil dianalisis secara berpasangan dengan Wilcoxon signed-rank serta koreksi
Holm. Pada run utama, seluruh 13.500 pengukuran lolos paritas. Median keseluruhan
database-call adalah 0,226 ms untuk SQLite, 1,474 ms untuk MongoDB, dan 3,314 ms
untuk Neo4j. Setelah sepuluh kasus dalam setiap cell diringkas menjadi median per
blok, SQLite tetap memiliki median terendah pada seluruh 30 blok di seluruh 15
cell. Semua perbandingan berpasangan tetap signifikan setelah koreksi Holm
(p terkoreksi terbesar 1,73×10^-6). Oleh sebab itu, simpulan yang dipertahankan
adalah **SQLite paling sesuai untuk ruang lingkup eksperimen ini**, bukan SQLite
paling unggul untuk semua sistem produksi.

Catatan batas klaim: eksperimen sensitivitas basis data membenarkan pemilihan
backend, tetapi tidak mengukur interaksi antara jenis API dan database. Jika
yang ditanyakan adalah apakah peringkat REST–GraphQL berlaku pada semua database,
desain lanjutan yang tepat adalah faktorial 2×3 (REST/GraphQL ×
SQLite/MongoDB/Neo4j) dengan kontrak respons yang sama.

## Tambahan: SQLite dibandingkan PostgreSQL

Hasil SQLite yang lebih rendah tidak boleh disebut bukti bahwa "database
relasional mengurangi I/O", karena SQLite juga menghilangkan batas proses dan
network database. Eksperimen lanjutan mempertahankan skema relasional, indeks,
baris, dan operasi logis yang sama, lalu membandingkan SQLite 3.50.4 dengan
PostgreSQL 18.4. Seluruh 9.000 hasil lolos paritas. Median database-call adalah
0,181 ms pada SQLite dan 1,368 ms pada PostgreSQL; SQLite memiliki median lebih
rendah pada seluruh 30 blok di seluruh 15 cell.

Namun, diagnostik PostgreSQL setelah warm-up menunjukkan buffer-hit 100%, nol
shared block read, dan nol waktu tunggu read. Artinya, selisih tersebut bukan
akibat pembacaan disk. Interpretasi yang tepat adalah overhead jalur akses
client/server, driver, penjadwalan antarproses, planning bila terjadi, dan
eksekusi engine. PostgreSQL tetap lebih tepat apabila kebutuhan berubah menjadi
multi-server, database remote/terpusat, atau banyak penulis konkuren.

# Pengujian Hesk API Wrapper

Dokumen ini mencatat pengujian semua endpoint Hesk API Wrapper pada 27 Oktober 2026, sebelum dan sesudah perbaikan.

## Ringkasan

| Endpoint | Sebelum perbaikan | Sesudah perbaikan |
|---|---|---|
| `GET /` | Berfungsi | Berfungsi |
| `GET /api/tickets/{trackid}` | Berfungsi | Berfungsi |
| `GET /api/tickets/user/{u_email}` | Berfungsi | Berfungsi |
| `GET /api/tickets/{trackid}/replies` | Berfungsi | Berfungsi |
| `POST /api/tickets/` | Gagal (`500`) | Berfungsi |
| `POST /api/tickets/{trackid}/replies` | Gagal (`500`) | Berfungsi |
| `PATCH /api/tickets/{trackid}/close` | Berfungsi, riwayat tidak dicatat | Berfungsi |
| `POST /api/tickets/{trackid}/attachments` | Respons sukses, tapi lampiran tidak dikenali Hesk | Berfungsi |

Semua endpoint, termasuk `GET /`, memerlukan header `X-API-Key`.

## Lingkungan

- Hesk 3.6.4 di `/var/www/hesk` pada server `192.168.80.143`, dengan akun pelanggan aktif (`customer_accounts=1`).
- Database MariaDB `hesk`, diakses lewat SSH tunnel. Tabel Hesk memakai engine **MyISAM**, yang tidak mendukung transaksi, sehingga setiap perubahan dari endpoint tulis langsung tersimpan permanen dan tidak bisa di-rollback.
- Server uji: uvicorn di `http://127.0.0.1:8001`.

Data yang dipakai:

- Tiket yang sudah ada: `LSR-UM7-8ZD2`. Hanya dipakai untuk endpoint baca.
- Email pelanggan: `test@example.com`.
- Tiket uji yang dibuat saat pengujian: `VZT-RWT-ZATL`. Endpoint tulis hanya dijalankan pada tiket ini.

## Cara menjalankan pengujian

```bash
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8001 --workers 1

# Di terminal lain
set -a; source .env; set +a
B=http://127.0.0.1:8001
H="X-API-Key: $API_KEY"
```

Endpoint tulis membuat atau mengubah data Hesk secara permanen. Jalankan hanya pada tiket uji, atau pada salinan database.

## Hasil pengujian setelah perbaikan

### Autentikasi

| Kasus | Perintah | Hasil yang diharapkan | Hasil |
|---|---|---|---|
| Tanpa API key | `curl $B/` | `401` | `401` |
| API key salah | `curl -H "X-API-Key: salah" $B/api/tickets/LSR-UM7-8ZD2` | `401` | `401` |
| API key benar | `curl -H "$H" $B/` | `200`, `database_status: Terhubung` | `200`, `Terhubung` |
| Upload tanpa API key | `curl -F "file=@uji.pdf" $B/api/tickets/X/attachments` | `401` | `401` |

### Endpoint baca

| Kasus | Perintah | Hasil yang diharapkan | Hasil |
|---|---|---|---|
| Ambil tiket yang ada | `curl -H "$H" $B/api/tickets/LSR-UM7-8ZD2` | `200` dan data tiket | `200` |
| Ambil tiket yang tidak ada | `curl -H "$H" $B/api/tickets/TIDAKADA123` | `404` | `404`, `Tiket tidak ditemukan` |
| Tiket milik email | `curl -H "$H" $B/api/tickets/user/test@example.com` | `200` dan daftar tiket | `200`, 6 tiket (termasuk tiket uji baru) |
| Balasan tiket | `curl -H "$H" $B/api/tickets/LSR-UM7-8ZD2/replies` | `200` dan daftar balasan | `200`, 5 balasan |

### Membuat tiket (`POST /api/tickets/`)

| Kasus | Body | Hasil yang diharapkan | Hasil |
|---|---|---|---|
| Kategori tidak ada | `"category": 99999` | `400` | `400`, `Kategori tidak ditemukan` |
| Email tidak valid | `"u_email": "bukan-email"` | `422` | `422` |
| Data valid | `u_name`, `u_email: test@example.com`, `subject: [API TEST] pengujian endpoint`, `message`, `category: 21` | `200` dan trackid baru | `200`, trackid `VZT-RWT-ZATL` |

Contoh request:

```bash
curl -H "$H" -H 'Content-Type: application/json' \
  -d '{"u_name":"API test","u_email":"test@example.com","subject":"[API TEST] pengujian endpoint","message":"Baris satu <b>bold?</b>\nBaris dua","category":21}' \
  $B/api/tickets/
```

Pemeriksaan langsung di database untuk tiket `VZT-RWT-ZATL`:

- Trackid berformat Hesk (`XXX-XXX-XXXX`).
- `dt` (waktu dibuat), `ip`, dan riwayat `submitted by Customer` terisi.
- HTML di pesan tersimpan dalam bentuk ter-escape (`&lt;b&gt;`), dan baris baru di `message_html` menjadi `<br />`.
- Tiket terhubung ke pelanggan `test@example.com` (customer id 4) di `hesk_ticket_to_customer` sebagai `REQUESTER`.

### Mengirim balasan (`POST /api/tickets/{trackid}/replies`)

| Kasus | Hasil yang diharapkan | Hasil |
|---|---|---|
| Tiket tidak ada | `404` | `404` |
| Balasan ke `VZT-RWT-ZATL` | `200` | `200` |
| Daftar balasan setelahnya | Balasan baru muncul | 1 balasan |

Pemeriksaan di database:

- Balasan tersimpan dengan `dt` terisi, `staffid` 0, dan `customer_id` 4.
- Tiket: `replies` menjadi 1 dan `lastreplier` menjadi `0` (pelanggan).
- Status tiket menjadi `1` ("Waiting reply").

### Lampiran (`POST /api/tickets/{trackid}/attachments`)

| Kasus | File | Hasil yang diharapkan | Hasil |
|---|---|---|---|
| Tiket tidak ada | `a.pdf` | `404` | `404` |
| Ekstensi tidak diizinkan | `virus.exe` | `400` | `400`, `Ekstensi file tidak diizinkan` |
| File lebih dari 2 MB | `../../evil.pdf` (±2,1 MB) | `413` | `413`, `Ukuran file melebihi 2 MB` |
| Nama file berisi path | `../../laporan uji.pdf` | `200`, nama dibersihkan | `200`, disimpan sebagai `laporan-uji.pdf` |

Pemeriksaan di database dan server Hesk:

- Baris baru di `hesk_attachments`: `att_id` 5, `real_name` `laporan-uji.pdf`, ukuran 26 byte.
- Kolom `attachments` tiket berisi `5#laporan-uji.pdf,`, sama dengan format yang dipakai Hesk.
- File ada di `/var/www/hesk/attachments/VZT-RWT-ZATL_<hash>.pdf`, milik `www-data:www-data`, izin `644`.
- Tidak ada file `evil` di folder lampiran maupun di `/var/www`.

### Menutup tiket (`PATCH /api/tickets/{trackid}/close`)

| Kasus | Hasil yang diharapkan | Hasil |
|---|---|---|
| Tiket tidak ada | `404` | `404` |
| Tutup `VZT-RWT-ZATL` | `200`, status `3` | `200`, status `3` |

Pemeriksaan di database: `closedat` terisi, `closedby` 0, dan riwayat bertambah `closed by Customer`.

## Masalah yang ditemukan sebelum perbaikan

1. **Membuat tiket gagal (`500`).** MariaDB menolak insert dengan `Field 'merged' doesn't have a default value`. Tabel Hesk mewajibkan `merged`, `history`, dan `custom1` sampai `custom100`, yang tidak diisi API. Request tanpa `attachments` juga ditolak `422`, dan trackid yang dibuat tidak berformat Hesk.
2. **Mengirim balasan gagal (`500`).** `TypeError: 'staffid' is an invalid keyword argument for Reply`, karena model `Reply` tidak punya kolom `staffid`. Status tiket juga dikembalikan ke `0` ("New"), bukan "Waiting reply".
3. **Lampiran tidak dikenali Hesk.** File disimpan di folder `attachments/` di server wrapper, kolom `attachments` diisi `trackid_namafile`, dan tidak ada baris di `hesk_attachments`. Nama file dipakai apa adanya di path, sehingga nama seperti `../../x.pdf` bisa menulis file di luar folder lampiran.
4. **API key bisa dilewati.** Kalau `API_KEY` kosong dan request tidak mengirim header, perbandingan `None == None` membuat request lolos.

## Perbaikan

| File | Perubahan |
|---|---|
| `models.py` | Menambah kolom wajib Hesk di `Ticket` (termasuk `custom1`–`custom100`), kolom `Reply` yang kurang, serta model `Attachment`, `Customer`, `TicketToCustomer`, dan `Category`. |
| `schemas.py` | Memisahkan schema request dan response, menambah validasi input (email, panjang teks, prioritas 0–3), dan `attachments` tidak lagi wajib di request. |
| `routers/tickets.py` | Pembuatan tiket mengikuti format Hesk, balasan dan penutupan memperbarui data tiket seperti Hesk, dan lampiran disimpan lewat alur Hesk dengan batas ekstensi, ukuran, dan nama file yang dibersihkan. |
| `hesk_storage.py` | File baru untuk mengunggah dan menghapus lampiran di server Hesk lewat SSH. |
| `dependencies.py` | Menolak semua request jika `API_KEY` kosong, dan membandingkan kunci dengan `secrets.compare_digest`. |
| `.env` | Menambah `HESK_ATTACH_DIR=/var/www/hesk/attachments`. |
| `requirements.txt` | Menambah `python-multipart`, yang dibutuhkan upload file. |

## Catatan

- **Data uji yang tertinggal.** Tiket `VZT-RWT-ZATL` (subjek `[API TEST] pengujian endpoint`) beserta satu balasan dan lampiran `laporan-uji.pdf` tetap ada di Hesk dengan status ditutup. Hapus dari panel admin Hesk jika tidak diperlukan.
- **Perubahan pada tiket `9ET-QZW-MDZ8`.** Pada pengujian sebelum perbaikan, tiket ini sempat ditutup dan kolom lampirannya terisi, karena rollback tidak berlaku di MyISAM. Status dan lampirannya sudah dikembalikan ke nilai awal, tetapi `lastchange`-nya ikut berubah menjadi 27 Oktober 2026 14:52 WIB.
- **IP di tiket adalah IP pemanggil API.** Di produksi, yang tercatat adalah IP server portal RuangKerja, bukan IP pengguna akhir.

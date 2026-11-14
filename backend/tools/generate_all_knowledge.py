import json
import os
from pathlib import Path

KNOWLEDGE_DIR = Path("d:/coding/FalakHub/backend/knowledge")
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

# 1. DASAR FALAK
falak_dasar = [
    {
        "id": "falak_01_hisab_rukyat",
        "topik": "Perbedaan Hisab dan Rukyat",
        "kata_kunci": ["hisab", "rukyat", "hisab vs rukyat", "perbedaan hisab rukyat", "metode penentuan bulan"],
        "ringkasan_singkat": "Hisab adalah metode perhitungan matematis dan astronomis posisi benda langit, sedangkan rukyat adalah observasi visual langsung kemunculan hilal sesaat setelah matahari terbenam. Keduanya saling melengkapi dalam khazanah falak Islam.",
        "penjelasan_lengkap": "Dalam astronomi Islam, Hisab (astronomical calculation) menggunakan hukum fisika dan matematika celestial untuk memprediksi posisi matahari dan bulan secara presisi tinggi, seperti algoritma Jean Meeus atau ephemeris NASA JPL DE421. Sementara Rukyatul Hilal bil Fi'li adalah pengamatan empiris di lapangan menggunakan mata telanjang atau teleskop saat matahari terbenam pada hari ke-29 bulan Hijriah. Ulama kontemporer memadukan keduanya: hisab sebagai penentu arah dan visibilitas hilal, sedangkan rukyat sebagai verifikasi faktual lapangan.",
        "sumber": "Kompilasi Temu Pakar Falak Kemenag RI & Fiqh Falak Modern",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "falak_02_ijtimak",
        "topik": "Ijtimak atau Konjungsi Astronomis",
        "kata_kunci": ["ijtimak", "konjungsi", "conjunction", "ijtima", "bulan mati", "new moon"],
        "ringkasan_singkat": "Ijtimak atau konjungsi adalah peristiwa astronomis ketika bumi, bulan, dan matahari berada pada satu bujur ekliptika yang sama. Ini adalah batas astronomis berakhirnya bulan kamariyah lama dan mulainya bulan baru.",
        "penjelasan_lengkap": "Ijtimak (geocentric conjunction) terjadi ketika posisi geosentris Bulan dan Matahari memiliki bujur ekliptika (ecliptic longitude) yang sama. Secara astronomis, fase ini menandai 'bulan mati' di mana sisi bulan yang menghadap bumi tidak memantulkan cahaya matahari. Dalam penentuan kalender Hijriah, ijtimak merupakan syarat mutlak; hilal tidak mungkin terbentuk atau terlihat sebelum terjadinya ijtimak.",
        "sumber": "Ephemeris Hisab Rukyat Kemenag RI & Jean Meeus Astronomical Algorithms",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "falak_03_wujudul_hilal",
        "topik": "Kriteria Wujudul Hilal",
        "kata_kunci": ["wujudul hilal", "kriteria muhammadiyah", "wujud hilal", "kapan wujudul hilal"],
        "ringkasan_singkat": "Wujudul Hilal adalah kriteria penanggalan Hijriah yang menetapkan bulan baru telah masuk jika telah terjadi ijtimak sebelum matahari terbenam dan piringan atas bulan masih berada di atas ufuk saat matahari terbenam, berapapun ketinggiannya.",
        "penjelasan_lengkap": "Prinsip Wujudul Hilal yang dipedomani oleh Muhammadiyah mensyaratkan tiga parameter kumulatif: 1) Telah terjadi ijtimak, 2) Ijtimak terjadi sebelum matahari terbenam (ghurub), dan 3) Saat matahari terbenam, piringan atas bulan masih berada di atas ufuk hakiki (ketinggian > 0 derajat). Kriteria ini tidak mensyaratkan hilal harus bisa dilihat secara fisik dengan mata, melainkan cukup secara eksistensi geometris astronomis.",
        "sumber": "Majelis Tarjih dan Tajdid PP Muhammadiyah",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "falak_04_mabims_2021",
        "topik": "Kriteria Imkanur Rukyat MABIMS 2021 (Kriteria Baru)",
        "kata_kunci": ["mabims", "mabims 2021", "kriteria baru mabims", "imkanur rukyat", "syarat hilal kemenag", "3 derajat 6.4 derajat"],
        "ringkasan_singkat": "Kriteria baru MABIMS 2021 menyepakati bahwa hilal dianggap mungkin terlihat (imkanur rukyat) jika saat maghrib tinggi hilal mar'i minimal 3 derajat dan sudut elongasi geosentris minimal 6,4 derajat.",
        "penjelasan_lengkap": "Kriteria MABIMS (Menteri Agama Brunei, Indonesia, Malaysia, dan Singapura) diperbarui pada 2021 dan mulai diterapkan resmi oleh Kemenag RI pada 1443 H/2022 M. Kriteria ini menggantikan standar lama (2 derajat tinggi, 3 derajat elongasi). Nilai 3 derajat memperhitungkan refraksi dan ketebalan lapisan polusi serta uap air di ufuk, sementara elongasi 6,4 derajat memastikan ketebalan sabit bulan dan kontras cahaya hilal cukup terang melampaui sisa cahaya senja (twilight).",
        "sumber": "Kesepakatan Menteri Agama Brunei Darussalam, Republik Indonesia, Malaysia, dan Singapura (MABIMS) 2021",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "falak_05_mabims_lama",
        "topik": "Kriteria MABIMS Lama (Kriteria 2-3-8)",
        "kata_kunci": ["mabims lama", "kriteria lama kemenag", "2 derajat", "kriteria 2 3 8"],
        "ringkasan_singkat": "Kriteria lama MABIMS mensyaratkan tinggi hilal minimal 2 derajat, elongasi 3 derajat, atau umur bulan minimal 8 jam sejak ijtimak. Kriteria ini telah dihentikan penggunaannya sejak 2021 karena dinilai terlalu rendah secara sains astronomi modern.",
        "penjelasan_lengkap": "Kriteria lama MABIMS dirumuskan pada akhir abad ke-20 dengan parameter minimal tinggi 2 derajat dan elongasi 3 derajat, atau umur bulan 8 jam. Namun, berdasarkan riset astronomi modern (seperti catatan visibilitas Odeh dan LAPAN/BRIN), hilal pada ketinggian 2 derajat di wilayah tropis hampir mustahil dilihat mata maupun teleskop karena kontras cahaya redup terkubur hamburan cahaya senja. Oleh karena itu disepakati pembaharuan menjadi 3 derajat dan 6,4 derajat pada 2021.",
        "sumber": "Dokumen Sejarah Hisab Rukyat Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "falak_06_kriteria_nu",
        "topik": "Kriteria Nahdlatul Ulama (LF PBNU)",
        "kata_kunci": ["kriteria nu", "lf pbnu", "rukyat nu", "sidang isbat nu", "nahdlatul ulama falak"],
        "ringkasan_singkat": "Lembaga Falakiyah PBNU berpegang pada metode rukyatul hilal bil fi'li yang dipadukan dengan hisab imkanur rukyat MABIMS baru (3 derajat dan elongasi 6,4 derajat) sebagai filter saintifik keabsahan laporan rukyat.",
        "penjelasan_lengkap": "Bagi Nahdlatul Ulama, penetapan awal bulan qamariyah mensyaratkan kesaksian rukyatul hilal langsung yang disumpah di hadapan hakim pengadilan agama. Namun, LF PBNU menggunakan hisab kontemporer presisi tinggi sebagai batas filter ilmiah: jika hisab menunjukkan hilal masih di bawah kriteria imkanur rukyat MABIMS, maka laporan penglihatan hilal yang masuk akan ditolak atau diverifikasi sangat ketat karena patut diduga salah lihat (misalnya objek bintang, pantulan awan, atau ilusi optik).",
        "sumber": "Pedoman Penentuan Awal Bulan Qamariyah LF PBNU",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "falak_07_toposentris_geosentris",
        "topik": "Perbedaan Toposentris dan Geosentris",
        "kata_kunci": ["toposentris", "geosentris", "topocentric", "geocentric", "beda lihat", "parallax"],
        "ringkasan_singkat": "Geosentris adalah posisi benda langit jika dilihat dari titik pusat bumi, sedangkan toposentris adalah posisi nyata jika dilihat dari permukaan tempat pengamat berdiri. Posisi toposentris memperhitungkan paralaks dan refraksi tempat pengamat.",
        "penjelasan_lengkap": "Karena bumi berbentuk bulat dengan radius sekitar 6.371 km, posisi bulan relatif terhadap pengamat di permukaan bumi berbeda dari posisi terhadap titik pusat bumi. Selisih sudut ini disebut paralaks (beda lihat horizontal). Pada posisi toposentris, ketinggian bulan selalu terlihat lebih rendah sekitar 0,8 hingga 1 derajat dibandingkan ketinggian geosentrisnya. Kriteria MABIMS 2021 menggunakan tinggi toposentris/mar'i dan elongasi geosentris.",
        "sumber": "Buku Astronomi Praktis & Ephemeris Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "falak_08_parameter_hisab",
        "topik": "Parameter-Parameter Penting Hisab Hilal",
        "kata_kunci": ["elongasi", "azimuth", "altitude", "refraksi", "dip", "semidiameter", "umur bulan", "parameter hisab"],
        "ringkasan_singkat": "Parameter hisab hilal mencakup altitude (tinggi), azimuth (arah kompas), elongasi (sudut pisah bulan-matahari), refraksi (pembiasan atmosfer), dip (kerendahan ufuk), semidiameter (jari-jari piringan), dan umur bulan.",
        "penjelasan_lengkap": "1) Altitude/Tinggi: sudut vertikal dari ufuk pengamat ke pusat piringan bulan. 2) Azimuth: arah busur horizontal diukur dari Utara Sejati (0-360 derajat). 3) Elongasi: jarak busur sudut antara pusat matahari dan bulan. 4) Refraksi Atmosfer: pembelokan berkas cahaya akibat atmosfer bumi yang membuat benda langit tampak lebih tinggi ~34 menit busur di dekat ufuk. 5) Dip (Kerendahan Ufuk): koreksi penurunan ufuk mar'i akibat elevasi ketinggian pengamat di atas permukaan laut. 6) Semidiameter: jari-jari sudut penampakan piringan bulan (~15-16 menit busur). 7) Umur Bulan: selang waktu dari ijtimak hingga matahari terbenam.",
        "sumber": "Pedoman Ephemeris Hisab Rukyat Kemenag RI & Jean Meeus",
        "tingkat_keyakinan": "tinggi"
    }
]

# 2. WAKTU SALAT
waktu_salat = [
    {
        "id": "salat_01_subuh_imsak",
        "topik": "Waktu Subuh dan Imsak",
        "kata_kunci": ["subuh", "imsak", "fajar shadiq", "sudut subuh", "20 derajat subuh", "waktu subuh"],
        "ringkasan_singkat": "Waktu Subuh dimulai saat terbitnya fajar shadiq, yaitu cahaya putih melintang di ufuk timur. Kemenag RI menetapkan ketinggian matahari -20 derajat di bawah ufuk. Waktu imsak ditetapkan sekitar 10 menit sebelum azan Subuh sebagai bentuk kehati-hatian.",
        "penjelasan_lengkap": "Secara syar'i, batas awal salat Subuh adalah fajar shadiq (astronomical dawn). Di Indonesia, Kementerian Agama menetapkan sudut depresi matahari -20 derajat (didukung oleh hisab para ulama nusantara terdahulu). Sebagian lembaga internasional seperti MWL atau ISNA menggunakan sudut -18 derajat atau -15 derajat tergantung letak lintang geografis. Waktu imsak (menahan diri) adalah tradisi kehati-hatian (ihtiyath) warisan ulama Syafi'iyah di Nusantara berjarak sekitar 50 ayat Al-Qur'an atau setara 10 menit sebelum azan subuh berkumandang.",
        "sumber": "Pedoman Penentuan Jadwal Waktu Salat Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "salat_02_terbit_dhuha",
        "topik": "Waktu Terbit (Syuruq) dan Waktu Dhuha",
        "kata_kunci": ["terbit", "syuruq", "dhuha", "ketinggian dhuha", "satu tombak", "waktu dhuha"],
        "ringkasan_singkat": "Terbit atau syuruq terjadi ketika piringan atas matahari menyentuh ufuk hakiki (ketinggian sekitar -0,833 derajat). Salat Dhuha dimulai ketika matahari naik setinggi satu tombak atau sekitar 3,5 hingga 4,5 derajat di atas ufuk (sekitar 15-20 menit setelah terbit).",
        "penjelasan_lengkap": "Waktu syuruq menandai berakhirnya waktu subuh, saat piringan atas matahari mulai muncul di ufuk mar'i timur. Ketinggian matematis titik tengah matahari saat itu adalah -50 menit busur (-0,833 derajat) memperhitungkan refraksi 34 menit dan semidiameter 16 menit. Waktu dhuha dimulai ketika matahari naik setinggi 'qadra rumh' (kira-kira 3,5 derajat hingga 4,5 derajat atau setara 15-20 menit pasca syuruq) dan berakhir sesaat sebelum matahari mencapai kulminasi (zawal).",
        "sumber": "Kitab Fathul Qorib & Hisab Praktis Falakiyah",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "salat_03_dzuhur_zawal",
        "topik": "Waktu Dzuhur dan Istiwa (Zawal)",
        "kata_kunci": ["dzuhur", "zawal", "istiwa", "meridian", "kulminasi matahari", "waktu dzuhur"],
        "ringkasan_singkat": "Waktu Dzuhur dimulai saat matahari tergelincir ke arah barat dari garis meridian langit (zawalusy syams). Pada saat tepat di meridian (istiwa'), salat dilarang, dan setelah bergeser sekitar 2 menit waktu Dzuhur resmi masuk.",
        "penjelasan_lengkap": "Istiwa' adalah peristiwa ketika titik tengah matahari tepat melintasi meridian langit lokal (kulminasi atas / transit). Pada saat tepat tengah hari ini, bayangan benda tegak berada pada panjang terpendeknya (bayangan istiwa). Salat dilarang pada detik tepat istiwa' tersebut. Begitu matahari bergeser sedikit ke barat (zawal), waktu Dzuhur masuk. Dalam praktiknya, ditambahkan ikhtiyat (safety margin) sebesar 2 hingga 3 menit dari waktu zawal matematis.",
        "sumber": "Fiqh Sunnah & Ephemeris Hisab Rukyat Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "salat_04_ashar_mazhab",
        "topik": "Waktu Ashar dan Perbedaan Mazhab",
        "kata_kunci": ["ashar", "waktu ashar", "mazhab ashar", "hanafi ashar", "syafii ashar", "panjang bayangan"],
        "ringkasan_singkat": "Waktu Ashar dimulai saat panjang bayangan suatu benda sama dengan tinggi benda tersebut ditambah bayangan istiwa' menurut mayoritas ulama (Syafi'i, Maliki, Hambali). Mazhab Hanafi berpendapat waktu Ashar dimulai saat bayangan mencapai dua kali tinggi benda.",
        "penjelasan_lengkap": "Rumus astronomis waktu Ashar menghitung altitude matahari h: cot(h) = tan(zawal) + n, di mana n adalah faktor rasio bayangan. Mazhab Jumhur (Syafi'i, Maliki, Hambali) menetapkan n = 1 (panjang bayangan sama dengan panjang benda aslinya ditambah sisa bayangan zawal). Mazhab Hanafi menetapkan n = 2 (panjang bayangan dua kali lipat panjang benda ditambah sisa bayangan zawal), sehingga jadwal Ashar mazhab Hanafi lebih lambat sekitar 40-60 menit dibanding mazhab jumhur.",
        "sumber": "Al-Mughni Ibnu Qudamah & Hisab Falakiyah Kontemporer",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "salat_05_maghrib_isya",
        "topik": "Waktu Maghrib dan Isya",
        "kata_kunci": ["maghrib", "isya", "mega merah", "syafaq ahmar", "sudut isya", "waktu maghrib"],
        "ringkasan_singkat": "Waktu Maghrib dimulai saat seluruh piringan matahari terbenam sempurna di bawah ufuk mar'i. Waktu Isya masuk saat mega merah (syafaqul ahmar) di ufuk barat hilang sempurna, dengan ketinggian matahari -18 derajat di bawah ufuk standar Kemenag RI.",
        "penjelasan_lengkap": "Terbenamnya matahari (ghurub) secara syar'i terjadi saat piringan atas matahari telah lenyap di bawah ufuk mar'i (altitude matahari titik tengah = -50' atau -0,833 derajat plus koreksi elevasi). Waktu Maghrib berakhir dan waktu Isya masuk saat cahaya senja merah (syafaqul ahmar / astronomical twilight) telah hilang sepenuhnya. Kemenag RI menetapkan sudut depresi matahari untuk awal Isya adalah -18 derajat di bawah ufuk hakiki, sementara sebagian negara lain menggunakan sudut -17,5 derajat atau -19 derajat.",
        "sumber": "Pedoman Hisab Rukyat Kemenag RI & Fiqh Empat Mazhab",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "salat_06_ikhtiyat",
        "topik": "Konsep Ikhtiyat (Waktu Pengaman)",
        "kata_kunci": ["ikhtiyat", "safety margin", "pengaman jadwal", "koreksi menit salat"],
        "ringkasan_singkat": "Ikhtiyat adalah penambahan waktu sekitar 1 hingga 2 menit pada jadwal salat sebagai langkah kehati-hatian untuk mengantisipasi selisih lintang-bujur daerah, ketinggian tempat, dan pembulatan detik.",
        "penjelasan_lengkap": "Dalam pembuatan jadwal salat suatu kabupaten/kota yang mencakup area berjarak puluhan kilometer, titik koordinat acuan biasanya berada di masjid agung kota. Waktu matahari terbit atau terbenam dapat berbeda beberapa detik hingga 1-2 menit di ujung barat atau timur kabupaten tersebut. Ulama falak menetapkan penambahan ikhtiyat (ihtiyath) umumnya 2 menit (kecuali syuruq yang dikurangi 2 menit untuk keamanan) agar salat dipastikan masuk tepat waktu di seluruh cakupan daerah.",
        "sumber": "Standarisasi Jadwal Salat Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    }
]

# 3. KIBLAT DAN RASHDUL KIBLAT
kiblat_rashdul = [
    {
        "id": "kiblat_01_rumus_azimuth",
        "topik": "Arah Kiblat dan Rumus Perhitungannya",
        "kata_kunci": ["kiblat", "arah kiblat", "azimuth kiblat", "rumus kiblat", "ka'bah", "derajat kiblat"],
        "ringkasan_singkat": "Arah kiblat adalah arah busur terpendek dari posisi pengamat di permukaan bumi menuju Ka'bah di Mekkah (21°25'21\" LU, 39°49'34\" BT). Di Indonesia, arah kiblat berkisar antara 290° hingga 295° dari arah Utara sejati searah jarum jam.",
        "penjelasan_lengkap": "Penentuan arah kiblat menggunakan trigonometri bola (spherical trigonometry) segitiga bola antara Kutub Utara, posisi pengamat (lintang phi, bujur lambda), dan posisi Ka'bah (lintang phi_k = 21,422487° N, bujur lambda_k = 39,826206° E). Rumus matematisnya: tan(Q) = sin(delta_lambda) / [cos(phi)*tan(phi_k) - sin(phi)*cos(delta_lambda)]. Hasil sudut Q diukur dari Utara Sejati ke Barat (sekitar 65-70 derajat dari Barat ke Utara, atau azimuth 290-295 derajat).",
        "sumber": "Ilmu Falak Teori dan Praktik & Pedoman Penentuan Arah Kiblat Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "kiblat_02_rashdul_kiblat_global",
        "topik": "Rashdul Kiblat Global (Istiwa' A'zham)",
        "kata_kunci": ["rashdul kiblat", "istiwa a'zham", "bayangan kiblat", "28 mei", "16 juli", "kalibrasi arah kiblat"],
        "ringkasan_singkat": "Rashdul Kiblat global terjadi dua kali setahun, yaitu pada 28 Mei pukul 16.18 WIB dan 16 Juli pukul 16.27 WIB (atau 27 Mei & 15 Juli pada tahun kabisat). Pada saat itu matahari tepat di atas Ka'bah, sehingga semua bayangan benda tegak lurus mengarah ke kiblat.",
        "penjelasan_lengkap": "Ketika deklinasi matahari tepat sama dengan lintang geografis Ka'bah (21° 25' LU) dan matahari melintasi meridian Ka'bah, posisi matahari berada tepat di zenit Ka'bah. Fenomena ini disebut Istiwa' A'zham atau Rashdul Kiblat Global. Siapapun di belahan bumi yang mengalami siang hari (termasuk Indonesia bagian barat dan tengah) dapat mengalibrasi arah kiblat dengan sangat akurat dan mudah: cukup tancapkan tongkat lurus secara tegak pada bidang datar, bayangan tongkat pada jam tersebut mengarah persis ke arah kiblat.",
        "sumber": "Badan Hisab Rukyat Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "kiblat_03_rashdul_kiblat_harian",
        "topik": "Rashdul Kiblat Harian (Lokal)",
        "kata_kunci": ["rashdul kiblat harian", "bayangan kiblat harian", "kiblat harian", "kalibrasi kiblat lokal"],
        "ringkasan_singkat": "Rashdul Kiblat harian adalah waktu pada setiap hari ketika posisi matahari melintasi azimuth arah kiblat suatu daerah. Pada waktu tersebut, bayangan benda tegak akan sejajar persis dengan garis arah kiblat lokal.",
        "penjelasan_lengkap": "Jika tidak ingin menunggu tanggal 28 Mei atau 16 Juli, penentuan arah kiblat dapat dilakukan setiap hari menggunakan metode Rashdul Kiblat Harian. Menggunakan rumus segitiga bola matahari, dihitung jam berapa azimuth matahari tepat sama dengan azimuth kiblat setempat (atau azimuth kiblat + 180 derajat). Saat jam tersebut tiba di lokasi pengamat, bayangan benda yang berdiri tegak lurus langsung menunjukkan garis arah kiblat.",
        "sumber": "Buku Ilmu Falak Khazanah Islam Modern",
        "tingkat_keyakinan": "tinggi"
    }
]

# 4. KALENDER HIJRIAH
kalender_hijriah = [
    {
        "id": "hijri_01_sistem_kamariyah",
        "topik": "Sistem Kalender Hijriah Kamariyah",
        "kata_kunci": ["kalender hijriah", "kalender kamariyah", "lunar calendar", "panjang tahun hijriah", "12 bulan hijriah"],
        "ringkasan_singkat": "Kalender Hijriah didasarkan pada peredaran bulan mengelilingi bumi (fase sinodis). Satu bulan memiliki panjang 29 atau 30 hari, sehingga satu tahun Hijriah berjumlah 354 atau 355 hari, kira-kira 10-12 hari lebih pendek dari tahun Masehi.",
        "penjelasan_lengkap": "Siklus sinodis bulan (dari ijtimak ke ijtimak berikutnya) rata-rata adalah 29 hari 12 jam 44 menit 2,8 detik (29,53059 hari). Karena hari dalam kalender harus bilangan bulat, maka bulan Hijriah berselang-seling antara 29 dan 30 hari. Total hari dalam 12 bulan adalah sekitar 354,367 hari. Selisih 10,875 hari dengan tahun tropis Masehi (365,2422 hari) menyebabkan musim dan perayaan Islam selalu bergeser maju sekitar 11 hari setiap tahun masehi.",
        "sumber": "Astronomi Islam dan Penanggalan Hijriah",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "hijri_02_urfi_vs_hakiki",
        "topik": "Kalender Hijriah Urfi vs Hakiki",
        "kata_kunci": ["hijriah urfi", "hisab urfi", "hijriah hakiki", "hisab hakiki", "penentuan kalender"],
        "ringkasan_singkat": "Kalender Hijriah Urfi adalah sistem kalender tabel aritmatis dengan pola tetap 30 dan 29 hari, sedangkan Kalender Hakiki didasarkan pada posisi astronomis bulan yang sesungguhnya di langit.",
        "penjelasan_lengkap": "Sistem Urfi (aritmatis) membagi bulan ganjil 30 hari dan genap 29 hari, dengan tahun kabisat (355 hari) sebanyak 11 kali dalam siklus 30 tahun (pada tahun ke-2, 5, 7, 10, 13, 16, 18, 21, 24, 26, dan 29). Sistem urfi sangat praktis untuk keperluan administrasi sipil atau konversi cepat, namun tidak boleh dipakai untuk ibadah (Ramadhan, Idul Fitri, Dzulhijjah). Untuk ibadah, umat Islam wajib berpedoman pada hisab/rukyat hakiki yang mencerminkan posisi fisik hilal yang nyata.",
        "sumber": "Al-Khulashah Al-Wafiyah & Kaidah Fiqh Falak",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "hijri_03_umm_al_qura",
        "topik": "Kalender Umm al-Qura (Arab Saudi)",
        "kata_kunci": ["umm al-qura", "kalender arab saudi", "kriteria umm al qura", "penanggalan mekkah"],
        "ringkasan_singkat": "Kalender Umm al-Qura adalah kalender resmi Arab Saudi. Kriterianya menetapkan bulan baru masuk jika konjungsi terjadi sebelum matahari terbenam di Mekkah dan bulan terbenam setelah matahari terbenam di Mekkah.",
        "penjelasan_lengkap": "Kriteria Umm al-Qura yang berlaku sejak 1423 H menyatakan bahwa awal bulan baru dimulai jika: 1) Ijtimak terjadi sebelum matahari terbenam di koordinat Ka'bah Mekkah, dan 2) Bulan terbenam setelah terbenamnya matahari (moonset after sunset) di Mekkah. Kriteria ini berlaku untuk urusan sipil administratif di Arab Saudi, namun untuk awal Ramadhan, Syawal, dan Dzulhijjah, otoritas kehakiman Arab Saudi tetap menggelar rukyatul hilal resmi.",
        "sumber": "Official Umm al-Qura Calendar Guidelines",
        "tingkat_keyakinan": "tinggi"
    }
]

# 5. GERHANA ASTRONOMI
gerhana_astronomi = [
    {
        "id": "gerhana_01_matahari",
        "topik": "Gerhana Matahari (Kusuf asy-Syams)",
        "kata_kunci": ["gerhana matahari", "kusuf", "solar eclipse", "gerhana total", "gerhana cincin", "gerhana hibrida"],
        "ringkasan_singkat": "Gerhana matahari terjadi ketika bulan melintas di antara bumi dan matahari sehingga menutupi sebagian atau seluruh piringan matahari. Ini hanya terjadi pada fase bulan mati (ijtimak) di dekat simpul orbit bulan.",
        "penjelasan_lengkap": "Orbit bulan memiliki kemiringan sekitar 5,14 derajat terhadap bidang ekliptika bumi. Gerhana matahari hanya terjadi saat ijtimak bertepatan dengan bulan yang berada di dekat salah satu titik potong orbitnya (simpul naik / ascending node atau simpul turun / descending node). Jenis gerhana matahari ada empat: Gerhana Matahari Total (GMT), Gerhana Matahari Sebagian (GMS), Gerhana Matahari Cincin (GMC), dan Gerhana Matahari Hibrida (GMH). Saat gerhana matahari, umat Islam disunnahkan melaksanakan Salat Kusuf.",
        "sumber": "NASA Eclipse Website & Fiqh Salat Kusuf",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "gerhana_02_bulan",
        "topik": "Gerhana Bulan (Khusuf al-Qamar)",
        "kata_kunci": ["gerhana bulan", "khusuf", "lunar eclipse", "gerhana total bulan", "blood moon", "gerhana penumbra"],
        "ringkasan_singkat": "Gerhana bulan terjadi ketika bumi berada persis di antara matahari dan bulan, sehingga bayangan bumi menutupi piringan bulan. Ini selalu terjadi pada fase purnama (istiqbal) di dekat simpul orbit.",
        "penjelasan_lengkap": "Bayangan bumi memiliki dua bagian: kerucut gelap total (umbra) dan kerucut kabur (penumbra). Jenis gerhana bulan meliputi: Gerhana Bulan Total (seluruh piringan bulan masuk ke umbra bumi, sering tampak merah tembaga karena hamburan Rayleigh atmosfer bumi), Gerhana Bulan Sebagian (hanya sebagian bulan masuk umbra), dan Gerhana Bulan Penumbra (bulan hanya melewati bayangan penumbra sehingga cahayanya sedikit meredup). Saat gerhana bulan terlihat, disunnahkan melaksanakan Salat Khusuf.",
        "sumber": "Badan Riset dan Inovasi Nasional (BRIN) & Fiqh Sunnah",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "gerhana_03_salat_gerhana",
        "topik": "Salat Gerhana (Kusuf dan Khusuf)",
        "kata_kunci": ["salat gerhana", "shalat gerhana", "tata cara salat gerhana", "hukum salat gerhana", "khutbah gerhana"],
        "ringkasan_singkat": "Salat gerhana hukumnya sunnah muakkadah. Dilaksanakan dua rakaat dengan tata cara khusus: setiap rakaat terdiri dari dua kali berdiri, dua kali membaca surat, dan dua kali ruku', diakhiri dengan dua khutbah nasihat.",
        "penjelasan_lengkap": "Nabi Muhammad SAW bersabda bahwa sesungguhnya matahari dan bulan adalah dua tanda di antara tanda-tanda kebesaran Allah; keduanya tidak mengalami gerhana karena mati atau hidupnya seseorang. Tata caranya: 1) Niat salat kusuf (matahari) atau khusuf (bulan), 2) Takbiratul ihram, membaca Al-Fatihah dan surat, 3) Ruku' pertama yang panjang, 4) Bangkit i'tidal lalu membaca Al-Fatihah dan surat kedua, 5) Ruku' kedua, 6) I'tidal lalu sujud dua kali, 7) Mengulangi rakaat kedua dengan pola serupa (dua ruku'), 8) Salam, dilanjutkan mendengarkan khutbah gerhana.",
        "sumber": "Hadits Shahih Bukhari & Muslim, Kitab Fathul Mu'in",
        "tingkat_keyakinan": "tinggi"
    }
]

# 6. FENOMENA ASTRONOMI
fenomena_astronomi = [
    {
        "id": "fenomena_01_fase_bulan",
        "topik": "Fase-Fase Bulan",
        "kata_kunci": ["fase bulan", "moon phases", "bulan sabit", "purnama", "kuartir", "cembung"],
        "ringkasan_singkat": "Fase bulan adalah penampakan bagian permukaan bulan yang diterangi matahari jika dilihat dari bumi. Terdiri dari 8 fase: bulan baru, sabit awal, kuartir awal, cembung awal, purnama, cembung akhir, kuartir akhir, dan sabit akhir.",
        "penjelasan_lengkap": "Siklus fase bulan berlangsung sekitar 29,53 hari (periode sinodis). 1) New Moon / Hilal Awal: bulan berada di antara matahari dan bumi. 2) Waxing Crescent: bulan sabit tipis di ufuk barat selepas sunset. 3) First Quarter: setengah piringan bulan tampak terang di barat saat senja. 4) Waxing Gibbous: lebih dari separuh piringan terang. 5) Full Moon (Purnama/Badr): bulan beroposisi 180 derajat terhadap matahari, bersinar semalaman. 6) Waning Gibbous: piringan mulai mengecil. 7) Third/Last Quarter: setengah piringan tampak di timur tengah malam. 8) Waning Crescent: sabit tua sebelum fajar.",
        "sumber": "Astronomy: A Beginner's Guide to the Universe & Ilmu Falak",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "fenomena_02_equation_of_time",
        "topik": "Equation of Time (Perata Waktu / Ta'dil al-Waqt)",
        "kata_kunci": ["equation of time", "perata waktu", "ta'dil waqt", "eot", "analemma", "matahari sejati"],
        "ringkasan_singkat": "Equation of Time adalah selisih antara waktu matahari sejati (solar time dari sundial) dan waktu matahari rata-rata (jam dinding/arloji). Selisih ini berkisar antara -14 hingga +16 menit sepanjang tahun.",
        "penjelasan_lengkap": "Karena orbit bumi mengelilingi matahari berbentuk elips (hukum Kepler kedua: kecepatan bumi bervariasi) dan sumbu rotasi bumi miring 23,44 derajat terhadap bidang orbit (oblikuitas ekliptika), maka gerak harian matahari di langit tidak konstan. Selisih inilah yang disebut Perata Waktu (Equation of Time / EoT). Dalam perhitungan jadwal salat, EoT sangat krusial untuk menentukan saat tepat matahari melintasi meridian (waktu zawal) dari waktu Greenwich rata-rata (GMT/UTC).",
        "sumber": "Jean Meeus Astronomical Algorithms & Hisab Kontemporer",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "fenomena_03_deklinasi_gerak_semu",
        "topik": "Deklinasi dan Gerak Semu Tahunan Matahari",
        "kata_kunci": ["deklinasi matahari", "gerak semu matahari", "solstis", "ekuinoks", "kemiringan bumi"],
        "ringkasan_singkat": "Deklinasi adalah sudut posisi benda langit di utara atau selatan ekuator langit. Akibat kemiringan sumbu bumi 23,5 derajat, deklinasi matahari berubah dari +23,5 derajat (Juni) hingga -23,5 derajat (Desember), menyebabkan perubahan musim dan panjang siang-malam.",
        "penjelasan_lengkap": "Bumi berotasi dengan sumbu miring 23° 26' terhadap bidang revolusinya. Hal ini memunculkan fenomena gerak semu tahunan matahari: pada 21 Maret matahari berada di ekuator (ekuinoks musim semi, deklinasi 0°), 21 Juni mencapai titik balik utara (solstis Juni, deklinasi +23,5°), 23 September kembali di ekuator (ekuinoks musim gugur, deklinasi 0°), dan 22 Desember mencapai titik balik selatan (solstis Desember, deklinasi -23,5°). Perubahan deklinasi ini adalah basis penentuan waktu salat dan fenomena Rashdul Kiblat.",
        "sumber": "Dasar-Dasar Astronomi Modern & Ephemeris Hisab Rukyat",
        "tingkat_keyakinan": "tinggi"
    }
]

# 7. LITERATUR DAN TOKOH FALAK NUSANTARA
literatur_tokoh = [
    {
        "id": "tokoh_01_kh_turaichan",
        "topik": "KH Turaichan Adjhuri dan Hisab Kudus",
        "kata_kunci": ["kh turaichan", "turaikhan", "turaichan adjhuri", "falak kudus", "menara kudus", "tokoh falak"],
        "ringkasan_singkat": "KH Turaichan Adjhuri (1915–1999) adalah salah satu ulama falak paling berpengaruh di Indonesia dari Kudus, Jawa Tengah. Beliau dikenal sangat teguh mempertahankan hisab hakiki tahqiqi dan menyusun penanggalan legendaris Menara Kudus.",
        "penjelasan_lengkap": "Mbah Turaichan Adjhuri Asy-Syarafi menguasai berbagai sistem hisab klasik dan kontemporer. Kitab-kitab karangannya banyak diajarkan di pesantren nusantara, di antaranya Irsyadul Murid, Sirajul Awam, dan Badi'atul Mitsal. Beliau memadukan hisab yang sangat teliti dengan keteguhan prinsip fikih, menjadi rujukan utama hisab para kiai di Jawa selama beberapa dekade.",
        "sumber": "Biografi Ulama Falak Nusantara & Sejarah Falak Menara Kudus",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "tokoh_02_kh_zubair_umar",
        "topik": "KH Zubair Umar Al-Jailani dan Kitab Al-Khulashah Al-Wafiyah",
        "kata_kunci": ["kh zubair umar", "al-khulashah al-wafiyah", "khulashah wafiyah", "zubair umar salatiga", "kitab falak"],
        "ringkasan_singkat": "KH Zubair Umar Al-Jailani dari Salatiga adalah pengarang kitab agung 'Al-Khulashah Al-Wafiyah fi Al-Falak bi Jadawil Al-Lugharitmiyyah', kitab hisab falak modern berbasis tabel logaritma yang menjadi kurikulum utama pesantren di Indonesia.",
        "penjelasan_lengkap": "Kitab Al-Khulashah Al-Wafiyah yang disusun KH Zubair Umar pada pertengahan abad ke-20 merupakan mahakarya hisab hakiki tahqiqi. Kitab ini mengintegrasikan kaidah hisab klasik dengan metode logaritma modern untuk menghitung posisi matahari, bulan, waktu salat, gerhana, dan arah kiblat dengan presisi tinggi tanpa memerlukan kalkulator elektronik pada masanya.",
        "sumber": "Kitab Al-Khulashah Al-Wafiyah & Khazanah Falak Pesantren",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "tokoh_03_kh_manshur_batawi",
        "topik": "KH Muhammad Manshur dan Kitab Sullamun Nayyirain",
        "kata_kunci": ["sullamun nayyirain", "kh manshur", "guru manshur", "manshur jembatan lima", "hisab taqribi", "kitab sullam"],
        "ringkasan_singkat": "KH Muhammad Manshur bin Abdul Hamid bin Damiri (Guru Manshur Jembatan Lima, Jakarta) menyusun kitab 'Sullamun Nayyirain' pada tahun 1925. Kitab ini merupakan kitab hisab taqribi paling populer dan legendaris di kalangan santri dan masyarakat Betawi.",
        "penjelasan_lengkap": "Kitab Sullamun Nayyirain menggunakan metode hisab taqribi (perhitungan pendekatan) yang diturunkan dari tabel Zaij Ulugh Beg dan Al-Battani. Keistimewaan kitab ini terletak pada penyajian tabel-tabel angka yang sederhana, sehingga santri dapat menghitung ijtimak dan posisi hilal hanya menggunakan penjumlahan dan pengurangan dasar. Meskipun bersifat taqribi (memiliki deviasi jika dibanding ephemeris modern), kitab ini memiliki jasa sejarah luar biasa dalam literasi falak rakyat nusantara.",
        "sumber": "Kitab Sullamun Nayyirain & Sejarah Falak Jakarta",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "tokoh_04_saadoeddin_djambek",
        "topik": "Saadoe'ddin Djambek (Pelopor Hisab Kontemporer)",
        "kata_kunci": ["saadoeddin djambek", "djambek", "hisab kontemporer", "spherical trigonometry", "tokoh hisab"],
        "ringkasan_singkat": "Saadoe'ddin Djambek (1911–1977) adalah ulama, pendidik, dan pakar falak asal Minangkabau yang mempelopori modernisasi ilmu falak di Indonesia dengan mengadopsi kalkulus dan trigonometri bola modern.",
        "penjelasan_lengkap": "Saadoe'ddin Djambek menulis banyak buku monumental seperti 'Waktu dan Jadwal', 'Arah Kiblat', dan 'Perbandingan Tarikh'. Beliau mentransformasi pengajaran hisab di universitas dan kementerian dari cara tradisional menjadi berbasis rumus matematika bola baku yang presisi, meletakkan fondasi hisab ephemeris modern yang digunakan Badan Hisab Rukyat Kemenag RI.",
        "sumber": "Buku-Buku Karya Saadoe'ddin Djambek & Ensiklopedi Islam",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "tokoh_05_kh_ahmad_dahlan",
        "topik": "KH Ahmad Dahlan dan Pelurusan Arah Kiblat",
        "kata_kunci": ["kh ahmad dahlan", "arah kiblat dahlan", "masjid gedhe kauman", "pelurusan kiblat", "muhammadiyah falak"],
        "ringkasan_singkat": "KH Ahmad Dahlan, pendiri Muhammadiyah, adalah tokoh pelopor pembaruan falak yang membetulkan arah kiblat Masjid Gedhe Kauman Yogyakarta dan masjid-masjid di Jawa pada akhir abad ke-19 menggunakan perhitungan matematis kompas dan istiwa.",
        "penjelasan_lengkap": "Sekembalinya dari belajar di Mekkah di bawah bimbingan Syaikh Ahmad Khatib Al-Minangkabawi, KH Ahmad Dahlan mendapati bahwa arah kiblat banyak masjid di tanah Jawa menghadap lurus ke barat (270 derajat), padahal posisi Mekkah dari Jawa adalah barat-laut (sekitar 295 derajat). Dengan ilmu ukur falak dan kompas, beliau melakukan koreksi saf salat. Peristiwa ini menjadi tonggak sejarah penting integrasi sains falak dalam amalan ibadah di Nusantara.",
        "sumber": "Sejarah Hidup KH Ahmad Dahlan & Perjalanan Arah Kiblat di Jawa",
        "tingkat_keyakinan": "tinggi"
    }
]

# 8. HARDWARE HILTRON TRACKER (ESP32 + BNO055 + GPS)
hardware_hiltron = [
    {
        "id": "hw_01_arsitektur_sistem",
        "topik": "Arsitektur HILTRON Dual-Axis Tracker ESP32",
        "kata_kunci": ["hiltron tracker", "esp32", "bno055", "neo-6m", "stepper", "spesifikasi tracker", "hardware hiltron"],
        "ringkasan_singkat": "HILTRON Tracker adalah sistem pelacak benda langit otomatis berbasis mikrokontroler ESP32, IMU 9-Axis Bosch BNO055 untuk orientasi ruang, GPS NEO-6M untuk waktu dan koordinat presisi, serta motor stepper ganda berdriver TMC2209.",
        "penjelasan_lengkap": "Perangkat keras HILTRON dirancang untuk observasi hilal dan benda langit otonom. Komponen utamanya: 1) ESP32 Dual-Core 240MHz dengan konektivitas WiFi/BLE dan WebSockets ke server FalakHub. 2) Bosch BNO055 Absolute Orientation IMU yang menggabungkan akselerometer, giroskop, dan magnetometer untuk mendeteksi heading (azimuth) dan pitch (altitude) real-time dengan sensor-fusion internal. 3) Modul GPS U-Blox NEO-6M untuk sinkronisasi sinyal waktu 1-PPS presisi microsecond dan penentuan lintang-bujur otomatis tanpa input manual. 4) Motor Stepper NEMA 17 dengan SilentStepStick TMC2209 untuk rotasi halus tanpa getaran getas.",
        "sumber": "Spesifikasi Teknis Hardware HILTRON IoT Telemetry Lab",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "hw_02_celestial_live_lock",
        "topik": "Mode Operasi: Celestial Live Lock (Tracking)",
        "kata_kunci": ["celestial live lock", "mode tracking", "kompensasi rotasi bumi", "14.5 derajat", "kecepatan tracking"],
        "ringkasan_singkat": "Celestial Live Lock adalah algoritma tracking aktif HILTRON yang menggerakkan sumbu polar teleskop sebesar 14,51 derajat per jam untuk mengompensasi rotasi bumi, menjaga objek hilal tetap berada di tengah bidang pandang kamera.",
        "penjelasan_lengkap": "Bumi berotasi pada porosnya satu putaran penuh (360 derajat) dalam waktu 23 jam 56 menit 4 detik (waktu sideris), yang berarti langit tampak bergerak dari timur ke barat dengan laju 15,041 derajat per jam untuk bintang, dan sekitar 14,51 derajat per jam untuk bulan (karena bulan juga memiliki gerak revolusi mengelilingi bumi ke arah timur sekitar 0,55 derajat per jam). HILTRON menghitung laju sudut relatif diferensial ephemeris DE421 dan mengumpankannya secara adaptif ke driver motor stepper.",
        "sumber": "Algoritma Tracking HILTRON Firmware ESP32 v1.2",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "hw_03_kalibrasi_troubleshooting",
        "topik": "Kalibrasi dan Troubleshooting Tracker HILTRON",
        "kata_kunci": ["kalibrasi bno055", "troubleshooting tracker", "kalibrasi tracker", "bno055 kalibrasi", "gangguan magnetik", "gps no fix"],
        "ringkasan_singkat": "Kalibrasi BNO055 dilakukan dengan memutar tracker perlahan membentuk pola angka 8 untuk magnetometer, dan mendatarkannya pada bidang level air (waterpass). Jika tracking melenceng, jauhkan dari benda logam feromagnetik dan pastikan antena GPS menghadap langit terbuka.",
        "penjelasan_lengkap": "Langkah kalibrasi optimal: 1) Leveling: letakkan tripod pada bidang datar menggunakan waterpass, pastikan pitch dan roll bernilai 0.0 derajat. 2) Kalibrasi Magnetometer: gerakkan perangkat membentuk lintasan angka 8 (figure-8 motion) di udara hingga status kalibrasi sistem mencapai tingkat 3 (penuh). 3) GPS Fix: letakkan antena GPS keramik menghadap langit terbuka tanpa halangan kanopi beton hingga LED 1PPS berkedip (3D Fix tercapai). 4) Troubleshooting umum: jika motor stepper skipping (kehilangan langkah), periksa tegangan VREF driver TMC2209 dan pastikan beban teleskop seimbang (counterweight terpasang baik).",
        "sumber": "Buku Panduan Teknis & Operasional HILTRON Observatory",
        "tingkat_keyakinan": "tinggi"
    }
]

# 9. FAQ PENGGUNA AWAM
faq_falak = [
    {
        "id": "faq_01_beda_awal_ramadhan",
        "topik": "Mengapa Awal Ramadhan atau Idul Fitri Bisa Berbeda di Indonesia?",
        "kata_kunci": ["kenapa beda ramadhan", "perbedaan idul fitri", "mengapa awal puasa beda", "muhammadiyah nu beda", "sidang isbat beda"],
        "ringkasan_singkat": "Perbedaan awal puasa atau lebaran terjadi karena perbedaan kriteria dan metode: Muhammadiyah menggunakan Wujudul Hilal (asalkan hilal sudah di atas ufuk), sedangkan Pemerintah (Kemenag) dan NU menggunakan Imkanur Rukyat MABIMS (tinggi minimal 3 derajat dan elongasi 6,4 derajat) serta verifikasi rukyat faktual.",
        "penjelasan_lengkap": "Ketika posisi hilal berada di antara 0 derajat sampai kurang dari 3 derajat, atau elongasinya belum mencapai 6,4 derajat, perbedaan penetapan hampir pasti terjadi. Menurut kriteria Wujudul Hilal, posisi tersebut sudah sah masuk bulan baru karena hilal sudah di atas ufuk (> 0°). Namun menurut kriteria Imkanur Rukyat MABIMS dan rukyatul hilal bil fi'li NU/Kemenag, hilal setinggi itu belum memenuhi batas minimal kemungkinan terlihat secara fisik, sehingga bulan berjalan digenapkan (istikmal) menjadi 30 hari. Perbedaan ini adalah ijtihad ilmiah yang sah dan harus disikapi dengan saling menghormati.",
        "sumber": "Panduan Harmonisasi Awal Bulan Kamariyah Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "faq_02_apa_itu_hilal",
        "topik": "Apa Itu Hilal Secara Astronomis dan Syar'i?",
        "kata_kunci": ["apa itu hilal", "pengertian hilal", "definisi hilal", "bentuk hilal", "hilal adalah"],
        "ringkasan_singkat": "Hilal adalah penampakan bulan sabit sangat tipis yang terlihat sesaat setelah matahari terbenam pada hari ke-29 bulan Hijriah di ufuk barat, menandai pergantian menuju bulan baru dalam kalender Islam.",
        "penjelasan_lengkap": "Secara bahasa, hilal berasal dari kata ahalla yang berarti tampak atau bersorak menyambutnya. Secara astronomis, hilal adalah bulan sabit muda pertama (crescent) yang memantulkan sinar matahari setelah terjadinya konjungsi (ijtimak). Hilal memiliki iluminasi yang sangat kecil (biasanya kurang dari 1-2 persen luas piringan bulan) dan hanya bertahan di atas ufuk selama beberapa menit hingga kurang dari satu jam sebelum tenggelam mengikuti matahari.",
        "sumber": "Leksikon Astronomi Islam & Fathul Wahhab",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "faq_03_kenapa_hilal_tidak_terlihat",
        "topik": "Mengapa Hilal Tidak Terlihat Meski Sudah Terjadi Ijtimak?",
        "kata_kunci": ["hilal tidak terlihat", "kenapa hilal tak nampak", "hilal gagal rukyat", "faktor kegagalan hilal", "sudah ijtimak hilal tidak ada"],
        "ringkasan_singkat": "Meskipun sudah ijtimak, hilal bisa tidak terlihat karena ketinggiannya masih terlalu rendah sehingga terkubur hamburan cahaya senja, kontras cahayanya terlalu redup, umur bulan masih terlalu muda, atau tertutup kabut dan awan tebal di ufuk barat.",
        "penjelasan_lengkap": "Ada dua faktor utama: 1) Faktor Astronomis (Limit Visibilitas): Setelah ijtimak, bulan butuh waktu berjam-jam untuk bergeser cukup jauh dari matahari agar ketebalan sabit dan kontras cahayanya melampaui kecerlangan langit senja (sky brightness). Jika elongasi kurang dari 6,4° atau tinggi kurang dari 3°, mata dan sensor kamera optik akan silau oleh hamburan cahaya senja (Danjon limit). 2) Faktor Atmosferis (Meteorologi): Ufuk barat Indonesia sering tertutup uap air laut, polusi debu, atau mendung awan cumulonimbus tebal saat senja.",
        "sumber": "Riset Visibilitas Hilal BMKG & BRIN",
        "tingkat_keyakinan": "tinggi"
    },
    {
        "id": "faq_04_beda_sabang_merauke",
        "topik": "Mengapa Ketinggian Hilal Berbeda Antara Sabang dan Merauke?",
        "kata_kunci": ["beda tinggi hilal", "sabang merauke hilal", "tinggi hilal indonesia barat timur", "perbedaan ufuk nusantara"],
        "ringkasan_singkat": "Wilayah Indonesia membentang sekitar 46 derajat bujur dengan selisih waktu terbenam matahari hampir 3 jam antara Merauke dan Sabang. Karena bulan terus bergerak menjauhi matahari dari timur ke barat, saat matahari terbenam di Sabang (Aceh), posisi hilal selalu lebih tinggi dan umurnya lebih tua daripada di Merauke.",
        "penjelasan_lengkap": "Matahari terbenam lebih awal di kawasan Indonesia Timur (Merauke/WIT) dan terbenam paling akhir di Indonesia Barat (Sabang/WIB). Dalam selang waktu hampir 3 jam tersebut, bulan terus bergerak dalam orbitnya mengelilingi bumi ke arah timur menjauhi matahari. Akibatnya, pada hari yang sama saat matahari terbenam di Sabang, sudut elongasi dan ketinggian hilal mar'i sudah bertambah lebih tinggi sekitar 1,5 hingga 2 derajat dibanding saat matahari terbenam di Merauke.",
        "sumber": "Peta Visibilitas Hilal Nasional Kemenag RI",
        "tingkat_keyakinan": "tinggi"
    }
]

# Write all files
all_kb = {
    "falak_dasar.json": falak_dasar,
    "waktu_salat.json": waktu_salat,
    "kiblat_rashdul.json": kiblat_rashdul,
    "kalender_hijriah.json": kalender_hijriah,
    "gerhana_astronomi.json": gerhana_astronomi,
    "fenomena_astronomi.json": fenomena_astronomi,
    "literatur_tokoh.json": literatur_tokoh,
    "hardware_hiltron.json": hardware_hiltron,
    "faq_falak.json": faq_falak
}

total_entries = 0
for filename, entries in all_kb.items():
    filepath = KNOWLEDGE_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    total_entries += len(entries)
    print(f"Saved {filename} with {len(entries)} entries.")

print(f"\nSuccessfully generated {len(all_kb)} knowledge files with {total_entries} total high-fidelity falak entries!")


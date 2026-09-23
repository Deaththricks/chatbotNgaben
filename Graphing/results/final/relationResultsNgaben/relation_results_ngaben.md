# Ngaben Relation Extraction

_981 relations across 465 sentences._


## S4

> sebagai ritual yang sangat rigid dan sarat makna, ngaben merepresentasikan siklus kehidupan dan kematian dalam kosmologi hindu bali.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `MELAMBANGKAN` | siklus kematian | dependency_rule |
| ngaben _(RITUAL_KEMATIAN)_ | `MELAMBANGKAN` | siklus kehidupan | dependency_rule |
| ngaben _(RITUAL_KEMATIAN)_ | `BERPERAN_SEBAGAI` | ritual yang sangat rigid dan sarat makna | dependency_rule |

## S6

> secara teologis, ngaben adalah ritual kremasi yang berakar pada filosofi pelepasan jiwa ( atma ) dari ikatan duniawi.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | ritual kremasi | manual_edit |
| ngaben _(RITUAL_KEMATIAN)_ | `BERAKAR_PADA` | filosofi pelepasan jiwa (atma) dari ikatan duniawi | manual_addition |

## S12

> secara etimologis, "ngaben" memiliki beberapa sudut pandang pemaknaan.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `MEMILIKI` | sudut pandang pemaknaan | dependency_rule |

## S16

> dalam sistem keagamaan hindu, ngaben diklasifikasikan sebagai bagian dari pitra yadnya , yaitu pengorbanan suci yang ditujukan kepada leluhur.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `BAGIAN_DARI` | pitra yadnya _(RITUAL)_ | dependency_rule |
| pitra yadnya _(RITUAL)_ | `ADALAH` | pengorbanan suci | object_decomposition |
| pengorbanan suci | `DITUJUKAN_UNTUK` | leluhur | object_decomposition |

## S26

> apah (air): mewakili unsur cair dalam tubuh.

| subject | relation | object | source |
|---|---|---|---|
| apah _(KONSEP_FILOSOFIS)_ | `MELAMBANGKAN` | unsur cair | dependency_rule |

## S27

> teja (panas/api): mewakili suhu dan energi.

| subject | relation | object | source |
|---|---|---|---|
| teja _(KONSEP_FILOSOFIS)_ | `MELAMBANGKAN` | suhu | dependency_rule |
| teja _(KONSEP_FILOSOFIS)_ | `MELAMBANGKAN` | energi | dependency_rule |

## S28

> bayu (angin): mewakili napas dan udara.

| subject | relation | object | source |
|---|---|---|---|
| bayu _(KONSEP_FILOSOFIS)_ | `MELAMBANGKAN` | napas | dependency_rule |
| bayu _(KONSEP_FILOSOFIS)_ | `MELAMBANGKAN` | udara | dependency_rule |

## S29

> akasa (eter/ruang): mewakili rongga dalam tubuh.

| subject | relation | object | source |
|---|---|---|---|
| akasa _(KONSEP_FILOSOFIS)_ | `MELAMBANGKAN` | rongga tubuh | dependency_rule |

## S32

> ngaben memiliki peran ganda yang saling menguatkan:

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `MEMILIKI` | peran ganda yang saling menguatkan | dependency_rule |

## S44

> sawa wedana adalah upacara untuk jenazah utuh (3-7 hari setelah meninggal); di era modern, penggunaan formalin umum dilakukan untuk memperlambat pembusukan selama masa persiapan.

| subject | relation | object | source |
|---|---|---|---|
| sawa wedana _(RITUAL_KEMATIAN)_ | `ADALAH` | upacara jenazah utuh ( 3-7 hari setelah meninggal ) | dependency_rule |
| formalin | `DIPAKAI_UNTUK` | memperlambat pembusukan (selama masa persiapan) | manual_addition |

## S45

> asti wedana adalah upacara pembakaran tulang belulang yang digali kembali dari kuburan sesuai aturan adat setempat.

| subject | relation | object | source |
|---|---|---|---|
| asti wedana _(RITUAL_KEMATIAN)_ | `ADALAH` | upacara pembakaran tulang belulang yang digali kembali dari kuburan sesuai aturan adat setempat | dependency_rule |

## S46

> swasta adalah upacara yang dilakukan jika jenazah tidak ditemukan atau meninggal di perantauan, menggunakan kayu cendana dan aksara sakral sebagai simbol pengganti jasad.

| subject | relation | object | source |
|---|---|---|---|
| swasta _(RITUAL_KEMATIAN)_ | `ADALAH` | upacara yang dilakukan jika jenazah tidak ditemukan atau meninggal di perantauan | manual_edit |
| swasta _(RITUAL_KEMATIAN)_ | `MENGGUNAKAN` | kayu cendana dan aksara sakral sebagai simbol pengganti jasad | manual_addition |

## S47

> ngelungah adalah ritual khusus untuk bayi yang belum tumbuh gigi (suci); jenazahnya segera dikubur dan upacaranya dilakukan minimal 12 hari kemudian.

| subject | relation | object | source |
|---|---|---|---|
| ngelungah _(RITUAL_KEMATIAN)_ | `ADALAH` | ritual khusus untuk bayi yang belum tumbuh gigi ( suci ) | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIKUBUR` | segera | manual_addition |
| upacara ngelungah _(RITUAL_KEMATIAN)_ | `DILAKUKAN` | minimal 12 hari kemudian | manual_addition |

## S48

> ngaben massal adalah pelaksanaan kolektif oleh warga desa untuk efisiensi biaya dan tenaga tanpa mengurangi nilai sakralitasnya.

| subject | relation | object | source |
|---|---|---|---|
| ngaben massal _(RITUAL_KEMATIAN)_ | `ADALAH` | pelaksanaan kolektif untuk efisiensi biaya dan tenaga tanpa mengurangi nilai sakralitas nya | dependency_rule |

## S58

> nganyut: melarung abu ke sungai atau laut sebagai simbol pelepasan terakhir menuju moksha .

| subject | relation | object | source |
|---|---|---|---|
| nganyut _(TAHAPAN_UPACARA)_ | `MELAMBANGKAN` | pelepasan terakhir menuju moksha _(KONSEP_FILOSOFIS)_ | manual_edit |
| abu _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | laut | manual_addition |
| abu _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | sungai | manual_addition |
| nganyut _(TAHAPAN_UPACARA)_ | `BERUPA` | pelarungan abu ke sungai atau laut | manual_addition |

## S61

> secara teologis, mapegat (berarti "memutuskan") memiliki makna krusial untuk memutus ikatan emosional dan duniawi antara mendiang ( niskala ) dengan keluarga ( skala ).

| subject | relation | object | source |
|---|---|---|---|
| mapegat _(TAHAPAN_UPACARA)_ | `MEMILIKI` | makna krusial untuk memutus ikatan emosional dan duniawi antara mendiang ( niskala ) dengan keluarga ( skala ) | dependency_rule |
| mapegat _(TAHAPAN_UPACARA)_ | `BERARTI` | memutuskan | dependency_rule |

## S69

> gedarba: berbentuk menyerupai beruang berwarna hitam, digunakan oleh wangsa sudra jadma (masyarakat umum).

| subject | relation | object | source |
|---|---|---|---|
| gedarba _(SARANA_RITUAL)_ | `BERBENTUK` | beruang berwarna hitam | manual_addition |

## S73

> naga banda adalah boneka naga raksasa yang melambangkan pengikat keinginan duniawi raja.

| subject | relation | object | source |
|---|---|---|---|
| naga banda _(SARANA_RITUAL)_ | `ADALAH` | boneka naga raksasa | dependency_rule |
| boneka naga raksasa | `MELAMBANGKAN` | pengikat keinginan duniawi raja | object_decomposition |

## S77

> secara teknis, naga banda seharusnya memiliki panjang 1.600 depa (sekitar 2,4 km) .

| subject | relation | object | source |
|---|---|---|---|
| naga banda _(SARANA_RITUAL)_ | `MEMILIKI` | panjang 1.600 depa | dependency_rule |

## S81

> misalnya, perbandingan kepala lembu adalah 2:1:1, sedangkan singa adalah 3:2:2.

| subject | relation | object | source |
|---|---|---|---|
| perbandingan kepala lembu | `ADALAH` | 2:1:1 | manual_addition |
| perbandingan kepala singa | `ADALAH` | 3:2:2 | manual_addition |

## S92

> kanoroyang: sanksi terberat berupa pemberhentian keanggotaan desa adat.

| subject | relation | object | source |
|---|---|---|---|
| kanoroyang _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | sanksi terberat berupa pemberhentian keanggotaan desa adat | manual_addition |

## S104

> bali aga vs bali dataran: terdapat perbedaan mendasar antara masyarakat pegunungan ( bali aga ) yang mempertahankan tradisi asli kuno (seperti di trunyan) dengan masyarakat bali dataran yang mendapat pengaruh kuat dari tradisi hindu-majapahit pasca jatuhnya kerajaan di jawa.

| subject | relation | object | source |
|---|---|---|---|
| bali aga _(Place)_ | `MEMPERTAHANKAN` | tradisi asli kuno | manual_addition |
| bali dataran _(Place)_ | `MENDAPAT_PENGARUH_DARI` | tradisi hindu-majapahit _(AGAMA)_ | manual_addition |

## S124

> bali dataran menggunakan sarana mewah (bade/petulangan) pengaruh majapahit, sedangkan bali aga lebih menonjolkan tradisi asli yang terkadang tidak menggunakan pembakaran fisik secara masif.

| subject | relation | object | source |
|---|---|---|---|
| bali dataran _(Place)_ | `MENGGUNAKAN` | sarana mewah | dependency_rule |
| sarana mewah | `ADALAH` | bade/petulangan | object_decomposition |
| bali aga _(Place)_ | `TIDAK_MENGGUNAKAN` | pembakaran fisik secara masif | manual_addition |
| bali aga _(Place)_ | `MENONJOLKAN` | tradisi asli | manual_addition |

## S126

> ngaben adalah institusi sosial-religius yang kompleks, berfungsi sebagai mekanisme spiritual pemurnian jiwa sekaligus perekat kohesi sosial.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | institusi sosial-religius | dependency_rule |
| ngaben _(RITUAL_KEMATIAN)_ | `BERFUNGSI_SEBAGAI` | mekanisme spiritual pemurnian jiwa | manual_addition |
| ngaben _(RITUAL_KEMATIAN)_ | `BERFUNGSI_SEBAGAI` | perekat kohesi sosial | manual_addition |

## S128

> kemampuan tradisi ini untuk beradaptasi—baik melalui efisiensi biaya maupun penggunaan teknologi—membuktikan bahwa ngaben adalah identitas budaya dinamis yang terus menjaga harmoni antara manusia, alam, dan sang pencipta.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | identitas budaya dinamis | dependency_rule |
| ngaben _(RITUAL_KEMATIAN)_ | `MENJAGA` | harmoni antara manusia, alam, dan sang pencipta | manual_addition |

## S133

> sebab bukan upakara yang besar dan megah yang menjamin manusia saat meninggalnya kelak akan secara otomatis mendapatkan sorga (amoring acintya), akan tetapi karma wasananyalah yang akan menuntun dan menentukan kelak di kemudian hari saat meninggalnya.

| subject | relation | object | source |
|---|---|---|---|
| karma wasana _(KONSEP_FILOSOFIS)_ | `MENENTUKAN` | nasib setelah meninggal | manual_addition |
| upakara _(SARANA_RITUAL)_ | `TIDAK_MENJAMIN` | sorga _(KONSEP_FILOSOFIS)_ | manual_addition |

## S197

> ngaben berdasarkan tingkatan upacara

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `BERDASARKAN` | tingkatan upacara _(KONSEP_HUKUM_ADAT)_ | dependency_rule |

## S215

> setelah upacara nyiraman, layon digulung dengan kain putih selanjutnya diletakkan di bale gede / saka roras atau tempat yang diperuntukkan untuk itu.

| subject | relation | object | source |
|---|---|---|---|
| layon _(SARANA_RITUAL)_ | `DIGULUNG_DENGAN` | kain putih _(SARANA_RITUAL)_ | dependency_rule |
| layon _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | bale gede _(BANGUNAN_RITUAL)_ | manual_addition |
| layon _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | saka roras _(BANGUNAN_RITUAL)_ | manual_addition |

## S217

> sampai pada hari yang telah ditentukan atau hari pengutangan, dilaksanakan pelebon, diawali dengan upacara ngaskara dan caru pengelambuk, selanjutnya jenazah dinaikkan ke usungan lalu berangkat ke setra.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DINAIKKAN_KE` | usungan _(SARANA_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `BERANGKAT_KE` | setra _(BANGUNAN_RITUAL)_ | manual_addition |
| pelebon _(RITUAL_KEMATIAN)_ | `DIAWALI_DENGAN` | caru pengelambuk _(TAHAPAN_UPACARA)_ | manual_addition |
| pelebon _(RITUAL_KEMATIAN)_ | `DIAWALI_DENGAN` | upacara ngaskara _(TAHAPAN_UPACARA)_ | manual_addition |

## S219

> dalam perjalanan ke setra ditaburkan sekar ura yang terdiri dari beras kuning, wang kepeng/bolong, dan daun temen serta kembang rampai, sebagai simbol perpisahan antara yang meninggal dengan keluarga yang ditinggal dengan harapan selalu diberikan kesejahteraan dan kemakmuran.

| subject | relation | object | source |
|---|---|---|---|
| sekar ura _(SARANA_RITUAL)_ | `TERDIRI_DARI` | beras kuning | dependency_rule |
| sekar ura _(SARANA_RITUAL)_ | `TERDIRI_DARI` | wang kepeng/bolong _(SARANA_RITUAL)_ | dependency_rule |
| sekar ura _(SARANA_RITUAL)_ | `TERDIRI_DARI` | daun temen | dependency_rule |
| sekar ura _(SARANA_RITUAL)_ | `TERDIRI_DARI` | kembang rampai _(SARANA_RITUAL)_ | dependency_rule |
| sekar ura _(SARANA_RITUAL)_ | `MELAMBANGKAN` | harapan selalu diberikan kesejahteraan dan kemakmuran | manual_addition |
| sekar ura _(SARANA_RITUAL)_ | `MELAMBANGKAN` | perpisahan antara yang meninggal dengan keluarga yang ditinggal | manual_addition |

## S246

> dilanjutkan dengan ngerorasin di pura dalem; puspa lingga tersebut dibuka keampigan bila upacara ini cukup sampai di sini saja.

| subject | relation | object | source |
|---|---|---|---|
| ngerorasin _(TAHAPAN_UPACARA)_ | `DIADAKAN_DI` | pura dalem _(BANGUNAN_RITUAL)_ | manual_addition |
| puspa lingga _(SARANA_RITUAL)_ | `DIBUKA` | keampigan | manual_addition |

## S253

> upacara ini dilakukan bila sawa telah terlebih dahulu dikubur dengan tata cara penguburan biasa.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIKUBUR_DENGAN` | tata cara penguburan biasa _(TAHAPAN_UPACARA)_ | dependency_rule |

## S254

> bila telah siap dilakukan upacara, maka kuburan dibongkar dan diambil tulang belulangnya.

| subject | relation | object | source |
|---|---|---|---|
| kuburan _(BANGUNAN_RITUAL)_ | `DIBONGKAR` | untuk mengambil tulang belulang | manual_addition |
| tulang belulang | `DIAMBIL_DARI` | kuburan _(BANGUNAN_RITUAL)_ | manual_addition |

## S258

> tegteg lalu diiring ke pura dalem, dengan tujuan matur piuning serta memohon atma yang akan diaben.

| subject | relation | object | source |
|---|---|---|---|
| tegteg _(SARANA_RITUAL)_ | `DIBAWA_KE` | pura dalem _(BANGUNAN_RITUAL)_ | dependency_rule |
| tegteg _(SARANA_RITUAL)_ | `DIPAKAI_UNTUK` | matur piuning serta memohon atma yang akan diaben | manual_addition |

## S265

> tegteg diletakkan di atas bungkusan tulang belulang tersebut, lalu diupacarai sebagaimana layaknya sawa utuh, selanjutnya tegteg ditempatkan di tumpang salu.

| subject | relation | object | source |
|---|---|---|---|
| tegteg _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | bungkusan tulang belulang | dependency_rule |
| tegteg _(SARANA_RITUAL)_ | `DIPERLAKUKAN_SEPERTI` | sawa utuh _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| tegteg _(SARANA_RITUAL)_ | `DITEMPATKAN_DI` | tumpang salu _(SARANA_RITUAL)_ | manual_addition |

## S270

> secara khusus, ngaben svasta dimaksudkan untuk pelaksanaan atiwa-tiwa terhadap orang yang telah meninggal yang jenazahnya tidak mungkin ditemukan kembali, telah lama terkubur/terpendam, atau karena letaknya terlalu jauh dari jangkauan kita.

| subject | relation | object | source |
|---|---|---|---|
| ngaben svasta _(RITUAL_KEMATIAN)_ | `DITUJUKAN_UNTUK` | jenazah yang telah lama terkubur/terpendam | manual_addition |
| ngaben svasta _(RITUAL_KEMATIAN)_ | `DITUJUKAN_UNTUK` | jenazah yang terlalu jauh dari jangkauan kita | manual_addition |
| ngaben svasta _(RITUAL_KEMATIAN)_ | `ADALAH` | pelaksanaan atiwa-tiwa terhadap orang yang telah meninggal yang jenazahnya tidak mungkin ditemukan kembali | manual_addition |

## S271

> adapun atiwa-tiwa yang tergolong dalam ngaben svasta adalah raçadana atau tirta yadnya pranawa, yakni sawa diganti dengan simbol tirtha (toyo çarira), sedangkan tata pelaksanaannya sama dengan atiwa-tiwa asti vedana — mulai dari matur piuning ke pura dalem, pembakaran, hingga nganyut, dan dilanjutkan dengan upacara sebagaimana mestinya hingga upacara ngelinggihang dewa hyang.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIGANTI_DENGAN` | simbol tirtha _(TIRTHA_SUCI)_ | dependency_rule |
| simbol tirtha | `ADALAH` | toyo çarira | object_decomposition |
| atiwa-tiwa _(RITUAL_KEMATIAN)_ | `ADALAH` | raçadana | dependency_rule |
| atiwa-tiwa _(RITUAL_KEMATIAN)_ | `ADALAH` | tirta yadnya pranawa _(RITUAL_KEMATIAN)_ | dependency_rule |
| atiwa-tiwa _(RITUAL_KEMATIAN)_ | `BAGIAN_DARI` | ngaben svasta _(RITUAL_KEMATIAN)_ | dependency_rule |
| raçadana | `SAMA_DENGAN` | atiwa-tiwa asti vedana _(RITUAL_KEMATIAN)_ | manual_addition |
| tirta yadnya pranawa | `SAMA_DENGAN` | atiwa-tiwa asti vedana _(RITUAL_KEMATIAN)_ | manual_addition |

## S283

> dalam lontar tersebut, banten yang menjadi simbol orang yang meninggal disebut kala puspa, sebagaimana juga disebutkan dalam lontar yama purva tattwa.

| subject | relation | object | source |
|---|---|---|---|
| banten yang menjadi simbol orang yang meninggal _(SARANA_RITUAL)_ | `DIKENAL_SEBAGAI` | kala puspa _(SARANA_RITUAL)_ | manual_addition |

## S332

> jenazah diletakkan pada balai dengan posisi kepala berhulu utara atau timur.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | balai | manual_edit |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `MEMBUJUR_KE` | kepala di utara atau timur | manual_addition |

## S338

> lalu disuguhi soda berupa nasi, minum, buah-buahan, jajan, dan lainnya, dilengkapi canang sari beserta kelengkapannya.

| subject | relation | object | source |
|---|---|---|---|
| soda _(SARANA_RITUAL)_ | `DILENGKAPI` | canang sari _(SARANA_RITUAL)_ | dependency_rule |
| soda _(SARANA_RITUAL)_ | `BERUPA` | buah-buahan | manual_addition |
| soda _(SARANA_RITUAL)_ | `BERUPA` | jajan | manual_addition |
| soda _(SARANA_RITUAL)_ | `BERUPA` | minum | manual_addition |
| soda _(SARANA_RITUAL)_ | `BERUPA` | nasi | manual_addition |

## S344

> eteh-eteh sawa, berupa kain putih untuk saput, kamben, tapih, sabuk, udeng, pangulungan, angkeb rai, angkeb baga/purus, leluwur, dan tatindih (biasanya dimohonkan dari sulinggih/griya); kain putih untuk bantal berisi pis bolong 11 kepeng; kain kuning untuk saput atau selendang; rantasan kain putih kuning dan kain anyar; serta samsam, bunga, dan kwangen.

| subject | relation | object | source |
|---|---|---|---|
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | kain putih untuk bantal berisi pis bolong 11 kepeng | dependency_rule |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | angkeb baga/purus _(SARANA_RITUAL)_ | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | angkeb rai _(SARANA_RITUAL)_ | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | bunga | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | kain kuning untuk saput atau selendang | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | kain putih untuk saput _(SARANA_RITUAL)_ | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | kamben | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | kwangen _(SARANA_RITUAL)_ | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | leluwur _(SARANA_RITUAL)_ | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | pangulungan | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | rantasan kain putih kuning dan kain anyar | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | sabuk | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | samsam _(SARANA_RITUAL)_ | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `DIMOHONKAN_DARI` | sulinggih/griya _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | tapih | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | tatindih | manual_addition |
| eteh-eteh sawa _(SARANA_RITUAL)_ | `BERUPA` | udeng _(SARANA_RITUAL)_ | manual_addition |

## S354

> pepaga terbuat dari bambu dengan hitungan: likah, wangke, wangkong, dan galar, galir, galur.

| subject | relation | object | source |
|---|---|---|---|
| pepaga _(SARANA_RITUAL)_ | `TERBUAT_DARI` | bambu | dependency_rule |
| pepaga _(SARANA_RITUAL)_ | `TERBUAT_DARI` | hitungan wangke | dependency_rule |
| pepaga _(SARANA_RITUAL)_ | `TERBUAT_DARI` | hitungan wangkong | dependency_rule |
| pepaga _(SARANA_RITUAL)_ | `TERBUAT_DARI` | hitungan galar _(SARANA_RITUAL)_ | dependency_rule |
| pepaga _(SARANA_RITUAL)_ | `TERBUAT_DARI` | hitungan galir | dependency_rule |
| pepaga _(SARANA_RITUAL)_ | `TERBUAT_DARI` | hitungan galur | dependency_rule |
| pepaga _(SARANA_RITUAL)_ | `TERBUAT_DARI` | hitungan likah | dependency_rule |

## S358

> pepaga ditempatkan di halaman rumah, di atasnya dipasang/direntangkan leluwur berupa kain putih.

| subject | relation | object | source |
|---|---|---|---|
| pepaga _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | halaman rumah | dependency_rule |
| pepaga _(SARANA_RITUAL)_ | `DIPASANG` | leluwur _(SARANA_RITUAL)_ | dependency_rule |
| leluwur _(SARANA_RITUAL)_ | `BERUPA` | kain putih _(SARANA_RITUAL)_ | manual_addition |

## S364

> sebelum jenazah diusung ke tempat pemandian, terlebih dahulu diadakan upacara nanginin, yaitu membangunkan almarhum seperti halnya membangunkan orang yang sedang tidur, dengan memanggil namanya dan mengucapkan kata-kata dengan lemah lembut serta memberitahukan untuk segera dimandikan — lebih baik lagi disertai kekidungan yang berhubungan dengan kidung pitra yadnya.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | tempat pemandian | dependency_rule |
| nanginin _(TAHAPAN_UPACARA)_ | `DILAKUKAN_SEBELUM` | jenazah diusung ke tempat pemandian _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| nanginin _(TAHAPAN_UPACARA)_ | `DILAKUKAN_DENGAN` | memanggil nama almarhum dan mengucapkan kata-kata lemah lembut | manual_addition |

## S365

> selanjutnya jenazah diangkat dan diletakkan pada pepaga yang telah disediakan, masih dibarengi kekidungan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | pepaga _(SARANA_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBARENGI` | kekidungan | dependency_rule |

## S366

> jenazah membujur ke utara atau ke timur.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `MEMBUJUR_KE` | timur | manual_addition |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `MEMBUJUR_KE` | utara | manual_addition |

## S370

> selanjutnya dipasang itik-itik pada ibu jari tangan dan kaki, jenazah digulung dengan tikar dan kain yang telah dirajah, diakhiri dengan lante dari bambu, lalu dimasukkan ke dalam slepa/peti dan ditempatkan pada bale gede/sakaroras atau tempat yang disiapkan, dengan posisi kepala ke utara atau ke timur.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIGULUNG_DENGAN` | tikar | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIGULUNG_DENGAN` | kain yang telah dirajah | manual_edit |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPASANG` | itik-itik _(SARANA_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIAKHIRI_DENGAN` | lante bambu _(SARANA_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | slepa/peti _(SARANA_RITUAL)_ | dependency_rule |
| itik-itik _(SARANA_RITUAL)_ | `DIPASANG_PADA` | ibu jari tangan dan kaki | manual_addition |

## S376

> bila telah datang hari baik, minimal/maksimal selama 7 hari sejak meninggal, jenazah diusung ke setra untuk dibasmi oleh sang hyang birawi.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | setra _(BANGUNAN_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBASMI_OLEH` | sang hyang birawi _(ENTITAS_KEAGAMAAN)_ | manual_addition |

## S399

> dengan demikian, dapat disimpulkan bahwa sasih yang baik untuk melaksanakan pitra yadnya, khususnya ngaben, adalah kasa, karo, dan katiga, dengan yang utama pada sasih karo.

| subject | relation | object | source |
|---|---|---|---|
| sasih karo _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | sasih utama untuk pitra yadnya _(RITUAL)_ | manual_addition |
| sasih yang baik untuk pitra yadnya (khususnya ngaben) _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | karo _(KONSEP_HUKUM_ADAT)_ | manual_addition |
| sasih yang baik untuk pitra yadnya (khususnya ngaben) _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | kasa _(KONSEP_HUKUM_ADAT)_ | manual_addition |
| sasih yang baik untuk pitra yadnya (khususnya ngaben) _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | katiga _(KONSEP_HUKUM_ADAT)_ | manual_addition |

## S400

> sasih kaenem dan kapitu disebut dewasa madya.

| subject | relation | object | source |
|---|---|---|---|
| sasih kaenem _(KONSEP_HUKUM_ADAT)_ | `DIKENAL_SEBAGAI` | dewasa madya _(KONSEP_HUKUM_ADAT)_ | manual_addition |
| sasih kapitu _(KONSEP_HUKUM_ADAT)_ | `DIKENAL_SEBAGAI` | dewasa madya _(KONSEP_HUKUM_ADAT)_ | manual_addition |

## S408

> sasih paruwak tahuk adalah sasih berbadankan kosong, terdiri dari:

| subject | relation | object | source |
|---|---|---|---|
| sasih paruwak tahuk _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | sasih berbadankan kosong _(KONSEP_HUKUM_ADAT)_ | dependency_rule |

## S411

> ● wuku kuningan ada pada sasih kasa dan kapitu.

| subject | relation | object | source |
|---|---|---|---|
| wuku kuningan _(KONSEP_HUKUM_ADAT)_ | `BERADA_DI` | sasih kapitu _(KONSEP_HUKUM_ADAT)_ | dependency_rule |
| wuku kuningan _(KONSEP_HUKUM_ADAT)_ | `BERADA_DI` | sasih kasa _(KONSEP_HUKUM_ADAT)_ | dependency_rule |

## S413

> ● uye ada pada sasih katiga dan kasanga.

| subject | relation | object | source |
|---|---|---|---|
| uye _(KONSEP_HUKUM_ADAT)_ | `BERADA_DI` | sasih kasanga _(KONSEP_HUKUM_ADAT)_ | dependency_rule |
| uye _(KONSEP_HUKUM_ADAT)_ | `BERADA_DI` | sasih katiga _(KONSEP_HUKUM_ADAT)_ | dependency_rule |

## S414

> ● wayang ada pada sasih kapat dan kadasa.

| subject | relation | object | source |
|---|---|---|---|
| wayang _(KONSEP_HUKUM_ADAT)_ | `BERADA_DI` | sasih kadasa _(KONSEP_HUKUM_ADAT)_ | dependency_rule |
| wayang _(KONSEP_HUKUM_ADAT)_ | `BERADA_DI` | sasih kapat _(KONSEP_HUKUM_ADAT)_ | dependency_rule |

## S415

> malamasa adalah sasih yang ditampih atau diduakalikan, disebut juga malamasa.

| subject | relation | object | source |
|---|---|---|---|
| malamasa _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | sasih yang ditampih atau diduakalikan | manual_edit |

## S633

> banten pengajeng sulinggih utawi pinandita.

| subject | relation | object | source |
|---|---|---|---|
| banten _(SARANA_RITUAL)_ | `DIPERSEMBAHKAN_KEPADA` | sulinggih utawi pinandita _(ENTITAS_KEAGAMAAN)_ | dependency_rule |

## S738

> puspa asti adalah abu yang diambil dengan mempergunakan sumpit/sepit, lalu dihancurkan/ditumbuk pada sebuah sesenden.

| subject | relation | object | source |
|---|---|---|---|
| puspa asti _(SARANA_RITUAL)_ | `ADALAH` | abu yang diambil dengan mempergunakan sumpit/sepit | manual_edit |
| puspa asti _(SARANA_RITUAL)_ | `DIHANCURKAN_DI` | sesenden _(SARANA_RITUAL)_ | manual_addition |

## S780

> dalam hal ini, puspa asti ditaruh pada balai selunglung atau dipangku oleh salah seorang keluarga; persembahyangan ini dipimpin oleh sulinggih.

| subject | relation | object | source |
|---|---|---|---|
| puspa asti _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | balai selunglung _(SARANA_RITUAL)_ | dependency_rule |
| persembahyangan _(TAHAPAN_UPACARA)_ | `DIPIMPIN_OLEH` | sulinggih _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| puspa asti _(SARANA_RITUAL)_ | `DIPANGKU_OLEH` | salah seorang keluarga | manual_addition |

## S785

> sebagaimana diketahui, pitra yadnya telah menjadi sebuah istilah bagi umat hindu di sini.

| subject | relation | object | source |
|---|---|---|---|
| pitra yadnya _(RITUAL)_ | `ADALAH` | istilah umat hindu _(AGAMA)_ | dependency_rule |

## S788

> pitra yadnya terdiri dari dua kata, yakni "pitra" dan "yadnya".

| subject | relation | object | source |
|---|---|---|---|
| pitra yadnya _(RITUAL)_ | `TERDIRI_DARI` | dua kata | dependency_rule |
| dua kata | `ADALAH` | pitra _(KONSEP_FILOSOFIS)_ | object_decomposition |
| dua kata | `ADALAH` | yadnya _(KONSEP_FILOSOFIS)_ | manual_addition |

## S789

> secara harfiah, "pitra" berarti orangtua (ayah dan ibu).

| subject | relation | object | source |
|---|---|---|---|
| pitra _(KONSEP_FILOSOFIS)_ | `BERARTI` | orangtua | dependency_rule |
| orangtua | `ADALAH` | ayah | object_decomposition |
| orangtua | `ADALAH` | ibu | manual_addition |

## S792

> jadi, "pitra yadnya" berarti pengorbanan yang dilandasi hati yang tulus suci kepada leluhur, terutama kepada orangtua.

| subject | relation | object | source |
|---|---|---|---|
| pitra yadnya _(RITUAL)_ | `BERARTI` | pengorbanan yang dilandasi hati yang tulus suci kepada leluhur , terutama kepada orangtua | dependency_rule |
| pitra yadnya _(RITUAL)_ | `DITUJUKAN_UNTUK` | orangtua | dependency_rule |
| pitra yadnya _(RITUAL)_ | `DITUJUKAN_UNTUK` | leluhur | manual_addition |

## S797

> sebagai istilah, pitra yadnya memiliki arti tersendiri, yakni upacara keagamaan yang diadakan untuk menyelenggarakan atau nyangaskara jenazah atau roh keluarga yang meninggal dengan pelbagai sajen dan alat-alat upakara sebagai sarananya.

| subject | relation | object | source |
|---|---|---|---|
| pitra yadnya _(RITUAL)_ | `ADALAH` | upacara keagamaan yang diadakan untuk menyelenggarakan atau nyangaskara jenazah atau roh keluarga yang meninggal | manual_edit |
| pitra yadnya _(RITUAL)_ | `MENGGUNAKAN` | pelbagai sajen dan alat-alat upakara _(SARANA_RITUAL)_ | manual_addition |

## S801

> pitra yadnya terdiri dari beberapa jenis yang pelaksanaannya ber-bhinneka.

| subject | relation | object | source |
|---|---|---|---|
| pitra yadnya _(RITUAL)_ | `TERDIRI_DARI` | beberapa jenis yang pelaksanaannya ber-bhinneka | manual_edit |

## S809

> antara lain karena pitra yadnya yang dilakukan di dataran rendah inilah yang rupanya merupakan hasil penyempurnaan terakhir dari yang ening sira empu kuturan, dang hyang dwijendra, empu lutuk dan lain-lain.

| subject | relation | object | source |
|---|---|---|---|
| pitra yadnya dataran rendah _(RITUAL)_ | `ADALAH` | hasil penyempurnaan terakhir dan lain-lain | manual_addition |
| pitra yadnya dataran rendah _(RITUAL)_ | `ADALAH` | hasil penyempurnaan terakhir dang hyang dwijendra | manual_addition |
| pitra yadnya dataran rendah _(RITUAL)_ | `ADALAH` | hasil penyempurnaan terakhir empu lutuk | manual_addition |
| pitra yadnya dataran rendah _(RITUAL)_ | `ADALAH` | hasil penyempurnaan terakhir yang ening sira empu kuturan | manual_addition |

## S822

> tidak lain lantaran pitra yadnya itu sendiri merupakan suatu upacara keagamaan.

| subject | relation | object | source |
|---|---|---|---|
| pitra yadnya _(RITUAL)_ | `ADALAH` | upacara keagamaan | dependency_rule |

## S851

> jelasnya, semasih pancamahabutha berwujud tubuh manusia termasuk setelah meninggal selaku sawa (jenazah), manusia "pemakai" lima unsur zat itu dinilai selaku pihak berhutang.

| subject | relation | object | source |
|---|---|---|---|
| pancamahabutha _(KONSEP_FILOSOFIS)_ | `BERWUJUD` | tubuh manusia | dependency_rule |
| manusia | `DINILAI_SEBAGAI` | pihak berhutang _(KONSEP_FILOSOFIS)_ | manual_addition |

## S898

> selain itu, sesajen yang dihaturkan itu tertuju kepada ida bhatara kumara yang diyakini sebagai "mengasuh" bayi tersebut.

| subject | relation | object | source |
|---|---|---|---|
| sesajen _(SARANA_RITUAL)_ | `DITUJUKAN_UNTUK` | ida bhatara kumara _(ENTITAS_KEAGAMAAN)_ | dependency_rule |

## S917

> namun lantaran telah pernah ada upacara bertalian dengan kelahirannya, maka perlu dibuatkan acara ala kadarnya antara lain, jenazah dibungkus kain putih setelah dimandikan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah bayi _(ISTILAH_UMUM_RITUAL)_ | `DIBUNGKUS_SETELAH` | dimandikan | manual_addition |
| jenazah bayi _(ISTILAH_UMUM_RITUAL)_ | `DIBUNGKUS_DENGAN` | kain putih _(SARANA_RITUAL)_ | manual_addition |

## S923

> saat berangkat ke kuburan, jenazah di momong, diiringi peti di sampingnya.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DISERTAI` | peti (di sampingnya) | manual_addition |

## S925

> setelah itu, jenazah dimasukkan ke dalam peti kayu, kemudian di kuburan tanpa upakara apapun yang tertuju langsung kepadanya.

| subject | relation | object | source |
|---|---|---|---|
| jenazah bayi _(ISTILAH_UMUM_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | peti kayu | manual_addition |

## S957

> pertama-tama jenazah bayi tersebut dimandikan dengan air biasa di atas dusa (balai-balai khusus pemandian jenazah) di natar rumah.

| subject | relation | object | source |
|---|---|---|---|
| jenazah bayi _(ISTILAH_UMUM_RITUAL)_ | `DISIRAM_DENGAN` | air biasa | dependency_rule |
| dusa _(SARANA_RITUAL)_ | `ADALAH` | balai-balai khusus pemandian jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| jenazah bayi _(ISTILAH_UMUM_RITUAL)_ | `DIMANDIKAN_DI_ATAS` | dusa _(SARANA_RITUAL)_ | manual_addition |
| jenazah bayi _(ISTILAH_UMUM_RITUAL)_ | `DIMANDIKAN_DI` | natar rumah | manual_addition |

## S958

> setelah bersih, jenazah bayi tersebut dimandikan dengan air kumkuman (air yang diberi serbuk cendana dan kembang serba harum).

| subject | relation | object | source |
|---|---|---|---|
| jenazah bayi _(ISTILAH_UMUM_RITUAL)_ | `DISIRAM_DENGAN` | air kumkuman _(TIRTHA_SUCI)_ | dependency_rule |
| air kumkuman | `ADALAH` | air yang diberi serbuk cendana dan kembang serba harum | object_decomposition |

## S961

> sawa itu kemudian dibungkus dengan kain putih dan diikat dengan benang leleson, dibelit sebelas kali dari hulu ke kaki.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIBUNGKUS_DENGAN` | kain putih _(SARANA_RITUAL)_ | dependency_rule |
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIIKAT_DENGAN` | benang leleson | dependency_rule |
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIIKAT` | sebelas kali | dependency_rule |

## S964

> setelah terbungkus, sawa tersebut digotong ke balai-balai rumah adat.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | balai-balai rumah adat | dependency_rule |

## S970

> tentu saja tirtha tersebut dimohon dari seorang sulinggih menurut tata cara betapa mestinya.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `DIMOHON_DARI` | sulinggih _(ENTITAS_KEAGAMAAN)_ | dependency_rule |

## S971

> karena tirtha tersebut dibuat dari klungah, maka pitra yadnya jenis ini dinamakan pula nglungah.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `TERBUAT_DARI` | klungah _(SARANA_RITUAL)_ | dependency_rule |
| pitra yadnya _(RITUAL)_ | `ADALAH` | nglungah _(RITUAL_KEMATIAN)_ | manual_addition |

## S972

> menurut ketentuan, sebagaimana tertulis dalam beberapa lontar, hanya sawa anak yang telah berusia lima bulan ke atas boleh atau sebaiknya dibakar dalam pitra yadnya nglungah ini.

| subject | relation | object | source |
|---|---|---|---|
| sawa anak yang telah berusia lima bulan ke atas _(ISTILAH_UMUM_RITUAL)_ | `DIBAKAR_DALAM` | pitra yadnya nglungah _(RITUAL)_ | manual_addition |

## S974

> setelah disuguhkan sesaji sederhana, abu itu dihanyutkan ke laut atau ke sungai.

| subject | relation | object | source |
|---|---|---|---|
| abu _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | laut | dependency_rule |
| abu _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | sungai | dependency_rule |
| abu _(SARANA_RITUAL)_ | `DISUGUHKAN` | sesaji sederhana _(SARANA_RITUAL)_ | manual_addition |

## S978

> tirtha ini dipercikkan sebelum tirtha pangentas pada saat menjelang penguburan atau pembakaran sawa.

| subject | relation | object | source |
|---|---|---|---|
| tirtha (dari pamrajan/kahyangan tiga/prajapati) _(TIRTHA_SUCI)_ | `DIPERCIKKAN_PADA` | saat menjelang penguburan atau pembakaran sawa | manual_addition |
| tirtha (dari pamrajan/kahyangan tiga/prajapati) _(TIRTHA_SUCI)_ | `DIPERCIKKAN_SEBELUM` | tirtha pangentas _(TIRTHA_SUCI)_ | manual_addition |

## S1016

> secara niskala (batiniah) ngaben bertujuan untuk memusnahkan segenap jasad sawa sehalus-halusnya, sehingga wujud sawa dari benda yang wungkul menjadi unsur, elemen atau mahabutha, yakni asal materi yang jauh lebih halus dari pada benda, lebih halus dari abu.

| subject | relation | object | source |
|---|---|---|---|
| niskala _(KONSEP_FILOSOFIS)_ | `ADALAH` | batiniah | object_decomposition |
| mahabutha _(KONSEP_FILOSOFIS)_ | `ADALAH` | asal materi yang jauh lebih halus dari benda (lebih halus dari abu) | manual_addition |
| ngaben _(RITUAL_KEMATIAN)_ | `BERTUJUAN_UNTUK` | memusnahkan segenap jasad sawa sehalus-halusnya _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| wujud sawa _(ISTILAH_UMUM_RITUAL)_ | `BERUBAH_MENJADI` | unsur, elemen atau mahabutha _(KONSEP_FILOSOFIS)_ | manual_addition |

## S1017

> terutama semua mahabutha yang lima unsur itu, kembali kepada induk asalnya masing-masing.

| subject | relation | object | source |
|---|---|---|---|
| mahabutha (yang lima unsur) _(KONSEP_FILOSOFIS)_ | `KEMBALI_KEPADA` | induk asalnya masing-masing | manual_addition |

## S1024

> sebagaimana pula diketahui, upacara itu selalu pula diiringi tujuan tambahan, misalnya permohonan kepada tuhan yang maha pengampun agar mendiang diberi ampun.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `DIBERI` | ampun | dependency_rule |

## S1034

> jenazah itu dibaringkan di bale adat (bila ada) dan sebaiknya pula diberi langse (tirai) secukupnya.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | bale adat _(BANGUNAN_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBERI` | langse _(SARANA_RITUAL)_ | dependency_rule |
| langse _(SARANA_RITUAL)_ | `ADALAH` | tirai | object_decomposition |

## S1039

> setelah semuanya itu siap, jenazah pun dimandikan di atas balai-balai rumah adat.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIMANDIKAN_DI_ATAS` | balai-balai rumah adat | manual_addition |

## S1040

> cara memandikan, yakni, mula-mula tikar alas jenazah ditarik, sehingga sawa berada di atas galar.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `BERADA_DI` | atas galar _(SARANA_RITUAL)_ | dependency_rule |

## S1056

> pepaga ini berfungsi sebagai balai-balai alas memandikan jenazah dan ngringkes.

| subject | relation | object | source |
|---|---|---|---|
| pepaga _(SARANA_RITUAL)_ | `BERFUNGSI_SEBAGAI` | balai-balai alas ngringkes | manual_edit |
| pepaga _(SARANA_RITUAL)_ | `BERFUNGSI_SEBAGAI` | balai-balai alas memandikan jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |

## S1058

> di atas pepaga itu dipasang secarik kain putih selaku "leluhur" atau langit-langit tandu tersebut.

| subject | relation | object | source |
|---|---|---|---|
| kain putih _(SARANA_RITUAL)_ | `DISEBUT` | "leluhur" (langit-langit tandu) _(SARANA_RITUAL)_ | manual_addition |
| kain putih _(SARANA_RITUAL)_ | `DIPASANG_DI_ATAS` | pepaga _(SARANA_RITUAL)_ | manual_addition |

## S1060

> setelah jenazah dipindahkan dari rumah adat ke pepaga, kain penutup dibuka.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPINDAHKAN_KE` | pepaga _(SARANA_RITUAL)_ | manual_addition |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPINDAHKAN_DARI` | rumah adat | manual_addition |
| kain penutup _(SARANA_RITUAL)_ | `DIBUKA` | setelah jenazah dipindahkan ke pepaga _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S1066

> jenazah ditelentangkan di atas pembungkus itu, serta mulailah diberi berbagai sarana simbolik pangringkesan, antara lain sesisir pisang selaku kalang bahu.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DITELENTANGKAN_DI` | pembungkus | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBERI` | berbagai sarana simbolik pangringkesan _(SARANA_RITUAL)_ | manual_edit |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBERI` | sesisir pisang | dependency_rule |

## S1079

> kemudian jenazah diikat dengan tali ktekung (tali bambu dipintal).

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIIKAT_DENGAN` | tali ktekung | dependency_rule |
| tali ktekung | `ADALAH` | tali bambu dipintal | object_decomposition |

## S1082

> jenazah yang masih tetap di atas pepaga itu, kemudian dikenakan baju serta disuguhi sajen kecil yang disebut pengulapan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPAKAIKAN` | baju | dependency_rule |
| sajen kecil | `DIPERSEMBAHKAN_KEPADA` | jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| sajen kecil | `DIKENAL_SEBAGAI` | pengulapan _(SARANA_RITUAL)_ | object_decomposition |

## S1086

> sesudah pangringkesan, jenazah dibaringkan kembali di atas balai-balai rumah adat.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | balai-balai rumah adat | dependency_rule |

## S1122

> nyekeh berarti jenazah dibaringkan di rumah adat dalam jangka waktu agak lama hingga tiba jatuhnya hari h untuk ngaben sesuai dewasa yang dipilih.

| subject | relation | object | source |
|---|---|---|---|
| nyekeh _(RITUAL_KEMATIAN)_ | `BERARTI` | jenazah dibaringkan di rumah adat dalam jangka waktu agak lama hingga tiba hari H untuk ngaben sesuai dewasa yang dipilih | manual_edit |

## S1123

> jenazah bisa disebut masekeh, bila telah berada minimal satu bulan, pernah dilewati bulan purnama dan tilem, serta upacaranya sudah memenuhi syarat.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIKENAL_SEBAGAI` | masekeh _(RITUAL_KEMATIAN)_ | dependency_rule |

## S1126

> nyekeh sawa merupakan pekerjaan berat, bila dibandingkan dengan menempuh jalan lain.

| subject | relation | object | source |
|---|---|---|---|
| nyekeh sawa _(RITUAL_KEMATIAN)_ | `ADALAH` | pekerjaan berat | dependency_rule |

## S1128

> itulah sebabnya, nyekeh sawa lebih sering ditempuh keluarga raja atau pendeta, karena dari golongan masyarakat itu yang memang lebih mampu melakukan upacara ini.

| subject | relation | object | source |
|---|---|---|---|
| nyekeh sawa _(RITUAL_KEMATIAN)_ | `DILAKUKAN_OLEH` | keluarga pendeta | dependency_rule |
| nyekeh sawa _(RITUAL_KEMATIAN)_ | `DILAKUKAN_OLEH` | keluarga raja | dependency_rule |

## S1133

> setelah selesai ngringkes, sawa dinaikkan di tumpang salu di rumah adat.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DINAIKKAN_KE` | tumpang salu _(SARANA_RITUAL)_ | dependency_rule |

## S1134

> sesajen dan punjung dihaturkan kepada mendiang.

| subject | relation | object | source |
|---|---|---|---|
| sesajen dan punjung _(SARANA_RITUAL)_ | `DIPERSEMBAHKAN_KEPADA` | mendiang _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |

## S1136

> damar kurung itu merupakan sarana permohonan kepada sanghyang agni, agar keletehan yang dipancarkan sawa mendiang diblokir terbatas, yakni hanya sebatas tanah pekarangan keluarga mendiang saja.

| subject | relation | object | source |
|---|---|---|---|
| damar kurung _(SARANA_RITUAL)_ | `ADALAH` | sarana permohonan kepada sanghyang agni _(ENTITAS_KEAGAMAAN)_ | manual_edit |
| damar kurung _(SARANA_RITUAL)_ | `BERTUJUAN_AGAR` | keletehan yang dipancarkan sawa mendiang diblokir terbatas, hanya sebatas tanah pekarangan keluarga mendiang | manual_addition |

## S1138

> mendiang mendapat ayaban upakara diuskamaligi, yang bermakna penyucian, sehingga letehnya sawa tidak atau kurang memancar ke luar dan tidak menghimbasi yang lain.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | ayaban upakara diuskamaligi yang bermakna penyucian | manual_edit |
| ayaban upakara diuskamaligi _(TAHAPAN_UPACARA)_ | `BERTUJUAN_AGAR` | leteh sawa tidak memancar ke luar dan tidak menghimbasi yang lain | manual_addition |

## S1160

> patus yang benar-benar merupakan bantuan gratis, selaku perwujudan rasa kebersamaan yang ada di dada krama.

| subject | relation | object | source |
|---|---|---|---|
| patus _(KONSEP_HUKUM_ADAT)_ | `BERPERAN_SEBAGAI` | perwujudan rasa kebersamaan yang ada di dada krama | dependency_rule |
| patus _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | bantuan gratis | manual_addition |

## S1163

> ngaben adalah suatu yadnya selaku pelaksanaan ajaran agama, yang hendaklah didukung dengan sredaning manah atau rasa hati tulus dan ikhlas.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | suatu yadnya selaku pelaksanaan ajaran agama | manual_edit |
| ngaben _(RITUAL_KEMATIAN)_ | `DIDUKUNG_DENGAN` | sredaning manah atau rasa hati tulus dan ikhlas | manual_addition |

## S1169

> sawa itu ditanam atau dibakar dengan status dititip sebelum ada rezeki, yang datangnya entah kapan untuk, menggelar upacara ngaben beberapa bulan atau bahkan beberapa tahun kemudian.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DITANAM_ATAU_DIBAKAR` | dengan status dititip | manual_addition |
| sawa (dititip) _(ISTILAH_UMUM_RITUAL)_ | `MENUNGGU` | rezeki untuk menggelar ngaben _(RITUAL_KEMATIAN)_ | manual_addition |

## S1173

> selain ngaben berstandar yang agak tinggi bisa ditempuh dengan biaya ringan, juga dapat memupuk rasa kekeluargaan dan kebersamaan.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `DITEMPUH_DENGAN` | biaya ringan | dependency_rule |
| ngaben _(RITUAL_KEMATIAN)_ | `MEMUPUK` | rasa kebersamaan | dependency_rule |
| ngaben _(RITUAL_KEMATIAN)_ | `MEMUPUK` | rasa kekeluargaan | dependency_rule |

## S1188

> sebagaimana pula dalam upacara lainnya, dalam upacara ini juga mempergunakan tirtha antara lain, tirtha panglukatan dan pabersihan selaku sarana penyucian, agar sawa boleh dan wajar menerima sesaji dan tirtha lainnya.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | sesaji _(SARANA_RITUAL)_ | dependency_rule |
| sawa _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | tirtha lainnya _(TIRTHA_SUCI)_ | dependency_rule |
| upacara ngaben titip _(RITUAL_KEMATIAN)_ | `MEMPERGUNAKAN` | tirtha pabersihan _(TIRTHA_SUCI)_ | manual_addition |
| upacara ngaben titip _(RITUAL_KEMATIAN)_ | `MEMPERGUNAKAN` | tirtha panglukatan _(TIRTHA_SUCI)_ | manual_addition |

## S1189

> tirtha yang dimohon di pamerajan dan pura lainnya, merupakan sarana restu dari ida bhatara di kahyangan tersebut terhadap arwah mendiang dalam peristiwa beralihnya dari dunia manusia ke dunia roh.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `ADALAH` | sarana restu dari ida bhatara di kahyangan tersebut | manual_edit |
| tirtha _(TIRTHA_SUCI)_ | `DITUJUKAN_UNTUK` | arwah mendiang dalam peristiwa beralihnya dari dunia manusia ke dunia roh | manual_addition |

## S1197

> masing-masing jun pere itu berisi tulisan aksara dan gambar yang khas.

| subject | relation | object | source |
|---|---|---|---|
| jun pere _(SARANA_RITUAL)_ | `BERISI` | tulisan aksara | dependency_rule |
| jun pere _(SARANA_RITUAL)_ | `BERISI` | gambar | dependency_rule |

## S1205

> tirtha pangentas merupakan sarana yang secara formal religius berfungsi memotong ikatan dan hubungan jasad dengan atma -jiwa dari mendiang.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `BERFUNGSI_UNTUK` | memotong ikatan dan hubungan jasad dengan atma-jiwa dari mendiang | manual_addition |

## S1206

> tirtha itu juga selaku sarana untuk menetapkan kedudukan arwah mendiang pada satu alam roh (pitra) tertentu sesuai dengan tingkat upacaranya (makingsan atau ngaben).

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `BERPERAN_SEBAGAI` | sarana untuk menetapkan kedudukan arwah mendiang pada satu alam roh (pitra) tertentu | manual_edit |

## S1213

> ada daerah yang membiasakan ayaban itu dilakukan di rumah, ada pula setelah sawa berada di kuburan setelah dibakar atau dikubur.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `BERADA_DI` | kuburan _(BANGUNAN_RITUAL)_ | dependency_rule |
| ayaban | `DILAKUKAN_DI` | rumah | manual_addition |

## S1215

> setelah tiba di setra, sawa diletakkan di atas lubang tempat penguburan atau di atas para-para tempat pembakarannya nanti.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | lubang tempat penguburan _(TAHAPAN_UPACARA)_ | dependency_rule |
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | para-para tempat pembakaran _(SARANA_RITUAL)_ | manual_addition |

## S1216

> setelah gulungan pangringkesar dibongkar, sawa disiram dengan toya penembak.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DISIRAM_DENGAN` | toya penembak _(TIRTHA_SUCI)_ | dependency_rule |

## S1219

> setelah itu, barulah sawa ditanam atau dibakar beserta semua alat pangringkesannya.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DITANAM_ATAU_DIBAKAR_BERSAMA` | semua alat pangringkesan _(SARANA_RITUAL)_ | manual_addition |

## S1221

> abu tulang dipungut dan dimasukkan ke dalam klungah nyuh gading/suku tunggal.

| subject | relation | object | source |
|---|---|---|---|
| abu tulang _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | klungah nyuh gading/suku tunggal _(SARANA_RITUAL)_ | dependency_rule |

## S1222

> kemudian abu tulang itu dihanyutkan ke laut.

| subject | relation | object | source |
|---|---|---|---|
| abu tulang _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | laut | dependency_rule |

## S1253

> ngaben dalam bahasa alus-singgihnya adalah malebuang atau atiwa-tiwa.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | atiwa-tiwa _(RITUAL_KEMATIAN)_ | manual_addition |
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | malebuang _(RITUAL_KEMATIAN)_ | manual_addition |

## S1256

> tapi ingat, ngaben tetap berarti dan bernama mreteka sawa secara religius, walau sering tidak terdapat jenazah nyata dalam acara itu.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `DIKENAL_SEBAGAI` | mreteka sawa _(RITUAL_KEMATIAN)_ | dependency_rule |

## S1261

> dari segi variasi besar kecilnya biaya dan "wibawa" lahiriahnya, ngaben merupakan salah satu yadnya yang paling banyak ragamnya.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | salah satu yadnya yang paling banyak ragamnya | manual_edit |
| ngaben _(RITUAL_KEMATIAN)_ | `BERVARIASI_DALAM` | besar kecilnya biaya | manual_addition |
| ngaben _(RITUAL_KEMATIAN)_ | `BERVARIASI_DALAM` | wibawa lahiriah | manual_addition |

## S1289

> yadnya selaku swadharma, seyogyanya dapat dilakukan.

| subject | relation | object | source |
|---|---|---|---|
| yadnya _(KONSEP_FILOSOFIS)_ | `BERPERAN_SEBAGAI` | swadharma _(KONSEP_HUKUM_ADAT)_ | dependency_rule |

## S1290

> dalam pada itu, sebagai pengorbanan, yadnya itu harus dirasakan sebagai "beban" bagi pemikulnya.

| subject | relation | object | source |
|---|---|---|---|
| yadnya _(KONSEP_FILOSOFIS)_ | `HARUS_DIRASAKAN_SEBAGAI` | beban (bagi pemikulnya) | manual_addition |

## S1308

> lalu muncul pertanyaan, mengapa tirtha punya tarif bak barang dagangan di pasar swalayan?

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `MEMILIKI` | tarif | manual_edit |

## S1328

> artinya, besar kecilnya punia atau "honorarium" itu hendaknya disinkronkan dengan jenis upacara tersebut.

| subject | relation | object | source |
|---|---|---|---|
| punia _(KONSEP_HUKUM_ADAT)_ | `DISINKRONKAN_DENGAN` | jenis upacara | manual_addition |

## S1335

> berapapun harganya, tirtha itu tetap punya nilai spiritual yang sama, karena dipuja dengan weda pengastawa yang sama.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `MEMILIKI` | nilai spiritual yang sama | dependency_rule |
| tirtha _(TIRTHA_SUCI)_ | `MEMILIKI` | harga | dependency_rule |
| tirtha _(TIRTHA_SUCI)_ | `DIPUJA_DENGAN` | weda pengastawa _(KONSEP_FILOSOFIS)_ | dependency_rule |

## S1361

> karena itu, kaum arif bijaksana mengamanatkan, setiap yadnya hendaklah didukung dengan penuh sredaning citta, penuh kesanggupan dan kesungguhan, kemulusan dan keikhlasan hati.

| subject | relation | object | source |
|---|---|---|---|
| yadnya _(KONSEP_FILOSOFIS)_ | `BERDASARKAN` | penuh sredaning citta _(KONSEP_FILOSOFIS)_ | dependency_rule |
| yadnya _(KONSEP_FILOSOFIS)_ | `BERDASARKAN` | penuh kesanggupan | dependency_rule |
| yadnya _(KONSEP_FILOSOFIS)_ | `BERDASARKAN` | kesungguhan | dependency_rule |
| yadnya _(KONSEP_FILOSOFIS)_ | `BERDASARKAN` | kemulusan | dependency_rule |
| yadnya _(KONSEP_FILOSOFIS)_ | `BERDASARKAN` | keikhlasan hati | dependency_rule |

## S1407

> ngaben jenis ini selalu dilakukan dengan sawa, artinya benar-benar sasarannya adalah jenazah secara nyata.

| subject | relation | object | source |
|---|---|---|---|
| ngaben cara yama purwana tatwa _(RITUAL_KEMATIAN)_ | `BERSASARAN` | jenazah secara nyata _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| ngaben cara yama purwana tatwa _(RITUAL_KEMATIAN)_ | `DILAKUKAN_DENGAN` | sawa _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S1409

> ngaben ini biasa dilakukan bagi sawa baru, bukan dari hasil galian tanam titip, juga bukan dari sawa yang disekeh.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `DITUJUKAN_UNTUK` | sawa baru _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |

## S1417

> sawa beserta semua sarana diangkut ke setra.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | setra _(BANGUNAN_RITUAL)_ | dependency_rule |
| semua sarana _(SARANA_RITUAL)_ | `DIBAWA_KE` | setra _(BANGUNAN_RITUAL)_ | manual_addition |

## S1419

> setibanya di setra, dibaringkanlah sawa itu di atas para-para pembakaran.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | para-para pembakaran | dependency_rule |

## S1421

> kemudian secara formal sawa diberi pakaian selengkapnya.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIBERI` | pakaian lengkap | manual_edit |

## S1422

> sebagaimana yang berlaku bagi tanam dan bakar titip, sawa disirati berbagai jenis tirtha.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIPERCIKI_DENGAN` | berbagai jenis tirtha _(TIRTHA_SUCI)_ | manual_addition |

## S1429

> daksina merupakan penegasan secara formal bahwa yadnya sudah selesai (siddhaning yadnya).

| subject | relation | object | source |
|---|---|---|---|
| daksina _(SARANA_RITUAL)_ | `ADALAH` | penegasan secara formal bahwa yadnya sudah selesai ( siddhaning yadnya ) | dependency_rule |

## S1430

> beras catur adalah lambang kekuatan panca dewata selaku manifestasi hyang widhi yang mengelola alam semesta (bhuwana agung).

| subject | relation | object | source |
|---|---|---|---|
| beras catur _(SARANA_RITUAL)_ | `ADALAH` | lambang kekuatan panca dewata selaku manifestasi hyang widhi yang mengelola alam semesta (bhuwana agung) | manual_edit |

## S1439

> masing-masing abu tulang kepala, tangan, punggung, dada, bokong, paha dan kaki diambil serta digiling lumat-lumat di atas sesenden, lantas dimasukkan ke dalam klungah nyuh gading serta dibentuk menjadi sukutunggal (sebuah wujud perlambang badan).

| subject | relation | object | source |
|---|---|---|---|
| abu tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki _(SARANA_RITUAL)_ | `DIGILING_DI` | sesenden _(SARANA_RITUAL)_ | dependency_rule |
| abu tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | klungah nyuh gading _(SARANA_RITUAL)_ | dependency_rule |
| abu tulang kepala, tangan, punggung, dada, bokong, paha, dan kaki _(SARANA_RITUAL)_ | `DIBENTUK_MENJADI` | sukutunggal (wujud perlambang badan) _(SARANA_RITUAL)_ | manual_addition |

## S1452

> menurut lontar petunjuknya, nywasta ditempuh orang dalam hal sawa tan inulatan atau jenazah seseorang yang tak ditemukan, misalnya mati dalam suatu pertempuran, meninggal di pulau seberang, tenggelam atau karena musibah lain.

| subject | relation | object | source |
|---|---|---|---|
| nywasta _(RITUAL_KEMATIAN)_ | `DILAKUKAN_DALAM_HAL` | jenazah yang tak dapat ditemukan (mati dalam pertempuran, tenggelam, di pulau seberang, dsb.) | manual_addition |

## S1456

> sebelum pertanyaan itu dijawab, perlu ditegaskan, bahwa nywasta merupakan ngaben yang sangat sederhana dalam hal sajen dan alat-alat upakaranya.

| subject | relation | object | source |
|---|---|---|---|
| nywasta _(RITUAL_KEMATIAN)_ | `ADALAH` | ngaben yang sangat sederhana | manual_edit |

## S1458

> pertama-tama sesajen dan alat upakaranya disediakan di rumah yang bersangkutan setuntas mungkin.

| subject | relation | object | source |
|---|---|---|---|
| sesajen dan alat upakara _(SARANA_RITUAL)_ | `DISEDIAKAN_DI` | rumah yang bersangkutan | manual_edit |

## S1461

> adegan yaitu suatu bentuk alat upakara yang terbuat dari daun rontal, beralaskan bakul kecil atau pangkon (paso kecil agak tinggi dari tanah atau perak).

| subject | relation | object | source |
|---|---|---|---|
| adegan _(SARANA_RITUAL)_ | `ADALAH` | alat upakara _(SARANA_RITUAL)_ | dependency_rule |
| adegan _(SARANA_RITUAL)_ | `BERALASKAN` | bakul kecil atau pangkon | manual_addition |
| adegan _(SARANA_RITUAL)_ | `TERBUAT_DARI` | daun rontal | manual_addition |

## S1465

> pengawak terdiri dari sebuah jun pere (periuk tanah yang kecil/masih merah) berisikan air, 54 atau 108 lembar daun alang-alang serta sembilan batang kayu cendana kecil-kecil (sebesar batang korek api).

| subject | relation | object | source |
|---|---|---|---|
| pengawak _(SARANA_RITUAL)_ | `TERDIRI_DARI` | jun pere _(SARANA_RITUAL)_ | dependency_rule |
| jun pere _(SARANA_RITUAL)_ | `ADALAH` | periuk tanah | object_decomposition |
| jun pere _(SARANA_RITUAL)_ | `BERISI` | 54 atau 108 lembar daun alang-alang | manual_addition |
| jun pere _(SARANA_RITUAL)_ | `BERISI` | air | manual_addition |
| jun pere _(SARANA_RITUAL)_ | `BERISI` | sembilan batang kayu cendana | manual_addition |

## S1467

> setelah tempat upacara ditata sebaik-baiknya, adegan dan pengawak didudukkan di suatu tempat yang telah ditentukan.

| subject | relation | object | source |
|---|---|---|---|
| adegan dan pengawak _(SARANA_RITUAL)_ | `DIDUDUKKAN_DI` | tempat yang telah ditentukan | manual_addition |

## S1468

> dengan sajen dan tirtha panglukatan selaku sarana utamanya, disucikanlah upakara tersebut hingga dianggap wajar untuk digunakan.

| subject | relation | object | source |
|---|---|---|---|
| upakara _(SARANA_RITUAL)_ | `DISUCIKAN_DENGAN` | sajen | manual_addition |
| upakara _(SARANA_RITUAL)_ | `DISUCIKAN_DENGAN` | tirtha panglukatan _(TIRTHA_SUCI)_ | manual_addition |

## S1474

> kepada mendiang, diayabkanlah sesajen antara lain: diuskamaligi, nasi angkeb, saji dan lain-lain.

| subject | relation | object | source |
|---|---|---|---|
| sesajen _(SARANA_RITUAL)_ | `MELIPUTI` | diuskamaligi _(TAHAPAN_UPACARA)_ | manual_addition |
| sesajen _(SARANA_RITUAL)_ | `DIPERSEMBAHKAN_KEPADA` | mendiang _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| sesajen _(SARANA_RITUAL)_ | `MELIPUTI` | nasi angkeb _(SARANA_RITUAL)_ | manual_addition |
| sesajen _(SARANA_RITUAL)_ | `MELIPUTI` | saji | manual_addition |

## S1476

> terutama disiratkanlah berbagai tirtha terhadap kedua perlambang yang duduk berdampingan itu.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `DIPERCIKKAN_PADA` | kedua perlambang | dependency_rule |

## S1477

> dalam hal ini, tirtha pangentas merupakan siratan terakhir, serta semua isinya (daun alang-alang, walantaga, kekitir, pripih dan sebagainya), dipersatukan dengan isi pengawak.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | siratan terakhir | dependency_rule |
| tirtha pangentas (dan isinya) _(TIRTHA_SUCI)_ | `DIPERSATUKAN_DENGAN` | isi pengawak _(SARANA_RITUAL)_ | manual_addition |

## S1482

> sawa ini dibakar dengan khusuknya, diiringi dengan kakawin yang khas dengan penuh bhakti, hingga hangus jadi abu seluruhnya.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DISERTAI` | kakawin | dependency_rule |
| sawa _(ISTILAH_UMUM_RITUAL)_ | `MENJADI` | abu (seluruhnya) _(SARANA_RITUAL)_ | manual_addition |
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIBAKAR_DENGAN` | khusuk | manual_addition |

## S1483

> kemudian, abu itu dimasukkan ke dalam klungah nyuh gading yang dikasturi dan disukutunggalkan.

| subject | relation | object | source |
|---|---|---|---|
| abu _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | klungah nyuh gading yang dikasturi dan disukutunggalkan | manual_edit |

## S1493

> manah yang sredah itu pula ditentukan oleh standar kedudukan seseorang di masyarakat, termasuk kemampuan sosial ekonominya.

| subject | relation | object | source |
|---|---|---|---|
| kemampuan sosial ekonomi | `JENIS_DARI` | standar kedudukan seseorang di masyarakat | manual_addition |

## S1497

> sawa wedana dapat memberikan wibawa dan kemegahan semantap-mantapnya.

| subject | relation | object | source |
|---|---|---|---|
| sawa wedana _(RITUAL_KEMATIAN)_ | `MEMBERIKAN` | wibawa | dependency_rule |
| sawa wedana _(RITUAL_KEMATIAN)_ | `MEMBERIKAN` | kemegahan semantap-mantap | dependency_rule |

## S1504

> selaku nama upacara, ngulapin juga mempunyai makna yang mirip dengan itu pula.

| subject | relation | object | source |
|---|---|---|---|
| ngulapin _(TAHAPAN_UPACARA)_ | `MEMILIKI` | makna yang mirip dengan itu pula | dependency_rule |
| ngulapin _(TAHAPAN_UPACARA)_ | `BERPERAN_SEBAGAI` | nama upacara | dependency_rule |

## S1514

> untuk itu sebuah adegan yang sudah disisipkan sebuah awak-awakaning sawa yang terbuat dari sebilah papan cendana atau majagau tipis, diarak menuju setra tempat jasad mendiang ditanam atau bakar titip.

| subject | relation | object | source |
|---|---|---|---|
| adegan _(SARANA_RITUAL)_ | `DIUSUNG` | setra tempat jasad mendiang _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| adegan _(SARANA_RITUAL)_ | `DISISIPI` | awak-awakaning sawa yang terbuat dari sebilah papan cendana atau majagau tipis | manual_addition |

## S1522

> dalam situasi itu, mendiang dianggap seseorang yang masih hidup.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `DIANGGAP_SEBAGAI` | seseorang yang masih hidup | manual_addition |

## S1523

> selanjutnya, bersama keluarga atau anak keturunan selaku wakilnya, mendiang melakumuspa pamitan kepada sang hyang prajapati, pura dalem dan sedahan setra.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `BERPAMITAN_KEPADA` | hyang prajapati _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MELAKUKAN` | muspa pamitan _(TAHAPAN_UPACARA)_ | manual_addition |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `BERPAMITAN_KEPADA` | pura dalem _(BANGUNAN_RITUAL)_ | manual_addition |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `BERPAMITAN_KEPADA` | sedahan setra _(BANGUNAN_RITUAL)_ | manual_addition |

## S1525

> adegan dan pengawak itu kemudian disemayamkan pada balai adat, diberi sajen dan perjamuan lain, sebagaimana layaknya menyambut dan melayani seorang keluarga yang baru datang dari bepergian jauh.

| subject | relation | object | source |
|---|---|---|---|
| adegan dan pengawak _(SARANA_RITUAL)_ | `BERADA_DI` | balai adat | dependency_rule |
| adegan dan pengawak _(SARANA_RITUAL)_ | `DIBERI` | sajen | dependency_rule |
| adegan dan pengawak _(SARANA_RITUAL)_ | `DIBERI` | perjamuan lain | dependency_rule |

## S1533

> demikianlah, pengawak tersebut untuk selanjutnya mendapat upacara, sama dengan sawa asli dalam pengabenan itu.

| subject | relation | object | source |
|---|---|---|---|
| pengawak _(SARANA_RITUAL)_ | `MEMPEROLEH` | upacara | dependency_rule |
| pengawak | `DIPERLAKUKAN_SAMA_DENGAN` | sawa asli _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S1544

> apa lagi dahulu, formalin belum dikenal, sehingga sawa yang sudah berhari-hari atau bahkan beberapa minggu, menyebarkan bau yang kurang sedap.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `MENYEBARKAN` | bau yang kurang sedap | manual_edit |

## S1552

> sumpe itu berfungsi selaku penguat rekatan antar badan peti dengan tutupnya.

| subject | relation | object | source |
|---|---|---|---|
| sumpe _(SARANA_RITUAL)_ | `BERFUNGSI_SEBAGAI` | penguat rekatan antar badan peti dengan tutupnya | manual_edit |

## S1556

> panca datu ini mempunyai daya mistik-religius, untuk memohon kepada hyang widhi dalam manifestasi sebagai panca dewata (içwara, brahma, mahadewa, wisnu dan siwa) yang mengatur bhuwana agung ini, supaya unsur jasad dari mendiang kembali dengan baik ke dalam lingkungan bhuwana agung, dengan tidak menyebabkan letehnya alam raya-nya ini.

| subject | relation | object | source |
|---|---|---|---|
| panca datu _(SARANA_RITUAL)_ | `MEMILIKI` | daya mistik-religius | dependency_rule |
| panca datu | `DIPAKAI_UNTUK` | memohon kepada hyang widhi (restu panca dewata) | manual_addition |

## S1558

> demikianlah sawa kembali dibaringkan di atas tumpang salu, serta dikurung dengan paplengkungan sebagaimana semula.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIKURUNG_DENGAN` | paplengkungan _(BANGUNAN_RITUAL)_ | manual_addition |
| sawa _(ISTILAH_UMUM_RITUAL)_ | `DIBARINGKAN_DI` | tumpang salu _(BANGUNAN_RITUAL)_ | manual_addition |

## S1559

> dengan demikian, siaplah sudah sawa kita menghadapi upacara pabersihan dengan berbagai rangkaiannya.

| subject | relation | object | source |
|---|---|---|---|
| sawa _(ISTILAH_UMUM_RITUAL)_ | `MENGHADAPI` | upacara pabersihan dengan berbagai rangkaian nya | dependency_rule |

## S1584

> perlu dijelaskan, harapan agar sang pitara mewujudkan bayangan dirinya dalam dan dengan air ening, maka perlu dilakukan dengan pujastawa oleh ida sang sadaka pada upacara tarpana nantinya.

| subject | relation | object | source |
|---|---|---|---|
| pitara _(KONSEP_FILOSOFIS)_ | `MEWUJUDKAN` | bayangan diri dalam air ening | manual_addition |
| tarpana | `DILAKUKAN_OLEH` | ida sang sadaka _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| tarpana | `DILAKUKAN_DENGAN` | pujastawa | manual_addition |

## S1588

> lain dari pada itu, lingga sarira sang pitara juga berunsur bayu dan akasa pula.

| subject | relation | object | source |
|---|---|---|---|
| lingga sarira pitara _(KONSEP_FILOSOFIS)_ | `BERUNSUR` | bayu _(KONSEP_FILOSOFIS)_ | dependency_rule |
| lingga sarira pitara _(KONSEP_FILOSOFIS)_ | `BERUNSUR` | akasa _(KONSEP_FILOSOFIS)_ | dependency_rule |

## S1597

> kajang atau kakerebsari adalah nama sebuah alat upakara yang pelik dalam pangabenan ini.

| subject | relation | object | source |
|---|---|---|---|
| kajang atau kakerebsari _(SARANA_RITUAL)_ | `ADALAH` | alat upakara yang pelik dalam pangabenan ini | dependency_rule |

## S1601

> setelah diplaspas (disucikan), kajang dengan segala bagiannya itu berfungsi sebagai "kain kafan teratas" pada plengkungan sawa.

| subject | relation | object | source |
|---|---|---|---|
| kajang _(SARANA_RITUAL)_ | `BERFUNGSI_SEBAGAI` | kain kafan teratas (pada plengkungan sawa) | manual_edit |
| kajang _(SARANA_RITUAL)_ | `BERADA_DI` | plengkungan sawa _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S1602

> kajang itu akan disambung dengan lancingan, yakni kain putih yang panjangnya puluhan meter.

| subject | relation | object | source |
|---|---|---|---|
| kajang _(SARANA_RITUAL)_ | `DISAMBUNG_DENGAN` | lancingan _(SARANA_RITUAL)_ | dependency_rule |
| lancingan | `ADALAH` | kain putih (panjangnya puluhan meter) _(SARANA_RITUAL)_ | manual_addition |

## S1603

> di kala jenazah diangkut ke setra tempat pembakaran, lancingan kajang ini dijunjung dengan khidmat oleh segenap keturunan mendiang, sehingga membentuk barisan panjang.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | setra tempat pembakaran _(BANGUNAN_RITUAL)_ | manual_addition |
| lancingan kajang | `DIJUNJUNG_OLEH` | segenap keturunan mendiang _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S1605

> perlu diingat, bahwa saat mlaspas, kajang itu diletakkan di depan pendeta yang memujanya.

| subject | relation | object | source |
|---|---|---|---|
| kajang _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | depan pendeta yang memujanya | manual_edit |

## S1606

> dengan puja itu kajang disucikan dan "dihidupkan", untuk dapat bertuah betapa mestinya.

| subject | relation | object | source |
|---|---|---|---|
| kajang _(SARANA_RITUAL)_ | `DISUCIKAN_DENGAN` | puja | dependency_rule |
| kajang _(SARANA_RITUAL)_ | `DIHIDUPKAN_DENGAN` | puja | manual_addition |

## S1609

> moksa adalah menjadi satunya jiwa/atma dengan paratma/brahman, serta kembalinya pula unsur badan manusia ke asalnya yakni badannya bhuwana agung (pancamahabutha).

| subject | relation | object | source |
|---|---|---|---|
| moksa | `ADALAH` | kembalinya unsur badan manusia ke asalnya (bhuwana agung/pancamahabutha) | manual_addition |
| moksa _(KONSEP_FILOSOFIS)_ | `ADALAH` | penyatuan jiwa/atma dengan paratma/brahman _(KONSEP_FILOSOFIS)_ | manual_addition |

## S1610

> dengan demikian, ngaben pun merupakan salah satu tahap untuk mencapai moksa.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `ADALAH` | satu tahap untuk mencapai moksa _(KONSEP_FILOSOFIS)_ | dependency_rule |

## S1629

> kita maklumi bahwa kajang dengan suratannya yang sangat khas itu, oleh umat kita (khususnya angkatan tua) dianggap mempunyai nilai dan bobot istimewa, yakni selaku atribut nilai martabat warga ("cihna kawongan").

| subject | relation | object | source |
|---|---|---|---|
| kajang _(SARANA_RITUAL)_ | `BERPERAN_SEBAGAI` | atribut nilai martabat warga | manual_addition |
| kajang _(SARANA_RITUAL)_ | `MEMILIKI` | nilai dan bobot istimewa | manual_addition |

## S1639

> demikianlah setelah selesai dipuja pada pamlaspasan dengan penuh khidmat, kajang itu diletakkan di atas paplengkungan jenazah, sebagaimana telah disinggung di depan.

| subject | relation | object | source |
|---|---|---|---|
| kajang _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | paplengkungan jenazah _(BANGUNAN_RITUAL)_ | dependency_rule |
| kajang _(SARANA_RITUAL)_ | `DIPUJA_PADA` | pamlaspasan | manual_addition |

## S1642

> angenan, merupakan sebuah pelita kecil terbuat dari kulit telur ayam berminyak kelapa.

| subject | relation | object | source |
|---|---|---|---|
| angenan _(SARANA_RITUAL)_ | `ADALAH` | pelita kecil | dependency_rule |
| angenan _(SARANA_RITUAL)_ | `TERBUAT_DARI` | kulit telur ayam berminyak kelapa | manual_addition |

## S1647

> manah mendiang dicabut dengan puja pendeta lalu diletakkan pada angenan.

| subject | relation | object | source |
|---|---|---|---|
| manah mendiang _(KONSEP_FILOSOFIS)_ | `DICABUT_DENGAN` | puja pendeta | dependency_rule |
| manah mendiang _(KONSEP_FILOSOFIS)_ | `DILETAKKAN_DI` | angenan _(SARANA_RITUAL)_ | dependency_rule |

## S1650

> kemudian pisang jati, adalah sebuah upakara yang berbadankan bakul-kecil (bagaikan daksina).

| subject | relation | object | source |
|---|---|---|---|
| pisang jati _(SARANA_RITUAL)_ | `ADALAH` | upakara yang berbadankan bakul-kecil ( bagaikan daksina ) | dependency_rule |

## S1657

> sedangkan panguryagan adalah alat upakara yang beralaskan tembong (nyiru yang tabingnya tinggi), berisi bermacam-macam ramuan.

| subject | relation | object | source |
|---|---|---|---|
| panguryagan | `BERISI` | bermacam-macam ramuan | manual_addition |
| panguryagan | `BERALASKAN` | tembong (nyiru yang tabingnya tinggi) | manual_addition |

## S1681

> pada ngaben jenis sawa wedana ini, bersamaan dengan angenan, damar kurung pun ikut dinyalakan.

| subject | relation | object | source |
|---|---|---|---|
| damar kurung _(SARANA_RITUAL)_ | `DINYALAKAN_SAAT` | ngaben jenis sawa wedana (dan angenan turut dinyalakan) | manual_addition |

## S1688

> adegan ini berwujud cili terbuat dari rontal dilapisi kertas emas.

| subject | relation | object | source |
|---|---|---|---|
| adegan _(SARANA_RITUAL)_ | `BERWUJUD` | cili _(SARANA_RITUAL)_ | dependency_rule |
| cili | `TERBUAT_DARI` | rontal (dilapisi kertas emas) | manual_addition |

## S1699

> sangaskara, samskara atau panyangaskara adalah upacara penyucian.

| subject | relation | object | source |
|---|---|---|---|
| sangaskara, samskara, atau panyangaskara _(TAHAPAN_UPACARA)_ | `ADALAH` | upacara penyucian | dependency_rule |

## S1713

> sebentar kemudian, adegan yang semula berada di samping jenazah, diambil dengan penuh hormat oleh keluarga yang ngaben (bila ada anak mendiang yang terkemuka).

| subject | relation | object | source |
|---|---|---|---|
| adegan _(SARANA_RITUAL)_ | `DIAMBIL_OLEH` | keluarga (yang ngaben) | manual_addition |

## S1714

> adegan itu dibawa menghadap serta melakukan sembah bakti kepada pendeta.

| subject | relation | object | source |
|---|---|---|---|
| adegan _(SARANA_RITUAL)_ | `MELAKUKAN` | sembah bakti | dependency_rule |
| adegan _(SARANA_RITUAL)_ | `DIBAWA_MENGHADAP` | pendeta | manual_addition |

## S1717

> adegan, adalah alat upakara, tempat atma mendiang "didudukkan".

| subject | relation | object | source |
|---|---|---|---|
| adegan _(SARANA_RITUAL)_ | `ADALAH` | alat upakara _(SARANA_RITUAL)_ | dependency_rule |
| adegan _(SARANA_RITUAL)_ | `ADALAH` | tempat atma mendiang _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S1732

> upadesa yang dalam masyarakat kita lebih dikenal dengan nama upanisad, menurut para ahli memang berarti "bisikan dang guru" kepada sisia atau juga berarti "tatwa pengarahan hidup." tentang acara yang pelik ini, satu hal perlu kita catat, bahwa

| subject | relation | object | source |
|---|---|---|---|
| upadesa _(TAHAPAN_UPACARA)_ | `DIKENAL_DENGAN` | nama upanisad _(KONSEP_FILOSOFIS)_ | dependency_rule |
| upadesa _(TAHAPAN_UPACARA)_ | `BERARTI` | bisikan dang guru | dependency_rule |
| upadesa | `BERARTI` | tatwa pengarahan hidup | manual_addition |

## S1738

> kalau mendiang semasa hidupnya punya kedudukan tertentu (seorang pemangku, pejabat, sastrawan dan sebagainya), dengan rendah hati mundurlah ida bagus atau ida ayu kita.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `ADALAH` | pemangku _(ENTITAS_KEAGAMAAN)_ | object_decomposition |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `ADALAH` | pejabat | manual_addition |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `ADALAH` | sastrawan | manual_addition |

## S1747

> begitulah setelah paguntingan dan upadesa, berakhirnya, kembalilah adegan didudukkan pada ruang paturon di samping jenazah.

| subject | relation | object | source |
|---|---|---|---|
| adegan _(SARANA_RITUAL)_ | `BERADA_DI` | ruang paturon (di samping jenazah) _(ISTILAH_UMUM_RITUAL)_ | manual_edit |

## S1753

> dengan demikian, mendiang diyakini akan "akrab" dengan para penghadang itu.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `AKRAB_DENGAN` | penghadang | manual_addition |

## S1754

> karena akrab, maka mendiang diterima sebagai "warga baru" dalam pergaulan di alam roh tersebut.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `DITERIMA_SEBAGAI` | warga baru dalam pergaulan alam roh | manual_addition |

## S1763

> tentu saja sebuah banten bebangkit atau pulagembal selaku dasarnya, serta sebuah sekah abin sebagai ciri khususnya.

| subject | relation | object | source |
|---|---|---|---|
| banten bebangkit atau pulagembal _(SARANA_RITUAL)_ | `BERPERAN_SEBAGAI` | dasar | manual_addition |
| sekah abin | `BERPERAN_SEBAGAI` | ciri khusus | manual_addition |

## S1764

> sebagaimana namanya, sekah abin ini dipangku (abin = dipangku) oleh yang menggelar yadnya di kala ia menghaturkan sembah bhakti.

| subject | relation | object | source |
|---|---|---|---|
| sekah abin | `DIPANGKU_OLEH` | yang menggelar yadnya | manual_addition |

## S1776

> upakara itu berupa uang kepeng yang dibungkus dengan daun dapdap dan diikat dengan benang tridatu (merah, hitam dan putih).

| subject | relation | object | source |
|---|---|---|---|
| upakara _(SARANA_RITUAL)_ | `BERUPA` | uang kepeng _(SARANA_RITUAL)_ | dependency_rule |
| uang kepeng | `DIIKAT_DENGAN` | benang tridatu (merah, hitam dan putih) | manual_addition |
| uang kepeng | `DIBUNGKUS_DENGAN` | daun dapdap _(SARANA_RITUAL)_ | manual_addition |

## S1782

> menurut sang arif bijaksana, pamerasan adalah upacara timbang terima secara keagamaan, antara mendiang yang akan pergi ke dunia lain dengan keluarga (terutama anak-anak) yang masih hidup.

| subject | relation | object | source |
|---|---|---|---|
| pamerasan _(TAHAPAN_UPACARA)_ | `ADALAH` | upacara timbang terima (secara keagamaan) | manual_edit |
| pamerasan _(TAHAPAN_UPACARA)_ | `DILAKUKAN_ANTARA` | mendiang dan keluarga yang masih hidup | manual_addition |

## S1783

> mendiang menyerahkan swadharma, beban dan tanggung jawab, diiringi dengan penyerahan hak dan berbagai milik yang dulunya ada pada mendiang.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MENYERAHKAN` | swadharma _(KONSEP_HUKUM_ADAT)_ | dependency_rule |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MENYERAHKAN` | beban | dependency_rule |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MENYERAHKAN` | tanggung jawab | dependency_rule |
| mendiang | `MENYERAHKAN` | hak dan berbagai milik yang dulunya ada pada mendiang | manual_addition |

## S1794

> upakara ini juga dilengkapi keris (bila ada) dan satu dua perhiasan pusaka (cincin dan sebagainya).

| subject | relation | object | source |
|---|---|---|---|
| upakara _(SARANA_RITUAL)_ | `DILENGKAPI` | keris | dependency_rule |
| upakara _(SARANA_RITUAL)_ | `DILENGKAPI` | satu dua perhiasan pusaka | dependency_rule |
| satu dua perhiasan pusaka | `ADALAH` | cincin | object_decomposition |

## S1823

> perlu ditegaskan, sesuai dengan opini masyarakat, bila mendiang di masa hidupnya memegang jabatan, maka dalam pengabenan upacara panebusan merupakan sesuatu yang mutlak atau paling tidak dianggap sangat penting.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMEGANG` | jabatan | dependency_rule |
| upacara panebusan | `ADALAH` | sesuatu yang mutlak (dalam pengabenan) | manual_addition |

## S1832

> dengan demikian, karma phala orangtua atau leluhur (dalam batas tertentu) dapat diwariskan kepada keturunannya.

| subject | relation | object | source |
|---|---|---|---|
| karma phala orangtua atau leluhur _(KONSEP_FILOSOFIS)_ | `DIWARISKAN_KEPADA` | keturunan (dalam batas tertentu) | manual_addition |

## S1845

> panebusan dan bahkan semua upacara dalam pitra yadnya pasti berpengaruh kepada kedudukan sang pitara di alam sana.

| subject | relation | object | source |
|---|---|---|---|
| panebusan _(TAHAPAN_UPACARA)_ | `MEMPENGARUHI` | kedudukan pitara _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| semua upacara dalam pitra yadnya _(RITUAL)_ | `MEMPENGARUHI` | kedudukan pitara _(ENTITAS_KEAGAMAAN)_ | manual_addition |

## S1850

> mamutru tentu saja asal katanya "putru" dan merupakan perubahan dari kata "pitra".

| subject | relation | object | source |
|---|---|---|---|
| mamutru | `MERUPAKAN_PERUBAHAN_DARI` | pitra _(KONSEP_FILOSOFIS)_ | manual_addition |
| mamutru | `BERASAL_DARI_KATA` | putru | manual_addition |

## S1853

> lontar putru ada beberapa jenis antara lain putru sangaskara, dan putru saji.

| subject | relation | object | source |
|---|---|---|---|
| lontar putru | `MEMILIKI_JENIS` | putru saji _(NASKAH_SUCI)_ | manual_addition |
| lontar putru | `MEMILIKI_JENIS` | putru sangaskara _(NASKAH_SUCI)_ | manual_addition |

## S1854

> masing-masing lontar itu lebih banyak merinci tentang atma/pitara itu.

| subject | relation | object | source |
|---|---|---|---|
| lontar _(NASKAH_SUCI)_ | `MERINCI` | atma/pitara _(ENTITAS_KEAGAMAAN)_ | dependency_rule |

## S1879

> sejalan dengan arti pemberian pengarahan ini, maka lontar yang dibaca sudah merupakan bacaan pilihan.

| subject | relation | object | source |
|---|---|---|---|
| lontar _(NASKAH_SUCI)_ | `ADALAH` | bacaan pilihan | dependency_rule |

## S1889

> dengan demikian, bila pabersihan dilakukan dua atau tiga hari sebelum ngaben, maka pengambilan air ini tidaklah pada hari pabersihan, melainkan disesuaikan dengan syarat tadi.

| subject | relation | object | source |
|---|---|---|---|
| pabersihan _(TAHAPAN_UPACARA)_ | `DILAKUKAN` | dua atau tiga hari sebelum ngaben | manual_edit |

## S1898

> yeh panembak itu ditaruh di suatu tempat di pamrajan, menunggu saat digunakan pada pengabenan.

| subject | relation | object | source |
|---|---|---|---|
| yeh panembak _(TIRTHA_SUCI)_ | `DILETAKKAN_DI` | tempat pamrajan _(BANGUNAN_RITUAL)_ | dependency_rule |
| yeh panembak | `DIGUNAKAN_PADA` | pengabenan _(RITUAL_KEMATIAN)_ | manual_addition |

## S1899

> menurut sejumlah pakar, yeh panembak yang sudah lazim dipakai umat hindu di bali itu, adalah sarana penyucian jenazah yang digunakan oleh penganut sekte paksa surya.

| subject | relation | object | source |
|---|---|---|---|
| yeh panembak _(TIRTHA_SUCI)_ | `ADALAH` | sarana penyucian jenazah yang digunakan oleh penganut sekte paksa surya | dependency_rule |

## S1915

> suatu misal, pabersihan dilangsungkan pada hari senin dan pangabenan digelar hari kamis tiga hari kemudian.

| subject | relation | object | source |
|---|---|---|---|
| pangabenan _(RITUAL_KEMATIAN)_ | `DIGELAR` | hari kamis | dependency_rule |
| pabersihan | `DILANGSUNGKAN_PADA` | hari senin | manual_addition |

## S1931

> berdasarkan lontar yama purwana tatwa, recadana (istilah lombok dan karangasem) atau swasta geni yang sederhana pun pangabenan telah selesai dengan tuntas.

| subject | relation | object | source |
|---|---|---|---|
| recadana atau swasta geni | `MELENGKAPI` | pangabenan _(RITUAL_KEMATIAN)_ | manual_addition |

## S1936

> terutama, atma dengan lingga-sariranya diberangkatkanlah ke alamnya pula.

| subject | relation | object | source |
|---|---|---|---|
| atma lingga-sarira _(KONSEP_FILOSOFIS)_ | `DIBAWA_KE` | alam | dependency_rule |

## S1937

> sebagaimana telah disebutkan, bahwa sawa wedana adalah pengabenan yang paling banyak ada upacara, sesajen dan upakaranya.

| subject | relation | object | source |
|---|---|---|---|
| sawa wedana _(RITUAL_KEMATIAN)_ | `ADALAH` | pengabenan yang paling banyak ada upacara , sesajen dan upakara nya | dependency_rule |

## S1938

> karena itu pengabenan ini dinilai tingkat utama.

| subject | relation | object | source |
|---|---|---|---|
| pengabenan _(RITUAL_KEMATIAN)_ | `DINILAI_SEBAGAI` | tingkat utama | manual_addition |

## S1963

> pering dibuat berpasang-pasangan sebagai perlambang purusa-pradana dan diletakkan selaku penambah bobot, nilai dan asri bagaikan mahkotanya pada sajen untuk surya, penebusan, pamerasan, banten teben dan sebagainya.

| subject | relation | object | source |
|---|---|---|---|
| pering _(SARANA_RITUAL)_ | `DILETAKKAN_PADA` | banten teben _(SARANA_RITUAL)_ | manual_addition |
| pering _(SARANA_RITUAL)_ | `MENYERUPAI` | mahkota | manual_addition |
| pering _(SARANA_RITUAL)_ | `DILETAKKAN_PADA` | pamerasan _(TAHAPAN_UPACARA)_ | manual_addition |
| pering _(SARANA_RITUAL)_ | `DILETAKKAN_PADA` | penebusan _(TAHAPAN_UPACARA)_ | manual_addition |
| pering _(SARANA_RITUAL)_ | `MELAMBANGKAN` | purusa-pradana _(KONSEP_FILOSOFIS)_ | manual_addition |
| pering _(SARANA_RITUAL)_ | `DILETAKKAN_PADA` | sajen untuk surya _(SARANA_RITUAL)_ | manual_addition |

## S1982

> bade adalah bangunan untuk sawa.

| subject | relation | object | source |
|---|---|---|---|
| bade _(SARANA_RITUAL)_ | `ADALAH` | bangunan untuk sawa _(ISTILAH_UMUM_RITUAL)_ | manual_edit |

## S1985

> selain itu bade menunjukkan status sosial seseorang dalam masyarakat.

| subject | relation | object | source |
|---|---|---|---|
| bade _(SARANA_RITUAL)_ | `MENUNJUKKAN` | status sosial seseorang | dependency_rule |

## S1987

> bade jenis apa yang boleh dan wajar dipakai oleh seseorang, ditentukan berdasarkan statusnya dalam tata kemasyarakatan pada zaman itu.

| subject | relation | object | source |
|---|---|---|---|
| jenis bade yang dipakai seseorang _(SARANA_RITUAL)_ | `DITENTUKAN_BERDASARKAN` | status orang tersebut dalam tata kemasyarakatan pada zaman itu _(STRUKTUR_SOSIAL_ADAT)_ | manual_addition |

## S2000

> bade yang bertingkat 11 dipakai untuk jenazah raja bali (gelgel/klungkung).

| subject | relation | object | source |
|---|---|---|---|
| bade _(SARANA_RITUAL)_ | `DIPAKAI_UNTUK` | jenazah raja bali _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| bade _(SARANA_RITUAL)_ | `MEMILIKI_TINGKAT` | 11 | dependency_rule |
| raja bali | `BERASAL_DARI` | gelgel/klungkung | manual_addition |

## S2001

> bade bertingkat sembilan digunakan untuk keluarga raja atau raja-raja bawahan raja bali.

| subject | relation | object | source |
|---|---|---|---|
| bade _(SARANA_RITUAL)_ | `DIPAKAI_UNTUK` | keluarga raja | dependency_rule |
| bade _(SARANA_RITUAL)_ | `DIPAKAI_UNTUK` | raja-raja bawahan raja bali | dependency_rule |
| bade _(SARANA_RITUAL)_ | `MEMILIKI_TINGKAT` | sembilan | dependency_rule |

## S2002

> bade bertingkat tujuh dipakai bagi keluarga yang leluhurnya pernah menjadi punggawa dan pejabat yang sederajat.

| subject | relation | object | source |
|---|---|---|---|
| bade _(SARANA_RITUAL)_ | `DITUJUKAN_UNTUK` | keluarga yang leluhurnya pernah menjadi punggawa dan pejabat yang sederajat | manual_edit |
| bade _(SARANA_RITUAL)_ | `MEMILIKI_TINGKAT` | tujuh | dependency_rule |

## S2003

> adapun wadah adalah usungan yang tanpa badawang mungkin bertingkat memakai hiasan boma dan warna kapas terbatas.

| subject | relation | object | source |
|---|---|---|---|
| wadah _(SARANA_RITUAL)_ | `ADALAH` | usungan yang tanpa badawang | manual_edit |
| wadah _(SARANA_RITUAL)_ | `MEMAKAI` | hiasan boma dan warna kapas terbatas | manual_addition |

## S2028

> menjelang pemberangkatan ke setra, mangle digantungkan pada tiap sudut atap bade atau wadah di masing-masing tingkatan.

| subject | relation | object | source |
|---|---|---|---|
| mangle _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | sudut atap wadah _(SARANA_RITUAL)_ | dependency_rule |
| mangle _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | sudut atap bade _(SARANA_RITUAL)_ | dependency_rule |
| mangle _(SARANA_RITUAL)_ | `DIGANTUNGKAN_DI` | masing-masing tingkatan bade atau wadah _(SARANA_RITUAL)_ | manual_addition |

## S2029

> dengan demikian, banyak sedikitnya mangle yang harus dibuat, tergantung pada tingkatan bade atau wadah bersangkutan.

| subject | relation | object | source |
|---|---|---|---|
| mangle _(SARANA_RITUAL)_ | `BERGANTUNG_PADA` | tingkatan bade atau wadah _(SARANA_RITUAL)_ | manual_addition |

## S2034

> dalam hal ini, mangle merupakan pengganti tingkat bade atau wadah.

| subject | relation | object | source |
|---|---|---|---|
| mangle _(SARANA_RITUAL)_ | `ADALAH` | pengganti tingkat bade atau wadah _(SARANA_RITUAL)_ | manual_edit |

## S2040

> setelah tiba di kuburan, jenazah pun diturunkan serta dibaringkan dalam "balai-balai".

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBARINGKAN` | balai-balai | dependency_rule |
| jenazah | `DITURUNKAN_DI` | kuburan _(BANGUNAN_RITUAL)_ | manual_addition |

## S2045

> di samping bentuk yang ditentukan oleh konstruksi praktisnya selaku tempat pembaringan "jenazah plus dapur" pembakaran, maka patulangan dibuat dalam berbagai bentuk yang berwujud binatang, yang mempunyai nilai religi tertentu.

| subject | relation | object | source |
|---|---|---|---|
| patulangan _(SARANA_RITUAL)_ | `DIBUAT_BERBENTUK` | binatang (yang mempunyai nilai religi tertentu) | manual_addition |
| patulangan | `BERFUNGSI_SEBAGAI` | tempat pembaringan jenazah (dan dapur pembakaran) | manual_addition |

## S2055

> patulangan yang berbentuk naga kahang dan gajah mina (yakni binatang yang biasa hidup di air), adalah pertanda bahwa mereka merupakan keturunan dari orang yang condong pada paksa wesnawa.

| subject | relation | object | source |
|---|---|---|---|
| patulangan _(SARANA_RITUAL)_ | `BERBENTUK` | naga kahang _(SARANA_RITUAL)_ | dependency_rule |
| patulangan _(SARANA_RITUAL)_ | `BERBENTUK` | gajah mina _(SARANA_RITUAL)_ | dependency_rule |
| patulangan yang berbentuk naga kahang dan gajah mina _(SARANA_RITUAL)_ | `ADALAH` | pertanda bahwa keluarga tersebut keturunan dari orang yang condong pada paksa wesnawa | manual_addition |

## S2056

> sedang patulangan yang berbentuk macan, singa, gadarba (beruang) dan binatang buas lainnya adalah ciri paksa brahmanisme.

| subject | relation | object | source |
|---|---|---|---|
| patulangan _(SARANA_RITUAL)_ | `ADALAH` | ciri paksa brahmanisme | dependency_rule |
| patulangan _(SARANA_RITUAL)_ | `BERBENTUK` | macan | dependency_rule |
| patulangan _(SARANA_RITUAL)_ | `BERBENTUK` | singa _(SARANA_RITUAL)_ | dependency_rule |
| patulangan _(SARANA_RITUAL)_ | `BERBENTUK` | gadarba | dependency_rule |
| gadarba | `ADALAH` | beruang | object_decomposition |
| patulangan _(SARANA_RITUAL)_ | `BERBENTUK` | binatang buas lainnya | dependency_rule |

## S2087

> naga banda hanya digunakan dalam upacara palebon (ngaben) dari keluarga tertentu saja.

| subject | relation | object | source |
|---|---|---|---|
| naga banda _(SARANA_RITUAL)_ | `DITUJUKAN_UNTUK` | keluarga tertentu saja | manual_addition |
| naga banda _(SARANA_RITUAL)_ | `DIGUNAKAN_DALAM` | upacara palebon (ngaben) _(RITUAL_KEMATIAN)_ | manual_addition |

## S2093

> yakni mendiang yang diaben semasa hidupnya mempunyai ikatan erat dengan masyarakat, mempunyai pertalian yang intim dengan soal duniawiah material.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMILIKI` | ikatan erat dengan masyarakat | manual_addition |
| mendiang | `MEMILIKI` | pertalian intim dengan soal duniawi material | manual_addition |

## S2115

> kelompok ini, karena swadharma kemasyarakatannya itu, dinamai paksa mahayana (kendaraan besar), kerana bertugas "memuat" ("mengangkut") masyarakat manusia ke alam sana.

| subject | relation | object | source |
|---|---|---|---|
| kelompok (paksa mahayana) | `BERTUGAS_MENGANGKUT` | masyarakat manusia ke alam sana | manual_addition |
| kelompok ini | `ADALAH` | paksa mahayana (kendaraan besar) | manual_addition |

## S2117

> berdasarkan pengertian inilah, seorang peranda buddha dinilai wajar memakai naga banda pada palebonnya.

| subject | relation | object | source |
|---|---|---|---|
| peranda buddha _(ENTITAS_KEAGAMAAN)_ | `MEMAKAI` | naga banda (pada palebonnya) _(SARANA_RITUAL)_ | manual_addition |

## S2124

> swadharma beliau untuk mamari-suddha (menyucikan) dunia ini, merupakan fungsi pokok beliau.

| subject | relation | object | source |
|---|---|---|---|
| swadharma _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | fungsi pokok | dependency_rule |
| swadharma _(KONSEP_HUKUM_ADAT)_ | `BERTUJUAN_UNTUK` | mamari-suddha ( menyucikan ) dunia ini | dependency_rule |

## S2130

> peranda shiwa menempatkan "diri" atau jenananya pada daya suci hyang widhi itu, mula-mula di atas alias di "luar" alam duniawi, lalu turun meresapi alam ini.

| subject | relation | object | source |
|---|---|---|---|
| peranda shiwa _(ENTITAS_KEAGAMAAN)_ | `TURUN_MERESAPI` | alam ini | manual_addition |
| peranda shiwa _(ENTITAS_KEAGAMAAN)_ | `MENEMPATKAN` | diri/jenana pada daya suci hyang widhi | manual_addition |
| peranda shiwa _(ENTITAS_KEAGAMAAN)_ | `MENEMPATKAN_DIRI_DI` | luar alam duniawi (mula-mula di atas) | manual_addition |

## S2133

> oleh karena peranda buddha erat kaitannya dengan alam ini, maka digunakanlah naga banda pada saat palebon.

| subject | relation | object | source |
|---|---|---|---|
| naga banda _(SARANA_RITUAL)_ | `DIGUNAKAN_SAAT` | palebon | manual_addition |

## S2163

> jadi, naga banda itu memiliki arti dan makna yang bermacam-macam.

| subject | relation | object | source |
|---|---|---|---|
| naga banda _(SARANA_RITUAL)_ | `MEMILIKI` | makna yang bermacam-macam | dependency_rule |

## S2166

> menjelang dan sampai dengan hari pabersihan, naga banda diletakkan berdampingan dengan jenazah mendiang pada ruang bale semanggen.

| subject | relation | object | source |
|---|---|---|---|
| naga banda _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | ruang bale semanggen _(BANGUNAN_RITUAL)_ | dependency_rule |
| naga banda _(SARANA_RITUAL)_ | `BERDAMPINGAN_DENGAN` | jenazah mendiang _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S2180

> bale salunglung berwujud sebuah rumah kecil sederhana.

| subject | relation | object | source |
|---|---|---|---|
| bale salunglung _(BANGUNAN_RITUAL)_ | `BERWUJUD` | rumah kecil sederhana | dependency_rule |

## S2183

> bale salunglung dibuat di rumah atau di bale banjar.

| subject | relation | object | source |
|---|---|---|---|
| bale salunglung _(BANGUNAN_RITUAL)_ | `DIBUAT_DI` | rumah | dependency_rule |
| bale salunglung _(BANGUNAN_RITUAL)_ | `DIBUAT_DI` | bale banjar _(BANGUNAN_RITUAL)_ | dependency_rule |

## S2184

> tetapi pada hari pangabenan (sebelum pengangkutan jenazah) bale salunglung dibawa ke tempat pembakaran lebih dulu dan diletakkan sekitar empat atau lima meter di arah hulu dari tempat pembakaran jenazah.

| subject | relation | object | source |
|---|---|---|---|
| bale salunglung _(BANGUNAN_RITUAL)_ | `DIBAWA_KE` | tempat pembakaran | dependency_rule |
| bale salunglung _(BANGUNAN_RITUAL)_ | `DILETAKKAN_DI` | sekitar empat atau lima meter di arah hulu dari tempat pembakaran jenazah | manual_edit |

## S2198

> kiranya tidak terlalu salah bila dinyatakan, bahwa bale salunglung adalah bagaikan pitraloka, tempat pitra mendiang yang diaben, atau wilayah "kantongnya segala sesuatu yang didetasering di dunia ini."

| subject | relation | object | source |
|---|---|---|---|
| bale salunglung _(BANGUNAN_RITUAL)_ | `ADALAH` | bagaikan pitraloka _(KONSEP_FILOSOFIS)_ | dependency_rule |
| bale salunglung _(BANGUNAN_RITUAL)_ | `ADALAH` | tempat pitra mendiang yang diaben | dependency_rule |
| bale salunglung _(BANGUNAN_RITUAL)_ | `ADALAH` | wilayah | dependency_rule |
| wilayah | `ADALAH` | kantongnya segala sesuatu yang didetasering di dunia ini | manual_edit |

## S2212

> kalau bale salunglung merupakan simbol pitraloka (untuk tempat badan halusnya mendiang), maka bale pamuunan merupakan sebaliknya, yakni bhuta-loka alias dunianya materi, tempat unsur jenazah bersangkutan.

| subject | relation | object | source |
|---|---|---|---|
| bale salunglung _(BANGUNAN_RITUAL)_ | `ADALAH` | simbol pitraloka ( untuk tempat badan halus nya mendiang ) | dependency_rule |
| bale pamuunan _(BANGUNAN_RITUAL)_ | `ADALAH` | bhuta-loka alias dunia materi _(ENTITAS_KEAGAMAAN)_ | dependency_rule |
| bale pamuunan _(BANGUNAN_RITUAL)_ | `ADALAH` | tempat unsur jenazah bersangkutan _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |

## S2224

> ngangkid galih yang dilakukan sehari menjelang pangabenan ini hampir hanya merupakan kegiatan kerja semata.

| subject | relation | object | source |
|---|---|---|---|
| ngangkid galih _(TAHAPAN_UPACARA)_ | `ADALAH` | kegiatan kerja semata | dependency_rule |

## S2234

> tetapi, sering terjadi bahwa jenazah seseorang (yang telah tertanam-titip) pada sebuah setra, diaben di setra lain.

| subject | relation | object | source |
|---|---|---|---|
| jenazah seseorang | `TERTANAM_TITIP_DI` | sebuah setra _(BANGUNAN_RITUAL)_ | manual_addition |
| jenazah seseorang (yang telah tertanam-titip) _(ISTILAH_UMUM_RITUAL)_ | `DIABEN_DI` | setra lain _(BANGUNAN_RITUAL)_ | manual_addition |

## S2252

> besar kemungkinan bahwa mendiang yang diaben mempunyai banyak keponakan, cucu-cucu dan sebagainya yang merupakan keluarga sampingan (bukan keluarga satu sidikara/saling sembah).

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMILIKI` | keponakan | dependency_rule |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMILIKI` | cucu-cucu | dependency_rule |
| mendiang (keponakan, cucu-cucu) | `TERGOLONG` | keluarga sampingan (bukan keluarga satu sidikara/saling sembah) | manual_addition |

## S2256

> pamerasan adalah sejumlah uang kepeng yang dibungkus dengan daun "dapdap", diikat benang tridatu.

| subject | relation | object | source |
|---|---|---|---|
| pamerasan _(TAHAPAN_UPACARA)_ | `ADALAH` | sejumlah uang kepeng _(SARANA_RITUAL)_ | manual_edit |
| uang kepeng | `DIIKAT_DENGAN` | benang tridatu | manual_addition |
| uang kepeng | `DIBUNGKUS_DENGAN` | daun dapdap _(SARANA_RITUAL)_ | manual_addition |

## S2258

> pamerasan merupakan sarana pemberitahuan akan adanya pangabenan untuk mendiang, serta selaku tanda, bahwa keluarga mendiang tidak lupa akan adanya ikatan keluarga.

| subject | relation | object | source |
|---|---|---|---|
| pamerasan | `ADALAH` | sarana pemberitahuan akan adanya pangabenan untuk mendiang | manual_addition |
| pamerasan | `ADALAH` | tanda bahwa keluarga mendiang tidak lupa akan ikatan keluarga | manual_addition |

## S2262

> oleh sang cucu, biasa pula tirtha itu dimohon pada pendeta yang muput pangabenan itu sendiri.

| subject | relation | object | source |
|---|---|---|---|
| sang cucu | `MEMOHON` | tirtha _(TIRTHA_SUCI)_ | manual_addition |
| tirtha | `DIMOHON_KEPADA` | pendeta yang muput pangabenan itu sendiri | manual_addition |

## S2265

> nyikut karang adalah upacara yang sangat sederhana.

| subject | relation | object | source |
|---|---|---|---|
| nyikut karang _(TAHAPAN_UPACARA)_ | `ADALAH` | upacara yang sangat sederhana | dependency_rule |

## S2269

> bale pamuun dan sejumlah alat-alat upakara lainnya, sebenarnya telah selesai secara de facto.

| subject | relation | object | source |
|---|---|---|---|
| bale pamuun (dan alat-alat upakara lainnya) | `TELAH_SELESAI_SECARA` | de facto | manual_addition |

## S2316

> begitu pula sang undagi (pembuat bade) dengan bade atau wadah dan lembunya pun terlibat pula pada suatu acara khusus.

| subject | relation | object | source |
|---|---|---|---|
| undagi _(STRUKTUR_SOSIAL_ADAT)_ | `TERLIBAT_DI` | acara khusus | dependency_rule |

## S2323

> hanya setelah diplaspas-lah, bade dan lembu (termasuk segala alat penting lainnya) merupakan sarana yang benar-benar berkeadaan "siap pakai" betapa mestinya.

| subject | relation | object | source |
|---|---|---|---|
| bade dan lembu | `TERGOLONG_BERSAMA` | alat penting lainnya | manual_addition |
| bade dan lembu | `MENJADI` | sarana yang benar-benar "siap pakai" (hanya setelah diplaspas) _(SARANA_RITUAL)_ | manual_addition |

## S2336

> kajang yang hanya beberapa asta panjangnya, diberilah sambungan ("lancingan") kain putih dua atau 30 meter lagi, hingga puluhan anggota keluarga dapat berbaris menjunjungnya keluar dari rumah menuju tempat bade, selaku tanda hormat baktinya kepada mendiang.

| subject | relation | object | source |
|---|---|---|---|
| kajang _(SARANA_RITUAL)_ | `DIBERI` | sambungan | dependency_rule |
| sambungan | `ADALAH` | lancingan _(SARANA_RITUAL)_ | object_decomposition |
| kajang _(SARANA_RITUAL)_ | `DIBERI` | kain putih _(SARANA_RITUAL)_ | dependency_rule |
| kajang _(SARANA_RITUAL)_ | `MELAMBANGKAN` | tanda hormat bakti kepada mendiang _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| sambungan kain putih _(SARANA_RITUAL)_ | `SEPANJANG` | dua atau 30 meter | manual_addition |

## S2337

> setelah jenazah/pengawak terletak rapi di balai-balai bade, kajang pun dinaikkan serta dilipat-lipat/ditindihkan pada jenazah atau simbolnya itu.

| subject | relation | object | source |
|---|---|---|---|
| jenazah /pengawak _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | balai-balai bade _(SARANA_RITUAL)_ | dependency_rule |
| kajang _(SARANA_RITUAL)_ | `DILIPAT_DI` | jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| kajang _(SARANA_RITUAL)_ | `DILIPAT_DI` | simbol | manual_edit |

## S2340

> adegan dan sebagainya ini sering dijadikan unsur arak-arakan indah oleh pemudi-pemudi keluarga bersangkutan.

| subject | relation | object | source |
|---|---|---|---|
| adegan | `DIJADIKAN` | unsur arak-arakan indah (oleh pemudi-pemudi keluarga bersangkutan) | manual_addition |

## S2363

> bale pamuunan yang telah dihuni lembu, dikelilingi pula sebanyak tiga kali oleh bade dengan jenazahnya.

| subject | relation | object | source |
|---|---|---|---|
| bale pamuunan | `DIKELILINGI_OLEH` | bade dengan jenazahnya (sebanyak tiga kali) | manual_addition |
| bale pamuunan _(BANGUNAN_RITUAL)_ | `DIHUNI` | lembu _(SARANA_RITUAL)_ | manual_addition |

## S2364

> setelah itulah baru bade diletakkan di sebelah hilir atau teben sang lembu.

| subject | relation | object | source |
|---|---|---|---|
| bade _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | sebelah hilir atau teben lembu | manual_addition |

## S2370

> pradaksina melambangkan turunnya purusa guna meresapi pradana, turunnya immaterial meresapi material, hingga material memperoleh imbas kesucian dari yang immaterial.

| subject | relation | object | source |
|---|---|---|---|
| pradaksina | `MELAMBANGKAN` | turunnya purusa meresapi pradana (material memperoleh imbas kesucian dari yang immaterial) | manual_addition |

## S2374

> prasawya adalah lambang gerak peningkatan diri dari sesuatu, atau gerak ke atas.

| subject | relation | object | source |
|---|---|---|---|
| prasawya _(TAHAPAN_UPACARA)_ | `ADALAH` | lambang gerak peningkatan diri dari sesuatu, atau gerak ke atas | manual_edit |

## S2377

> ngaben mempunyai tujuan pokok untuk merubah jenazah atau "benda bekas" badan seseorang, hingga kembali menjadi pancamahabutha sebagaimana asalnya semula.

| subject | relation | object | source |
|---|---|---|---|
| ngaben _(RITUAL_KEMATIAN)_ | `BERTUJUAN_POKOK` | merubah jenazah atau benda bekas badan seseorang kembali menjadi pancamahabutha seperti asalnya semula | manual_addition |

## S2380

> tentunya mudah dibayangkan bahwa bade seyogyanya berputar dengan cara prasawya (berputar ke kiri, berlawanan dengan putaran jarum jam), serta berlawanan pula dengan gerak pradaksina yang dilakukan pada upacara dewa yadnya di pura.

| subject | relation | object | source |
|---|---|---|---|
| bade _(SARANA_RITUAL)_ | `BERPUTAR_DENGAN` | cara prasawya _(TAHAPAN_UPACARA)_ | dependency_rule |
| cara prasawya | `ADALAH` | berputar ke kiri, berlawanan dengan putaran jarum jam | manual_edit |
| bade _(SARANA_RITUAL)_ | `BERLAWANAN_DENGAN` | gerak pradaksina yang dilakukan pada upacara dewa yadnya di pura | manual_addition |

## S2387

> setelah berkeliling sekitar bale pamuunan yang dihuni lembu, maka bade dengan sawa di atasnya itu diletakkan di sebelah hilir lembu.

| subject | relation | object | source |
|---|---|---|---|
| bade | `DILETAKKAN_DI` | sebelah hilir lembu | manual_addition |

## S2406

> kini, jenazah atau simboliknya menjadi sasaran segala kegiatan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah atau simbolik | `MENJADI` | sasaran segala kegiatan | manual_addition |

## S2419

> adegan, angenan, pisang jati, panguryagan dan lain-lain alat yang harus dibakar, semua dihaturkan kepada hyang agni (api) tanpa sisa.

| subject | relation | object | source |
|---|---|---|---|
| hyang agni | `ADALAH` | api | object_decomposition |
| adegan, angenan, pisang jati, panguryagan, dan lain-lain alat yang harus dibakar | `DIPERSEMBAHKAN_KEPADA` | hyang agni (api), tanpa sisa _(KONSEP_FILOSOFIS)_ | manual_addition |

## S2448

> suku tunggal yang telah dinilai selaku "pribadi" mendiang, dipangku dan diajak menghaturkan sembah bakti pamitan (dilakukan dari tempat itu saja) kepada semua bhatara-bhatari yang "bersemayam" di semua pura dan pamrajan panyiwiannya.

| subject | relation | object | source |
|---|---|---|---|
| bhatara-bhatari | `BERSEMAYAM_DI` | pura dan pamrajan panyiwiannya _(BANGUNAN_RITUAL)_ | manual_addition |
| suku tunggal | `MENGHATURKAN` | sembah bakti pamitan kepada bhatara-bhatari _(ENTITAS_KEAGAMAAN)_ | manual_addition |

## S2449

> selanjutnya suku tunggal itu diarak dan dihanyut ke laut.

| subject | relation | object | source |
|---|---|---|---|
| suku tunggal _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | laut | dependency_rule |

## S2455

> dari semua uraian terdahulu, maka jelaslah bahwa pangabenan terdiri dari berbagai jenis, masing-masing mempunyai nama sendiri-sendiri.

| subject | relation | object | source |
|---|---|---|---|
| pangabenan _(RITUAL_KEMATIAN)_ | `TERDIRI_DARI` | berbagai jenis | manual_edit |
| pangabenan jenis (masing-masing) | `MEMILIKI` | nama sendiri-sendiri | manual_addition |

## S2472

> "pranawa" juga berarti lambang suara "om".

| subject | relation | object | source |
|---|---|---|---|
| pranawa _(RITUAL_KEMATIAN)_ | `BERARTI` | lambang suara "om" | manual_edit |

## S2473

> dengan demikian, pangabenan yang menggunakan nama pranawa dilatarbelakangi oleh hasrat supaya mendiang (baik jenazah ataupun atmanya) dapat memperoleh ketenangan, kemantapan serta kesucian, seimbang dengan makna istilah itu sendiri.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | ketenangan | dependency_rule |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | kemantapan | dependency_rule |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | kesucian | dependency_rule |
| pangabenan yang menggunakan nama pranawa | `DILATARBELAKANGI_OLEH` | hasrat supaya mendiang memperoleh ketenangan, kemantapan, serta kesucian | manual_addition |

## S2480

> supta pranawa masih tergolong pangabenan jenis pranawa, namun telah mengalami variasi alakadarnya.

| subject | relation | object | source |
|---|---|---|---|
| supta pranawa _(RITUAL_KEMATIAN)_ | `BAGIAN_DARI` | pangabenan jenis pranawa _(RITUAL_KEMATIAN)_ | dependency_rule |
| supta pranawa _(RITUAL_KEMATIAN)_ | `MENGALAMI` | variasi alakadar | dependency_rule |

## S2483

> dengan demikian, "supta pranawa" adalah satu pangabenan yang berlandaskan hasrat, semoga mendiang mendapatkan situasi demikian di alam lain.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | situasi demikian di alam lain | manual_edit |
| supta pranawa _(RITUAL_KEMATIAN)_ | `ADALAH` | satu pangabenan yang berlandaskan hasrat, semoga mendiang mendapatkan situasi demikian di alam lain | manual_edit |

## S2485

> pangabenan pranawa, hanya digunakan bagi mendiang yang telah tak ada sawanya lagi.

| subject | relation | object | source |
|---|---|---|---|
| pangabenan pranawa _(RITUAL_KEMATIAN)_ | `DITUJUKAN_UNTUK` | mendiang yang telah tak ada sawanya lagi | manual_edit |

## S2489

> atma wedana boleh dikatakan pitra yadnya tahap kedua.

| subject | relation | object | source |
|---|---|---|---|
| atma wedana _(RITUAL_KEMATIAN)_ | `DIKATAKAN` | pitra yadnya tahap kedua _(RITUAL)_ | dependency_rule |

## S2502

> sawa wedana digelar dengan tujuan menyucikan (wedana) roh, arwah atau badan halus mendiang, supaya menjadi atma yang tanpa badan sama sekali.

| subject | relation | object | source |
|---|---|---|---|
| badan halus mendiang (roh/arwah) | `MENJADI` | atma yang tanpa badan sama sekali | manual_addition |
| sawa wedana | `BERTUJUAN_MENYUCIKAN` | arwah | manual_addition |
| sawa wedana | `BERTUJUAN_MENYUCIKAN` | badan halus mendiang _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| sawa wedana | `BERTUJUAN_MENYUCIKAN` | roh | manual_addition |

## S2520

> di samping itu perlu diketengahkan, bahwa berbeda dengan ngaben, atma wedana merupakan yadnya yang tidak bersifat sebel.

| subject | relation | object | source |
|---|---|---|---|
| atma wedana _(RITUAL_KEMATIAN)_ | `ADALAH` | yadnya yang tidak bersifat sebel | dependency_rule |
| atma wedana | `BERBEDA_DENGAN` | ngaben (dalam hal sifat sebel) _(RITUAL_KEMATIAN)_ | manual_addition |

## S2527

> pura, pamrajan, atau kahyangan jenis apapun, di mata hati umat hindu merupakan dewaloka atau alam kedewaan.

| subject | relation | object | source |
|---|---|---|---|
| pura, pamrajan, atau kahyangan jenis apapun | `ADALAH` | alam kedewaan | manual_addition |
| pura, pamrajan, atau kahyangan jenis apapun | `ADALAH` | dewaloka _(KONSEP_FILOSOFIS)_ | manual_addition |

## S2535

> dengan melakukan upacara atma wedana, sang pitara mengelupasi suksmasarira yang merupakan "kulit dirinya", sebagaimana halnya seekor udang yang tengah menylongsong.

| subject | relation | object | source |
|---|---|---|---|
| pitara _(ENTITAS_KEAGAMAAN)_ | `MENGELUPASI` | suksmasarira (yang merupakan "kulit dirinya") _(KONSEP_FILOSOFIS)_ | manual_edit |

## S2542

> sebagaimana halnya pangabenan, atma wedana pun ada beberapa jenis, masing-masing punya nama dan ciri-ciri tersendiri.

| subject | relation | object | source |
|---|---|---|---|
| atma wedana _(RITUAL_KEMATIAN)_ | `MEMILIKI` | beberapa jenis | manual_edit |
| jenis atma wedana (masing-masing) | `MEMILIKI` | nama dan ciri-ciri tersendiri | manual_addition |

## S2548

> tirtha pangentas atiwa-tiwa hanya boleh disiratkan sekali saja kepada sesosok mayat atau perlambangnya.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas atiwa-tiwa _(TIRTHA_SUCI)_ | `DIPERCIKKAN_PADA` | perlambang (hanya sekali saja) | manual_addition |
| tirtha pangentas atiwa-tiwa _(TIRTHA_SUCI)_ | `DIPERCIKKAN_PADA` | sesosok mayat (hanya sekali saja) | manual_addition |

## S2555

> atma wedana adalah nama resmi upacara penyucian pitra menurut pustaka yang kita warisi.

| subject | relation | object | source |
|---|---|---|---|
| atma wedana _(RITUAL_KEMATIAN)_ | `ADALAH` | nama resmi upacara penyucian pitra _(KONSEP_FILOSOFIS)_ | manual_edit |

## S2558

> ngroras, menurut aksaranya, berasal dari kata "roras" (bilangan 12).

| subject | relation | object | source |
|---|---|---|---|
| ngroras _(RITUAL_KEMATIAN)_ | `BERASAL_DARI` | kata roras | dependency_rule |
| kata roras | `ADALAH` | bilangan 12 | object_decomposition |

## S2563

> ingatlah, bhuwana alit hanya mempunyai 11 bidang yang mudah ditimpa suasana "sebel".

| subject | relation | object | source |
|---|---|---|---|
| bhuwana alit _(KONSEP_FILOSOFIS)_ | `MEMILIKI` | 11 bidang yang mudah ditimpa suasana "sebel" | manual_edit |

## S2566

> demikian juga bhuwana agung, masing-masing arah yang berjumlah 11 itu menerima cuntaka selama sehari.

| subject | relation | object | source |
|---|---|---|---|
| bhuwana agung (masing-masing arah yang berjumlah 11) | `MEMPEROLEH` | cuntaka selama sehari _(KONSEP_HUKUM_ADAT)_ | manual_addition |

## S2571

> begitu pula sang arjuna menghukum dirinya, ataupun "menghutannya" sang rama beserta laksmana, masing-masing selama 12 tahun juga.

| subject | relation | object | source |
|---|---|---|---|
| arjuna _(ENTITAS_KEAGAMAAN)_ | `MENGHUKUM` | diri | dependency_rule |

## S2604

> kedua, ngangsen adalah upacara penyucian sementara bagi sang pitra yang barusan lepas pertalian dengan stulasariranya, supaya suksmasariranya tidak masih dilekati bekas-bekas badan kasar sama sekali.

| subject | relation | object | source |
|---|---|---|---|
| ngangsen | `BERTUJUAN` | agar suksmasarira pitra tidak lagi dilekati bekas-bekas badan kasar | manual_addition |
| ngangsen | `ADALAH` | upacara penyucian sementara bagi sang pitra | manual_addition |
| pitra (dalam ngangsen) | `BARU_LEPAS_PERTALIAN_DENGAN` | stulasarira nya | manual_addition |

## S2612

> pitra mendiang, yang merupakan sasaran upacara dibuatkan perlambang yang disebut sekah kangsen.

| subject | relation | object | source |
|---|---|---|---|
| perlambang | `DIKENAL_SEBAGAI` | sekah kangsen _(SARANA_RITUAL)_ | object_decomposition |
| pitra mendiang _(KONSEP_FILOSOFIS)_ | `DIBUATKAN` | perlambang (yang disebut sekah kangsen) | manual_addition |

## S2619

> sekah kangsen menggunakan sebuah dulang atau sebuah meja pendek - kecil selaku singgasananya.

| subject | relation | object | source |
|---|---|---|---|
| sekah kangsen _(SARANA_RITUAL)_ | `MENGGUNAKAN` | dulang _(SARANA_RITUAL)_ | dependency_rule |
| sekah kangsen _(SARANA_RITUAL)_ | `MENGGUNAKAN` | meja pendek kecil | dependency_rule |

## S2620

> dulang atau meja kecil itu diletakkan di bagian hulu arena upacara.

| subject | relation | object | source |
|---|---|---|---|
| dulang atau meja kecil _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | hulu arena upacara | dependency_rule |

## S2623

> pertama-tama, sekah kangsen disucikan dengan tirtha dan sajen kecil sebagai pengantarnya.

| subject | relation | object | source |
|---|---|---|---|
| sekah kangsen _(SARANA_RITUAL)_ | `DISUCIKAN_DENGAN` | tirtha _(TIRTHA_SUCI)_ | dependency_rule |
| sekah kangsen _(SARANA_RITUAL)_ | `DISUCIKAN_DENGAN` | sajen kecil (sebagai pengantar) | manual_edit |

## S2624

> sang pitra mendiang dipersilakan masuk ke dalam sekah kangsen serta memakai wujud tersebut selaku "pralingga"-nya (perlambang diri yang dihuni).

| subject | relation | object | source |
|---|---|---|---|
| pitra mendiang | `DIPERSILAKAN_MASUK_KE` | sekah kangsen _(SARANA_RITUAL)_ | manual_addition |
| pitra mendiang | `MEMAKAI` | wujud tersebut selaku pralingga (perlambang diri yang dihuni) | manual_addition |

## S2630

> dengan upacara penyucian ini, pitra yang telah berada di sekah kangsen itu dinilai wajar menerima sembah bhakti serta ayaban sajen.

| subject | relation | object | source |
|---|---|---|---|
| pitra | `MENERIMA` | sembah bhakti serta ayaban sajen _(TAHAPAN_UPACARA)_ | manual_addition |

## S2635

> tarpana dan muspa inilah merupakan klimaks dalam upacara sederhana ini.

| subject | relation | object | source |
|---|---|---|---|
| tarpana dan muspa _(TAHAPAN_UPACARA)_ | `ADALAH` | klimaks upacara sederhana | dependency_rule |

## S2642

> setelah pamralina, sekah kangsen itupun dibongkar.

| subject | relation | object | source |
|---|---|---|---|
| sekah kangsen | `DIBONGKAR_SETELAH` | pamralina | manual_addition |

## S2644

> kemudian, abu daun tersebut yang dinilai selaku bekas-bekas stulasarira mendiang, dimasukkan ke dalam klungah nyuh gading yang dibentuk menjadi suku tunggal.

| subject | relation | object | source |
|---|---|---|---|
| abu daun (yang dinilai selaku bekas-bekas stulasarira mendiang) | `DIMASUKKAN_KE_DALAM` | klungah nyuh gading (yang dibentuk menjadi suku tunggal) | manual_addition |

## S2645

> selanjutnya, dengan melalui upacara mapepegat (perpisahan), abu dalam suku tunggal dihanyutkan ke laut atau sungai.

| subject | relation | object | source |
|---|---|---|---|
| abu suku tunggal _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | laut | dependency_rule |
| abu suku tunggal _(SARANA_RITUAL)_ | `DIHANYUTKAN_KE` | sungai | dependency_rule |

## S2649

> ngangsen adalah upacara untuk bertangguh.

| subject | relation | object | source |
|---|---|---|---|
| ngangsen _(RITUAL_KEMATIAN)_ | `ADALAH` | upacara untuk bertangguh | dependency_rule |

## S2651

> mungkin sampai lima atau sepuluh tahun kemudiannya lah baru atma wedana sesungguhnya dapat diadakan bagi mendiang.

| subject | relation | object | source |
|---|---|---|---|
| atma wedana _(RITUAL_KEMATIAN)_ | `DITUJUKAN_UNTUK` | mendiang (baru dapat diadakan setelah mungkin lima atau sepuluh tahun kemudian) | manual_edit |

## S2667

> sedangkan payadnyan adalah bangunan pokok pada arena ini.

| subject | relation | object | source |
|---|---|---|---|
| payadnyan _(BANGUNAN_RITUAL)_ | `ADALAH` | bangunan pokok pada arena ini | manual_edit |

## S2672

> dari segi ukuran, payadnyan merupakan bangunan yang paling rendah, tetapi dihias paling indah.

| subject | relation | object | source |
|---|---|---|---|
| payadnyan _(BANGUNAN_RITUAL)_ | `ADALAH` | bangunan yang paling rendah (dari segi ukuran) | manual_edit |
| payadnyan | `DIHIAS_PALING` | indah | manual_addition |

## S2686

> dalam sekah atau puspalingga inilah pitra mendiang bertahta.

| subject | relation | object | source |
|---|---|---|---|
| pitra mendiang _(KONSEP_FILOSOFIS)_ | `BERTAHTA` | sekah _(SARANA_RITUAL)_ | dependency_rule |
| pitra mendiang _(KONSEP_FILOSOFIS)_ | `BERTAHTA` | puspalingga _(SARANA_RITUAL)_ | dependency_rule |

## S2748

> di balai pawedan itu dideretkanlah semua sekah yang telah selesai diajum, dialasi dulang atau meja rendah, termasuk sekah sangge.

| subject | relation | object | source |
|---|---|---|---|
| sekah _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | balai pawedan _(BANGUNAN_RITUAL)_ | dependency_rule |
| sekah _(SARANA_RITUAL)_ | `DIALASI` | dulang _(SARANA_RITUAL)_ | dependency_rule |
| sekah _(SARANA_RITUAL)_ | `DIALASI` | meja rendah | dependency_rule |
| sekah sangge | `JENIS_DARI` | sekah _(SARANA_RITUAL)_ | dependency_rule |

## S2752

> dalam hal ini, tentu saja berarti bahwa mendiang lahir dalam wujud sekah, agar dapat "diajak berkomunikasi" oleh keluarganya.

| subject | relation | object | source |
|---|---|---|---|
| mendiang | `LAHIR_DALAM_WUJUD` | sekah _(SARANA_RITUAL)_ | manual_addition |
| mendiang (dalam wujud sekah) | `DIAJAK_BERKOMUNIKASI_OLEH` | keluarga | manual_addition |

## S2758

> mendiang mengalami perubahan wujud, dari suksma sarira menjadi tanpa berbadan sama sekali atau hanya "atma tattwatma" (atma yang mulus sama sekali).

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MENGALAMI` | perubahan wujud | dependency_rule |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `BERUBAH_DARI_SUKSMA_SARIRA_MENJADI` | tanpa berbadan sama sekali atau atma tattwatma | manual_addition |

## S2762

> walaupun mendiang telah memperoleh "upanisad" (pawisik) dari pendeta tentang jalan yang harus ditempuh, namun kemungkinan tersesat sangat besar.

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH` | upanisad _(KONSEP_FILOSOFIS)_ | dependency_rule |
| upanisad _(KONSEP_FILOSOFIS)_ | `ADALAH` | pawisik | object_decomposition |
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `MEMPEROLEH_DARI` | pendeta | manual_addition |
| upanisad | `TENTANG` | jalan yang harus ditempuh | manual_addition |

## S2768

> jadi, pada dasarnya ucapan orang tua-tua yang mengatakan bahwa sangge adalah dia "sang ngae" diri kita, sama sekali tidaklah salah.

| subject | relation | object | source |
|---|---|---|---|
| sangge _(SARANA_RITUAL)_ | `ADALAH` | "sang ngae" diri kita | manual_edit |

## S2777

> dalam hal ini bhatara yang dimohon selaku "lingga" (demikian namanya) dipendak (disongsong) secara khusus, serta dipersilakan untuk utpeti (masuk dan menghuni) pada puspalingga (sejenis sangge) selaku badan suksmanya.

| subject | relation | object | source |
|---|---|---|---|
| utpeti _(KONSEP_FILOSOFIS)_ | `ADALAH` | masuk dan menghuni | manual_edit |
| bhatara _(ENTITAS_KEAGAMAAN)_ | `DIPERSILAKAN_DI` | puspalingga _(SARANA_RITUAL)_ | dependency_rule |
| puspalingga _(SARANA_RITUAL)_ | `ADALAH` | sejenis sangge | object_decomposition |
| bhatara _(ENTITAS_KEAGAMAAN)_ | `DIPENDAK_SECARA` | khusus | manual_addition |
| bhatara _(ENTITAS_KEAGAMAAN)_ | `DIPERSILAKAN_UNTUK` | utpeti _(KONSEP_FILOSOFIS)_ | manual_addition |
| puspalingga _(SARANA_RITUAL)_ | `BERPERAN_SEBAGAI` | badan suksma bhatara _(ENTITAS_KEAGAMAAN)_ | manual_addition |

## S2780

> sanggar surya baligia mempunyai tiga buah ruang, dengan segala akibat lanjutannya.

| subject | relation | object | source |
|---|---|---|---|
| sanggar surya baligia _(BANGUNAN_RITUAL)_ | `MEMILIKI` | tiga buah ruang | manual_edit |

## S2787

> setelah pangutpetian, sekah itu dinaikkan ke atas bukur.

| subject | relation | object | source |
|---|---|---|---|
| sekah _(SARANA_RITUAL)_ | `DINAIKKAN_KE` | atas bukur _(SARANA_RITUAL)_ | dependency_rule |

## S2794

> lalu semua sekah termasuk sangge diturunkan dari pawedan.

| subject | relation | object | source |
|---|---|---|---|
| sangge | `JENIS_DARI` | sekah _(SARANA_RITUAL)_ | dependency_rule |
| sekah | `DITURUNKAN_DARI` | pawedan _(BANGUNAN_RITUAL)_ | manual_addition |

## S2803

> pawedan di samping sebagai tempat ngajum serta mengutpeti sekah, juga terutama merupakan tempat sang sulinggih dalam memuja bagi segenap upacara atma wedana ini.

| subject | relation | object | source |
|---|---|---|---|
| pawedan | `JUGA_ADALAH` | tempat ngajum serta mengutpeti sekah _(TAHAPAN_UPACARA)_ | manual_addition |
| pawedan _(BANGUNAN_RITUAL)_ | `ADALAH` | tempat sang sulinggih dalam memuja _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| tempat sang sulinggih dalam memuja | `DIPAKAI_UNTUK` | segenap upacara atma wedana ini _(RITUAL_KEMATIAN)_ | manual_addition |

## S2810

> mengingat hyang shiwa atau hyang adi buddha meresap ke dalam diri sang pendeta, maka pawedan tempatnya memuja, bukanlah sekadar bernilai "madyapada" saja, melainkan secara religius merupakan pula "shiwa (dewa) loka."

| subject | relation | object | source |
|---|---|---|---|
| shiwa _(ENTITAS_KEAGAMAAN)_ | `ADALAH` | dewa loka | object_decomposition |
| pawedan (tempat memuja) | `BUKAN_SEKADAR` | "madyapada" | manual_addition |
| pawedan (tempat memuja) | `MERUPAKAN` | shiwa (dewa) loka _(ENTITAS_KEAGAMAAN)_ | manual_addition |

## S2812

> kala itu, mendiang masih berkedudukan sebagai pitra (atma yang masih bersuksmasarira).

| subject | relation | object | source |
|---|---|---|---|
| mendiang _(ISTILAH_UMUM_RITUAL)_ | `BERPERAN_SEBAGAI` | pitra _(KONSEP_FILOSOFIS)_ | dependency_rule |
| pitra _(KONSEP_FILOSOFIS)_ | `ADALAH` | atma yang masih bersuksmasarira _(KONSEP_FILOSOFIS)_ | manual_edit |

## S2819

> payadnyan adalah sekadar bangunan darurat buatan manusia di mercapada ini.

| subject | relation | object | source |
|---|---|---|---|
| payadnyan _(BANGUNAN_RITUAL)_ | `ADALAH` | sekadar bangunan darurat buatan manusia di mercapada ini | manual_edit |

## S2824

> lalu, mengapa sekah dimasukkan melalui pintu belakang tatkala akan mengambil tempat pada payadnyannya itu?

| subject | relation | object | source |
|---|---|---|---|
| sekah | `DIMASUKKAN_MELALUI` | pintu belakang | manual_addition |

## S2832

> bukankah kalau masuk melalui jalan depan, dalam beberapa saat sang sekah membelakangi sang pendeta yang ada di pawedannya?

| subject | relation | object | source |
|---|---|---|---|
| sekah _(SARANA_RITUAL)_ | `MEMBELAKANGI` | pendeta | dependency_rule |

## S2843

> sementara itu sang sulinggih, tukang banten dan tamu terhormat dan tamu khusus lainnya, dihaturkan santapan istimewa.

| subject | relation | object | source |
|---|---|---|---|
| santapan istimewa | `DIPERSEMBAHKAN_KEPADA` | sulinggih, tukang banten, tamu terhormat, dan tamu khusus lainnya | dependency_rule |

## S2850

> pada patileman, punia ini merupakan syarat mutlak, walaupun besar-kecilnya sangat relatif, sepadan dengan jenis yadnya dan martabat sang mayadnya itu sendiri.

| subject | relation | object | source |
|---|---|---|---|
| punia _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | syarat mutlak | dependency_rule |
| punia (besar-kecilnya) | `SEPADAN_DENGAN` | jenis yadnya dan martabat sang mayadnya | manual_addition |

## S2854

> umumnya orang sangat yakin bahwa pitra mendiang yang tengah duduk pada puspalingganya masing-masing di payadnyan, tentu sangat bersuka cita dan terharu menyaksikan anak cucunya melakukan upacara manusa yadnya tersebut.

| subject | relation | object | source |
|---|---|---|---|
| pitra mendiang _(KONSEP_FILOSOFIS)_ | `BERSUKA` | cita | dependency_rule |
| pitra mendiang _(KONSEP_FILOSOFIS)_ | `MENYAKSIKAN` | anak cucunya melakukan upacara manusa yadnya tersebut | manual_edit |

## S2869

> sang pitara menggunakan tirtha ening selaku cermin-nya (tarpana = bercermin) hingga tampaklah bayangannya.

| subject | relation | object | source |
|---|---|---|---|
| pitara _(ENTITAS_KEAGAMAAN)_ | `MENGGUNAKAN` | tirtha ening _(TIRTHA_SUCI)_ | dependency_rule |
| pitara (menggunakan tirtha ening) | `HINGGA_TAMPAK` | bayangan nya | manual_addition |

## S2872

> demikianlah, manah tirtha ening ini dapat merupakan suatu pawai yang bernilai seni, lebih-lebih yang untuk pamukuran.

| subject | relation | object | source |
|---|---|---|---|
| manah tirtha ening _(KONSEP_FILOSOFIS)_ | `ADALAH` | pawai yang bernilai seni, lebih-lebih yang untuk pamukuran | manual_edit |

## S2885

> perlu pula dicatat, bahwa pada ngroras yang diiringi dengan potong gigi dan acara lainnya, maka setelah saji tarpana (hari pertama) dilaksanakan, sang sulinggih memberikan panjaya-jaya serta memberikan ayaban sesayut kepada putra-putri yang berupacara.

| subject | relation | object | source |
|---|---|---|---|
| sulinggih _(ENTITAS_KEAGAMAAN)_ | `MEMBERIKAN` | panjaya-jaya | dependency_rule |
| sulinggih _(ENTITAS_KEAGAMAAN)_ | `MEMBERIKAN` | ayaban sesayut _(SARANA_RITUAL)_ | dependency_rule |

## S2894

> dari segi kemeriahan, pralina kalah dengan upacara saji tarpana.

| subject | relation | object | source |
|---|---|---|---|
| pralina | `KALAH_MERIAH_DIBANDING` | upacara saji tarpana _(TAHAPAN_UPACARA)_ | manual_addition |

## S2904

> pralina adalah suatu istilah yang telah cukup memasyarakat.

| subject | relation | object | source |
|---|---|---|---|
| pralina _(TAHAPAN_UPACARA)_ | `ADALAH` | istilah yang telah cukup memasyarakat | dependency_rule |

## S2914

> suksma sarira, walaupun sangat halus, adalah materi juga adanya.

| subject | relation | object | source |
|---|---|---|---|
| suksma sarira _(KONSEP_FILOSOFIS)_ | `ADALAH` | materi (walaupun sangat halus) | manual_edit |

## S2923

> itulah sebabnya, mamukur dan upacara sebangsanya dilindungi dengan upaya penyucian wilayah yang ketat dengan berbagai pantangannya.

| subject | relation | object | source |
|---|---|---|---|
| mamukur dan upacara sebangsa _(RITUAL_KEMATIAN)_ | `DILINDUNGI_DENGAN` | upaya penyucian wilayah yang ketat dengan berbagai pantangannya | manual_edit |

## S2947

> kemudian abu itu diuyeg (digiling) selumat-lumatnya di atas sesenden (dulang tanah).

| subject | relation | object | source |
|---|---|---|---|
| sesenden _(SARANA_RITUAL)_ | `ADALAH` | dulang tanah | object_decomposition |
| abu _(SARANA_RITUAL)_ | `DIGILING_DI_ATAS` | sesenden _(SARANA_RITUAL)_ | manual_addition |

## S2948

> abu yang sudah lumat itu lalu dimasukkan ke klungah nyuh gading yang "disukutunggalkan".

| subject | relation | object | source |
|---|---|---|---|
| abu (yang sudah lumat) _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | klungah nyuh gading yang disukutunggalkan _(SARANA_RITUAL)_ | manual_addition |

## S2951

> berikutnya suku tunggal abu itu diarak mapradaksina, selaku lambang diresapkannya sinar suci hyang widhi, hingga meningkatlah status dan kesucian abu tersebut, dari bekas benda badan linggasarira, menjadi mahabutha yang suci.

| subject | relation | object | source |
|---|---|---|---|
| suku tunggal abu _(SARANA_RITUAL)_ | `DIUSUNG` | mapradaksina _(TAHAPAN_UPACARA)_ | dependency_rule |
| abu | `BERUBAH_DARI` | bekas benda badan linggasarira | manual_addition |
| abu | `MENJADI` | mahabutha yang suci | manual_addition |
| suku tunggal abu (diarak mapradaksina) | `MELAMBANGKAN` | diresapkannya sinar suci hyang widhi _(KONSEP_FILOSOFIS)_ | manual_addition |

## S2954

> lihatlah, atma sang pitara dimohonkan agar dapat meningkat ke dewaloka.

| subject | relation | object | source |
|---|---|---|---|
| atma pitara | `DIMOHONKAN_AGAR_MENUJU` | dewaloka _(KONSEP_FILOSOFIS)_ | manual_addition |

## S2968

> bila ditelusuri istilahnya maka ngajar-ajar berarti ajar-ajaran atau tuntunan.

| subject | relation | object | source |
|---|---|---|---|
| ngajar-ajar _(TAHAPAN_UPACARA)_ | `BERARTI` | ajar-ajaran | dependency_rule |
| ngajar-ajar _(TAHAPAN_UPACARA)_ | `BERARTI` | tuntunan | dependency_rule |

## S2969

> lebih-lebih jika mengingat siapa-siapa selaku sasaran utama yang dihaturi pelbagai sajen pada pelaksanaan upacara, maka tidaklah salah bila disimpulkan bahwa ngajar-ajar bermakna upacara pernyataan parama suksmaning idep alias ucapan terima kasih dari pihak sang mayadnya kepada para penuntun (para ajar) yang telah memberikan jasa-jasanya masing-masing, hingga yadnya dapat diselesaikan dengan tuntas sebagaimana mestinya.

| subject | relation | object | source |
|---|---|---|---|
| ngajar-ajar _(TAHAPAN_UPACARA)_ | `BERMAKNA` | upacara pernyataan parama suksmaning idep | dependency_rule |
| ngajar-ajar _(TAHAPAN_UPACARA)_ | `BERMAKNA` | ucapan terima kasih dari pihak sang mayadnya kepada para penuntun (para ajar) | manual_addition |

## S2977

> kedua pura itu telah dinilai layak untuk tempat pemujaan terhadap tuhan penguasa laut dan gunung.

| subject | relation | object | source |
|---|---|---|---|
| kedua pura _(BANGUNAN_RITUAL)_ | `DITUJUKAN_UNTUK` | tempat pemujaan terhadap tuhan penguasa laut dan gunung | dependency_rule |

## S2986

> berapapun banyaknya pitra yang diupacarai patileman sepanjang mereka masih tergolong sekeluarga tunggalan pamrajan, baginya hanya dibuat maksimal dua buah daksina tapakan saja, masing-masing untuk bhatara dan bhatari.

| subject | relation | object | source |
|---|---|---|---|
| pitra _(KONSEP_FILOSOFIS)_ | `BAGIAN_DARI` | sekeluarga tunggalan pamrajan _(BANGUNAN_RITUAL)_ | dependency_rule |
| daksina tapakan _(SARANA_RITUAL)_ | `DITUJUKAN_UNTUK` | bhatara _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| daksina tapakan _(SARANA_RITUAL)_ | `DITUJUKAN_UNTUK` | bhatari _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| pitra _(KONSEP_FILOSOFIS)_ | `MENERIMA` | dua buah daksina tapakan (dibuat untuknya) _(SARANA_RITUAL)_ | manual_addition |

## S2988

> bukankah sejak selesainya patileman sang pitra telah meningkat kedudukannya menjadi bhatara atau bhatari?

| subject | relation | object | source |
|---|---|---|---|
| pitra | `MENINGKAT_KEDUDUKAN_MENJADI` | bhatara atau bhatari (sejak selesainya patileman) | manual_addition |

## S3001

> punia ini adalah perwujudan nyata lahirlah dari pernyataan parama suksma lahir batin (purusa-pradana), atas jasa tuntunan yang telah dianugrahkan oleh beliau, hingga patileman dapat selesai secara tuntas.

| subject | relation | object | source |
|---|---|---|---|
| punia _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | perwujudan nyata dari pernyataan parama suksma lahir batin (purusa-pradana) | manual_edit |
| patileman | `DAPAT_SELESAI_SECARA` | tuntas (berkat punia) _(KONSEP_HUKUM_ADAT)_ | manual_addition |
| punia | `LAHIR_ATAS` | jasa tuntunan yang telah dianugrahkan oleh beliau | manual_addition |

## S3004

> tetapi yang penting adalah bahwa punia itu hendaklah merupakan perwujudan dari sredaning cita, yakni wujud dari ketulus-ikhlasan hati pihak yang bersangkutan.

| subject | relation | object | source |
|---|---|---|---|
| punia _(KONSEP_HUKUM_ADAT)_ | `ADALAH` | perwujudan sredaning cita | dependency_rule |
| perwujudan sredaning cita | `ADALAH` | wujud ketulus-ikhlasan hati pihak yang bersangkutan | manual_edit |

## S3007

> sang pandita selaku pemuka agama, sudah sangat memaklumi ketentuan punia yang demikian itu.

| subject | relation | object | source |
|---|---|---|---|
| pandita _(ENTITAS_KEAGAMAAN)_ | `BERPERAN_SEBAGAI` | pemuka agama | dependency_rule |
| pandita (selaku pemuka agama) | `MEMAKLUMI` | ketentuan punia yang demikian itu | manual_addition |

## S3063

> bagi yang meninggal di rumah, maka jenazah perlu dibersihkan, baik dari kotoran-kotoran yang telah lama berada pada badan orang yang meninggal maupun dari hal-hal yang lain.

| subject | relation | object | source |
|---|---|---|---|
| jenazah | `DIBERSIHKAN_DARI` | hal-hal yang lain | manual_addition |
| jenazah | `DIBERSIHKAN_DARI` | kotoran-kotoran (yang telah lama berada pada badan orang yang meninggal) | manual_addition |

## S3078

> apabila semuanya sudah selesai, maka jenazah ditutup dengan kain putih dari ujung kepala hingga ujung kaki, agar tidak kelihatan sama sekali.

| subject | relation | object | source |
|---|---|---|---|
| jenazah | `DITUTUP_DENGAN` | kain putih (dari ujung kepala hingga ujung kaki) | manual_addition |
| jenazah (ditutup kain putih) | `BERTUJUAN` | agar tidak kelihatan sama sekali | manual_addition |

## S3080

> biasanya di samping jenazah akan ditaruhkan punjung (makanan) kecil yang berisi nasi dengan lauknya, kopi dan rokok (bagi orang yang meninggal di saat hidupnya suka merokok)

| subject | relation | object | source |
|---|---|---|---|
| punjung _(SARANA_RITUAL)_ | `DITARUHKAN_DI_SAMPING` | jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| punjung _(SARANA_RITUAL)_ | `BERISI` | kopi | manual_addition |
| punjung _(SARANA_RITUAL)_ | `BERISI` | nasi dengan lauknya | manual_addition |
| punjung _(SARANA_RITUAL)_ | `BERISI` | rokok | manual_addition |

## S3091

> oleh karena itu sering orang mengatakan bahwa "atma baan nyilih" atau "nyawa adalah pinjaman yang tidak memiliki ketentuan batas, sehingga nyawa itu dapat diambil sewaktu-waktu kapan saja tanpa ada pemberitahuan sebelumnya."

| subject | relation | object | source |
|---|---|---|---|
| atma baan nyilih dan nyawa _(KONSEP_FILOSOFIS)_ | `ADALAH` | pinjaman yang tidak memiliki ketentuan batas, sehingga nyawa itu dapat diambil sewaktu-waktu kapan saja tanpa ada pemberitahuan sebelumnya | manual_edit |

## S3110

> daun intaran ini akan digunakan sebanyak 2 (dua) lembar saja, dan akan ditaruh pada kedua alis orang yang meninggal ketika upacara mabersih mati (ngelelet).

| subject | relation | object | source |
|---|---|---|---|
| daun intaran | `DIGUNAKAN_SEBANYAK` | 2 lembar | manual_addition |
| daun intaran | `DITARUH_DI` | kedua alis jenazah (ketika upacara mabersih mati / ngelelet) _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S3118

> daun dapdap, daun dapdap ini dihaluskan dan diisi air sedikit, kemudian ditaruh di atas takir, gunanya adalah untuk sampo pencuci rambut (keramas) bagi jenazah ketika upacara nyiramang layon.

| subject | relation | object | source |
|---|---|---|---|
| daun dapdap _(SARANA_RITUAL)_ | `DIISI_DENGAN` | air | dependency_rule |
| daun dapdap _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | atas takir _(SARANA_RITUAL)_ | dependency_rule |
| daun dapdap | `DIGUNAKAN_SAAT` | upacara nyiramang layon _(TAHAPAN_UPACARA)_ | manual_addition |
| daun dapdap (yang dihaluskan) | `BERGUNA_SEBAGAI` | sampo pencuci rambut (keramas) bagi jenazah | manual_addition |

## S3122

> malem (bekas sarang lebah), terlebih dulu malem dipulung-pulung (dibuat bundar) kecil-kecil sebesar kelereng, minimal dua buah dan ditaruh di atas takir ini digunakan untuk ditaruh pada kedua lubang kuping jenazah ketika upacara melelet.

| subject | relation | object | source |
|---|---|---|---|
| malem _(SARANA_RITUAL)_ | `DIPULUNG` | kelereng | dependency_rule |
| malem _(SARANA_RITUAL)_ | `DIPULUNG` | minimal dua buah | dependency_rule |
| malem (di atas takir) | `DIPAKAI_UNTUK` | ditaruh pada kedua lubang kuping jenazah ketika upacara melelet | manual_addition |
| malem (setelah dipulung, minimal dua buah) | `DITARUH_DI` | atas takir _(SARANA_RITUAL)_ | manual_addition |

## S3133

> paes gedubang ini diletakkan di atas takir bersama dengan secarik kain hitam yang nanti akan digunakan untuk menutup kelamin (angkeb sarira).

| subject | relation | object | source |
|---|---|---|---|
| paes gedubang _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | atas takir _(SARANA_RITUAL)_ | manual_edit |
| paes gedubang _(SARANA_RITUAL)_ | `DILETAKKAN_DENGAN` | secarik kain hitam yang digunakan untuk menutup kelamin (angkeb sarira) | manual_edit |

## S3134

> lekesan (daun sirih yang digulung) diikat dengan benang putih, kemudian dimasukkan ke lubang satu uang kepeng (pipis bolong), lalu di ujung atasnya diisi bawang putih yang sudah dikupas dan ditusuk dengan lidi.

| subject | relation | object | source |
|---|---|---|---|
| lekesan _(SARANA_RITUAL)_ | `DIIKAT_DENGAN` | benang putih | dependency_rule |
| lekesan _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | lubang satu uang kepeng _(SARANA_RITUAL)_ | dependency_rule |
| lekesan _(SARANA_RITUAL)_ | `DIISI_DENGAN` | bawang putih | dependency_rule |

## S3141

> kawangen ini akan diisi uang kepeng (pipis bolong) yang jumlahnya bervariasi, ada beberapa yang diisi 11 kepeng dan akan ditaruh pada setiap persendian (buku-buku), ada 25 kepeng untuk pebaktian jenazah (ditaruh di dada dan se olah-olah dipegang oleh tangan jenazah), dan lain-lainnya.

| subject | relation | object | source |
|---|---|---|---|
| kawangen _(SARANA_RITUAL)_ | `DIISI_DENGAN` | uang kepeng _(SARANA_RITUAL)_ | dependency_rule |
| uang kepeng | `ADALAH` | pipis bolong _(SARANA_RITUAL)_ | object_decomposition |
| kawangen | `DIISI` | 11 kepeng (ditaruh pada setiap persendian/buku-buku) | manual_addition |
| kawangen | `DIISI` | 25 kepeng untuk pebaktian jenazah (ditaruh di dada, seolah-olah dipegang oleh tangan jenazah) | manual_addition |

## S3142

> empat buah kawangen jeriji, seperti telah disebutkan di atas bahwa setiap kwangen berisi lima buah lembaran-lembaran daun sirih yang digulung, diikat dengan tali benang dan setiap gulungan diisi uang kepeng, sedangkan di ujungnya diisi bawang putih sebagai lambang kuku, untuk ditaruh di tiap-tiap jari tangan dan kaki jenazah.

| subject | relation | object | source |
|---|---|---|---|
| kwangen _(SARANA_RITUAL)_ | `BERISI` | lima buah lembaran-lembaran daun sirih | dependency_rule |
| kwangen _(SARANA_RITUAL)_ | `DIIKAT_DENGAN` | tali benang | dependency_rule |
| kwangen | `DIISI_DENGAN` | bawang putih sebagai lambang kuku (di ujungnya) | manual_addition |
| kwangen (dengan bawang putih ini) | `DITARUH_DI` | tiap-tiap jari tangan dan kaki jenazah | manual_addition |
| kwangen (setiap gulungan) | `DIISI_DENGAN` | uang kepeng _(SARANA_RITUAL)_ | manual_addition |

## S3150

> sekar ura tersebut akan di taburkan pada setiap persimpangan jalan menuju ke setra.

| subject | relation | object | source |
|---|---|---|---|
| sekar ura | `DITABURKAN_DI` | setiap persimpangan jalan menuju setra _(BANGUNAN_RITUAL)_ | manual_addition |

## S3153

> sisig, ini dibuat dari arang pembakaran jaja uli atau jaja gina kemudian ditaruh di atas takir, yang nantinya digunakan untuk gosok gigi jenazah.

| subject | relation | object | source |
|---|---|---|---|
| sisig _(SARANA_RITUAL)_ | `TERBUAT_DARI` | arang pembakaran jaja gina | manual_edit |
| sisig _(SARANA_RITUAL)_ | `TERBUAT_DARI` | arang pembakaran jaja uli | dependency_rule |
| sisig _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | atas takir _(SARANA_RITUAL)_ | dependency_rule |
| sisig (di atas takir ini) | `DIPAKAI_UNTUK` | gosok gigi jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S3154

> pecahan kaca dan pecahan besi baja, juga ditaruh di atas takir, karena pecahan kaca akan ditaruh di kedua mata dan pecahan besi baja ditaruh di gigi jenazah.

| subject | relation | object | source |
|---|---|---|---|
| pecahan kaca dan pecahan besi baja _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | atas takir _(SARANA_RITUAL)_ | dependency_rule |
| pecahan besi baja | `DITARUH_DI` | gigi jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| pecahan kaca | `DITARUH_DI` | kedua mata (jenazah) _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S3155

> anggapan (anai-anai atau ketam), adalah sebuah pisau khusus yang digunakan untuk memotong padi pada masa lalu, sedangkan arit gobed adalah sabit kecil untuk memotong rumput.

| subject | relation | object | source |
|---|---|---|---|
| anggapan _(SARANA_RITUAL)_ | `ADALAH` | pisau khusus yang digunakan untuk memotong padi pada masa lalu | manual_edit |
| arit gobed _(SARANA_RITUAL)_ | `ADALAH` | sabit kecil untuk memotong rumput | manual_edit |

## S3165

> di suatu daerah ada juga yang tidak menumbuknya, tetapi anget-angetan tersebut dikunyah dan kemudian disemburkan pada hulu hati jenazah pada saat upacara ngelelet.

| subject | relation | object | source |
|---|---|---|---|
| anget-angetan | `DISEMBURKAN_PADA` | hulu hati jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| anget-angetan | `DISEMBURKAN_SAAT` | upacara ngelelet _(TAHAPAN_UPACARA)_ | manual_addition |

## S3195

> yaitu sebuah banten pamegat yang nantinya dipergunakan pada waktu acara maktining layon setelah upacara pabresihan hidup, namun sebelum upacara pabresihan mati (ngelelet).

| subject | relation | object | source |
|---|---|---|---|
| upacara pabresihan mati | `ADALAH` | ngelelet _(TAHAPAN_UPACARA)_ | object_decomposition |
| banten pamegat _(SARANA_RITUAL)_ | `DIGUNAKAN_SAAT` | acara maktining layon _(SARANA_RITUAL)_ | manual_addition |
| banten pamegat _(SARANA_RITUAL)_ | `DIGUNAKAN_SEBELUM` | upacara pabresihan mati | manual_addition |

## S3196

> lis bale gading ini terdiri dari sasap, rangkadan, sorohan kecil, daksina, tipat, raka-raka, padma, bersihan payasan, benang tatebus, sampian pusung, sanggah urip, gelar sanga, sorohan, lis amuan-amuan, dan coblong.

| subject | relation | object | source |
|---|---|---|---|
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | sasap _(SARANA_RITUAL)_ | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | rangkadan | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | sorohan kecil _(SARANA_RITUAL)_ | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | daksina _(SARANA_RITUAL)_ | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | tipat | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | raka-raka | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | padma | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | bersihan payasan | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | benang tatebus | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | sampian pusung | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | sanggah urip _(BANGUNAN_RITUAL)_ | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | gelar sanga | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | sorohan _(SARANA_RITUAL)_ | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | lis amuan-amuan _(SARANA_RITUAL)_ | dependency_rule |
| lis bale gading _(SARANA_RITUAL)_ | `TERDIRI_DARI` | coblong | dependency_rule |

## S3221

> tirta pengeringkes (ke tiga tirta-tirta di atas didapat di gria),

| subject | relation | object | source |
|---|---|---|---|
| tirta pengeringkes _(TIRTHA_SUCI)_ | `DIDAPAT_DI` | gria _(BANGUNAN_RITUAL)_ | dependency_rule |

## S3237

> lekesan, (sirih lengkap dengan isinya termasuk tembakau, dan digulung).

| subject | relation | object | source |
|---|---|---|---|
| lekesan _(SARANA_RITUAL)_ | `BERISI` | tembakau | dependency_rule |

## S3294

> ketika jenazah akan ditaruh pada pepaga/asagan, maka jenazah tersebut tidak boleh ditaruh begitu saja dari samping pepaga/asagan, namun jenazah itu harus melalui ujung pepaga/asagan yang di teben (dari barat), dengan posisi diputar, yaitu kepala jenazah dimasukkan terlebih dulu baru kemudian kakinya berselonjor ke teben atau ke barat.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DILETAKKAN_DI` | pepaga/asagan _(SARANA_RITUAL)_ | dependency_rule |
| jenazah | `DIMASUKKAN` | kepala terlebih dahulu | manual_addition |
| jenazah | `HARUS_MELALUI` | ujung pepaga/asagan yang di teben (barat) | manual_addition |
| kaki jenazah | `BERSELONJOR_KE` | teben/barat | manual_addition |

## S3295

> logikanya bahwa jenazah itu naik bale dari teben menuju ke luanan (hulu), bukan dari samping, atau dari luanan (hulu).

| subject | relation | object | source |
|---|---|---|---|
| jenazah | `NAIK` | bale (dari arah teben menuju luanan/hulu) | manual_addition |

## S3296

> ketika jenazah sudah berada di atas pepaga/asagan, masyarakat atau keluarga tidak boleh kesusu (tergesa-gesa) untuk memandikannya.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `BERADA_DI` | pepaga/asagan _(SARANA_RITUAL)_ | dependency_rule |
| keluarga/masyarakat | `DILARANG` | tergesa-gesa memandikan jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S3330

> sebelum upacara nyiramang layon dilaksanakan, maka krama (masyarakat banjar) akan membuat bale-bale tempat memandikan mayat yang disebut pepaga atau asagan.

| subject | relation | object | source |
|---|---|---|---|
| bale-bale (tempat memandikan mayat) | `DIKENAL_SEBAGAI` | asagan _(SARANA_RITUAL)_ | manual_addition |
| bale-bale (tempat memandikan mayat) | `DIKENAL_SEBAGAI` | pepaga _(SARANA_RITUAL)_ | manual_addition |
| krama (masyarakat banjar) | `MEMBUAT` | bale-bale tempat memandikan mayat _(BANGUNAN_RITUAL)_ | manual_addition |

## S3332

> pepaga atau di beberapa tempat di denpasar menyebut asagan, dan ada juga yang menyebutkan bale penusangan, adalah semacam dipan atau bale darurat yang juga bisa dipergunakan sebagai usungan atau tandu.

| subject | relation | object | source |
|---|---|---|---|
| pepaga _(SARANA_RITUAL)_ | `DIKENAL_SEBAGAI` | asagan _(SARANA_RITUAL)_ | dependency_rule |
| pepaga | `DIKENAL_SEBAGAI` | bale penusangan (istilah Denpasar) _(BANGUNAN_RITUAL)_ | manual_addition |
| pepaga/asagan | `ADALAH` | semacam dipan atau bale darurat _(BANGUNAN_RITUAL)_ | manual_addition |
| pepaga/asagan | `DIPERGUNAKAN_SEBAGAI` | tandu _(SARANA_RITUAL)_ | manual_addition |
| pepaga/asagan | `DIPERGUNAKAN_SEBAGAI` | usungan _(SARANA_RITUAL)_ | manual_addition |

## S3333

> bale ini terbuat dari bambu dan galar nya juga terdiri dari bilah-bilah bambu berjumlah sebanyak 9 (sembilan) buah.

| subject | relation | object | source |
|---|---|---|---|
| bale _(BANGUNAN_RITUAL)_ | `TERBUAT_DARI` | bambu | dependency_rule |
| bale _(BANGUNAN_RITUAL)_ | `TERBUAT_DARI` | galar _(SARANA_RITUAL)_ | dependency_rule |
| galar _(SARANA_RITUAL)_ | `TERDIRI_DARI` | bilah-bilah bambu (sebanyak 9 buah) | manual_addition |

## S3339

> setelah waktu untuk upacara nyiramang layon dimulai, maka para krama atau keluarga yang meninggal akan mengambil jenazah, dari balai tempat jenazah itu disemayamkan (bagi umat hindu di bali yang memiliki tatanan rumah stil bali, tempat persemayaman jenazah ditempatkan di bale semanggen).

| subject | relation | object | source |
|---|---|---|---|
| krama atau keluarga _(STRUKTUR_SOSIAL_ADAT)_ | `MENGAMBIL` | jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIAMBIL_DARI` | balai (tempat jenazah disemayamkan) _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| tempat persemayaman jenazah | `DITEMPATKAN_DI` | bale semanggen _(BANGUNAN_RITUAL)_ | manual_addition |

## S3340

> jenazah itu akan diusung menuju ke tempat penusangan (nyiramang layon) yang berupa pepaga atau asagan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIUSUNG_KE` | tempat penusangan | manual_addition |
| tempat penusangan | `DIPAKAI_UNTUK` | nyiramang layon _(TAHAPAN_UPACARA)_ | manual_addition |
| tempat penusangan | `BERUPA` | pepaga atau asagan _(SARANA_RITUAL)_ | manual_addition |

## S3354

> ini menyimbulkan bahwa jenazah tersebut naik ke pepaga/asagan, dengan terlebih dulu duduk dan kemudian baru tidur tertelentang.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `NAIK_KE` | pepaga/asagan _(SARANA_RITUAL)_ | manual_addition |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIDUDUKKAN_DULU_SEBELUM` | tidur tertelentang di pepaga/asagan _(SARANA_RITUAL)_ | manual_addition |

## S3355

> disamping itu jenazah yang masuk melalui teben dari pepaga, memiliki makna agar orang yang meninggal tersebut lebih cepat menemui brahman (sang pencipta), sesuai dengan kisah yang disebutkan dalam kitab mahabarata.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIMASUKKAN_MELALUI` | teben pepaga/asagan _(SARANA_RITUAL)_ | manual_addition |
| jenazah yang masuk melalui teben dari pepaga _(ISTILAH_UMUM_RITUAL)_ | `BERMAKNA` | agar orang yang meninggal lebih cepat menemui brahman (sang pencipta) | manual_addition |

## S3363

> setelah jenazah ditaruh di atas pepaga/asagan, maka di bawah kepala jenazah dialasi dengan bantal biasa (bantal kapuk), sehingga jenazah tersebut seolah-olah seperti orang sedang tidur.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DITARUH` | atas pepaga/asagan _(SARANA_RITUAL)_ | dependency_rule |
| kepala jenazah | `DIALASI_DENGAN` | bantal biasa (bantal kapuk) | manual_addition |

## S3364

> ada suatu hal penting yang perlu diperhatikan karena hal ini menyangkut soal etika atau tata susila yaitu ketika jenazah baru ditaruh di asagan harus dibiarkan sebentar dan jangan garasa-grusu (tergesa-gesa) membuka pakaiannya, karena perlu menunggu orang yang dituakan atau orang lebih tua, yang akan terlebih dulu mencuci muka dan rambut orang yang meninggal itu.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `HARUS_DIBIARKAN` | sebentar (sebelum dibuka pakaiannya) | manual_addition |
| orang yang dituakan/lebih tua | `MENCUCI` | muka dan rambut jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S3446

> mengenakan kain (mewastra), dengan selesainya memandikan pada tahap pertama maka jenazah akan diberi pakaian seperti layaknya orang masih hidup dengan tatanannya sebagai berikut:

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBERI` | pakaian seperti layaknya orang masih hidup | manual_edit |

## S3468

> ini dimaksudkan bahwa jenazah tersebut seolah-olah masih hidup, berhias, memakai cincin, kalung, gelang (jika mereka punya) seperti pergi menghadiri kundangan atau pergi ke pura.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `MEMAKAI` | cincin | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `MEMAKAI` | kalung | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `MEMAKAI` | gelang | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIHIAS_SEOLAH_OLAH` | pergi menghadiri undangan atau ke pura | manual_addition |

## S3496

> kesepuluh: lekesan (daun sirih yang di gulung) ditempelkan sejenak pada gigi jenazah, dan dibersihkan dengan cara mengusap-usapkan tembakau pada bibir jenazah.

| subject | relation | object | source |
|---|---|---|---|
| lekesan _(SARANA_RITUAL)_ | `DITEMPELKAN_DI` | gigi jenazah (ISTILAH_UMUM_RITUAL) _(ISTILAH_UMUM_RITUAL)_ | manual_edit |
| jenazah (bibir) | `DIBERSIHKAN_DENGAN` | tembakau (diusapkan pada bibir) | manual_addition |

## S3544

> setelah selesai upacara sembah bhakti ini, semua kawangen yang tadi dipakai sembahyang dikumpulkan dan ditaruh di samping jenazah, sebagai tanda doa restu agar perjalanan roh yang meninggal tidak mendapatkan suatu halangan.

| subject | relation | object | source |
|---|---|---|---|
| kawangen _(SARANA_RITUAL)_ | `MELAMBANGKAN` | tanda doa restu | manual_edit |
| kawangen _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | samping jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| kawangen (di samping jenazah) _(SARANA_RITUAL)_ | `BERTUJUAN_AGAR` | perjalanan roh yang meninggal tidak mendapat halangan | manual_addition |

## S3546

> oleh sebab itu jenazah tersebut sebelumnya diisi dengan sebuah kawangen di tangannya (pada saat akhir pabersihan hidup tangan jenazah/layon ditaruh di dada dengan telapak tangan ditumpuk diisi sebuah kawangen sebagai simbol sikap amusti karana, karena seolah-olah layon/jenazah ikut sembahyang).

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIISI_DENGAN` | kawangen di tangan _(SARANA_RITUAL)_ | manual_edit |
| kawangen _(SARANA_RITUAL)_ | `MELAMBANGKAN` | sikap amusti karana (seolah-olah layon ikut sembahyang) | manual_addition |
| tangan jenazah/layon | `DILETAKKAN_DI` | dada | manual_addition |
| tangan jenazah/layon | `DITARUH_DENGAN` | posisi telapak tangan ditumpuk (ditumpangkan) | manual_addition |

## S3547

> setelah upacara sembah bhakti selesai, maka jenazah diperciki dan diminumkan tirta yang berasal dari bhetara hyang guru yaitu tirta yang dimohonkan di sanggah atau pamerajan keluarga orang yang meninggal.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPERCIKI_DAN_DIMINUMKAN` | tirta _(TIRTHA_SUCI)_ | manual_addition |
| tirta | `BERASAL_DARI` | bhetara hyang guru _(KONSEP_FILOSOFIS)_ | manual_addition |
| tirta | `DIMOHONKAN_DI` | sanggah/pamerajan keluarga orang yang meninggal | manual_addition |

## S3559

> waja meka panca datu,

| subject | relation | object | source |
|---|---|---|---|
| waja | `BAGIAN_DARI` | panca datu _(SARANA_RITUAL)_ | manual_addition |

## S3584

> pengerikan kuku mutlak dilakukan pada waktu upacara "melelet" (pabersihan mati), dan tidak boleh dilakukan pada saat "pabersihan hidup" yang telah dilaksanakan sebelumnya.

| subject | relation | object | source |
|---|---|---|---|
| pengerikan kuku mutlak _(TAHAPAN_UPACARA)_ | `DILAKUKAN_SAAT` | upacara "melelet" (pabersihan mati) _(TAHAPAN_UPACARA)_ | manual_edit |
| pengerikan kuku | `TIDAK_BOLEH_DILAKUKAN_SAAT` | pabersihan hidup _(TAHAPAN_UPACARA)_ | manual_addition |

## S3586

> karena pada saat upacara "pabersihan hidup" si jenazah masih dianggap sebagai orang yang masih hidup.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIANGGAP_SEBAGAI` | orang yang masih hidup | manual_addition |

## S3589

> arit gobed adalah simbol dari rare angon yaitu lambang keperkasaan seorang laki-laki.

| subject | relation | object | source |
|---|---|---|---|
| arit gobed _(SARANA_RITUAL)_ | `ADALAH` | simbol rare angon | manual_edit |
| arit gobed _(SARANA_RITUAL)_ | `MELAMBANGKAN` | keperkasaan seorang laki-laki | manual_addition |

## S3591

> anggapan (ani-ani atau ketam) adalah simbol dari dewi sri, yaitu lambang kesuburan, yang mana nantinya diharapkan wanita yang akan "numitis" memiliki kesuburan untuk dapat melahirkan.

| subject | relation | object | source |
|---|---|---|---|
| anggapan _(SARANA_RITUAL)_ | `MELAMBANGKAN` | kesuburan | manual_addition |
| anggapan (ani-ani atau ketam) _(SARANA_RITUAL)_ | `ADALAH` | simbol dewi sri _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| penggunaan anggapan | `BERTUJUAN_AGAR` | wanita yang numitis memiliki kesuburan untuk melahirkan | manual_addition |

## S3599

> namun sekarang ini demi cepatnya, babelonyoh tersebut hanya dioleskan pada dada jenazah, karena pakaian jenazah yang dipakaikan ketika upacara pabersihan hidup masih dibiarkan melekat, sedangkan hanya dada jenazah sajalah yang tidak memakai pakaian.

| subject | relation | object | source |
|---|---|---|---|
| babelonyoh _(SARANA_RITUAL)_ | `DIOLESKAN_DI` | dada jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |

## S3604

> itik-itik, setelah kesepuluh kuku tangan dan kuku kaki dikerik serta penggunaan babelonyoh dilaksanakan, dan telah dibersihkan dengan air, maka kedua jempol jari-jari tangan (ibu jari) diikat jadi satu dengan seutas tali benang tukelan (benang tenun bali) berwarna putih, begitu juga kedua jempol jari kaki diikat jadi satu dengan seutas tali benang tukelan.

| subject | relation | object | source |
|---|---|---|---|
| jempol jari kaki | `DIIKAT_DENGAN` | tali benang tukelan _(SARANA_RITUAL)_ | manual_addition |
| jempol jari tangan (kedua ibu jari) | `DIIKAT_DENGAN` | tali benang tukelan (benang tenun bali) berwarna putih | manual_addition |

## S3610

> umbi sikapa/sekapa (umbi gadung): jenazah disabuni (digosok) dengan umbi sikapa/sekapa, kemudian dibilas dengan air dan dikeringkan dengan kain kering.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DISABUNI_DENGAN` | umbi sikapa/sekapa _(SARANA_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBILAS_DENGAN` | air | manual_addition |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIKERINGKAN_DENGAN` | kain kering | manual_addition |

## S3623

> mewastra (berpakaian): setelah semuanya kering maka jenazah kenakan pakaian putih-putih, antara lain pakaian atau kain bawahnya berwarna putih, saput serta umpal (tali saput) juga berwarna putih dan udeng untuk laki-lakipun berwarna putih.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPAKAIKAN` | pakaian putih-putih | dependency_rule |
| umpal | `ADALAH` | tali saput | object_decomposition |
| kain bawah | `BERWARNA` | putih | manual_addition |
| saput | `BERWARNA` | putih | manual_addition |
| udeng (untuk laki-laki) _(SARANA_RITUAL)_ | `BERWARNA` | putih | manual_addition |
| umpal | `BERWARNA` | putih | manual_addition |

## S3647

> daun pisang saba setelah selesai berpakaian maka jenazah tersebut dialasi dengan "daun pisang saba" yang berfungsi sebagai tikar.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIALASI_DENGAN` | daun pisang saba | dependency_rule |
| daun pisang saba | `BERFUNGSI_SEBAGAI` | tikar | object_decomposition |

## S3649

> sesisir pisang kayu sebagai bantal di kepala : disamping mengalasi dengan daun pisang (namun bagi masyarakat yang tidak biasa menggunakan daun pisang tidak menjadi masalah, karena hal ini tidak mutlak digunakan), juga ada penggantian bantal, yang tadinya jenazah tersebut berbantalkan kapuk diganti dengan bantal sesisir buah pisang kayu.

| subject | relation | object | source |
|---|---|---|---|
| bantal kapuk | `DIGANTI_DENGAN` | bantal sesisir buah pisang kayu | manual_addition |

## S3651

> kembali pada makna pada penggunaan sesisir buah pisang kayu untuk bantal, yang dihubungkan dengan kitab purana yang menceriterakan ketika dewa wishnu selesai pengaduk lautan susu untuk mendapatkan tirtha amertha, maka beliau tidur di atas samudra, dialasi dan dipayungi oleh seekor naga (ular cobra) yang berkepala banyak (perhatikan bulir-bulir pisang pada satu sisir, kelihatan seperti kepala ular yang menyembul), sehingga terhindar dari marabahaya dan kepanasan.

| subject | relation | object | source |
|---|---|---|---|
| dewa wishnu _(ENTITAS_KEAGAMAAN)_ | `TIDUR_DI` | atas samudra (dialasi dan dipayungi naga/ular cobra berkepala banyak) | manual_addition |
| dewa wishnu _(ENTITAS_KEAGAMAAN)_ | `MENDAPATKAN` | tirtha amertha _(KONSEP_FILOSOFIS)_ | manual_addition |

## S3653

> gegaleng pada kepala: kata "gegaleng" juga berarti bantal untuk tidur.

| subject | relation | object | source |
|---|---|---|---|
| gegaleng kepala _(SARANA_RITUAL)_ | `BERARTI` | bantal untuk tidur | manual_edit |

## S3654

> gegaleng ini dibuat dari uang kepeng (pipis bolong) sebanyak 250 biji serta beberapa potongan-potongan dahan kayu dapdap yang dibungkus dengan kain putih.

| subject | relation | object | source |
|---|---|---|---|
| uang kepeng | `ADALAH` | pipis bolong _(SARANA_RITUAL)_ | object_decomposition |
| gegaleng _(SARANA_RITUAL)_ | `TERBUAT_DARI` | potongan-potongan dahan kayu dapdap yang dibungkus dengan kain putih | manual_addition |
| gegaleng _(SARANA_RITUAL)_ | `TERBUAT_DARI` | uang kepeng (pipis bolong) sebanyak 250 biji | manual_addition |

## S3656

> gegaleng ini adalah pengganti bantal kapuk yang telah dipakai pada waktu "pabersihan hidup", sehingga gegaleng ini juga disebut dengan "galeng pengerekan".

| subject | relation | object | source |
|---|---|---|---|
| gegaleng _(SARANA_RITUAL)_ | `ADALAH` | pengganti bantal kapuk yang telah dipakai pada waktu pabersihan hidup | manual_edit |
| gegaleng | `DIKENAL_SEBAGAI` | galeng pengerekan | manual_addition |

## S3694

> om sang hyang widhi, atas se ijin sang hyang hayu, atma sang meninggal lepas bebas dari badannya dan cepat melesat mencapai tujuan.

| subject | relation | object | source |
|---|---|---|---|
| atma _(KONSEP_FILOSOFIS)_ | `LEPAS_BEBAS_DARI` | badan | manual_addition |

## S3720

> disamping itu "anget-angetan" dapat menghilangkan bau busuk, ini juga bermakna agar orang yang meninggal tersebut kelak numitis lagi, disamping terhindar dari penyakit, juga agar memiliki budhi pekerti dan pikiran baik dan jernih, terlepas dari kebusukan-kebusukan, yang merupakan penyakit dalam kehidupan di dunia ini.

| subject | relation | object | source |
|---|---|---|---|
| anget-angetan _(SARANA_RITUAL)_ | `MENGHILANGKAN` | bau busuk | dependency_rule |
| anget-angetan | `BERMAKNA` | agar orang yang meninggal dapat numitis lagi dan terhindar dari penyakit, serta memiliki budi pekerti dan pikiran yang baik | manual_addition |

## S3728

> adapun makna penggunaan wewangian adalah agar kelak jika numitis lagi selalu mendapat pujian keharuman dalam setiap tingkah lakunya, di samping tersebut tubuhnya agar kelak berbau harum.

| subject | relation | object | source |
|---|---|---|---|
| penggunaan wewangian | `BERTUJUAN_AGAR` | orang yang numitis memperoleh pujian keharuman dalam tingkah lakunya | manual_addition |
| penggunaan wewangian | `BERTUJUAN_AGAR` | tubuh jenazah kelak berbau harum _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S3733

> kwangen jeriji : setelah pelaksanaan eteh-eteh pabersihan mati hampir selesai dilakukan maka pada setiap telapak tangan dan telapak kaki ditaruh masing-masing sebuah "kawangen jeriji".

| subject | relation | object | source |
|---|---|---|---|
| kwangen jeriji | `DITARUH_DI` | telapak kaki | manual_addition |
| kwangen jeriji | `DITARUH_DI` | telapak tangan | manual_addition |

## S3734

> kawangen jeriji adalah sebuah kojong yang dibuat dari daun pisang dan di dalamnya berisi lima buah gulungan "base" (daun sirih), setiap satu gulung daun sirih diikat dengan benang putih, kemudian gulungan sirih dimasukkan ke dalam lubang uang kepeng sampai sepanjang setengah gulungan sirih tersebut.

| subject | relation | object | source |
|---|---|---|---|
| kawangen jeriji _(SARANA_RITUAL)_ | `ADALAH` | kojong | dependency_rule |
| kojong | `TERBUAT_DARI` | daun pisang | object_decomposition |
| gulungan daun sirih | `DIIKAT_DENGAN` | benang putih | manual_addition |
| gulungan sirih | `DIMASUKKAN_KE` | lubang uang kepeng _(SARANA_RITUAL)_ | manual_addition |
| kojong (kawangen jeriji) | `BERISI` | lima buah gulungan base (daun sirih) | manual_addition |

## S3742

> sedangkan "kesuna" atau bawang putih bermakna agar orang tersebut bila numitis kembali, memiliki kuku-kuku yang indah dan putih bersih.

| subject | relation | object | source |
|---|---|---|---|
| kesuna (bawang putih) | `BERMAKNA` | agar orang yang numitis kembali memiliki kuku-kuku yang indah dan putih bersih | manual_addition |

## S3747

> di hulu hati, diisi sebuah kawangen yang berisi 9 biji uang kepeng dan bunga tunjung putih.

| subject | relation | object | source |
|---|---|---|---|
| kawangen _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | hulu hati | dependency_rule |
| kawangen _(SARANA_RITUAL)_ | `BERISI` | 9 biji uang kepeng _(SARANA_RITUAL)_ | dependency_rule |
| kawangen _(SARANA_RITUAL)_ | `BERISI` | bunga tunjung putih | dependency_rule |

## S3749

> di dada, diisi sebuah kawangen yang berisi 7 biji uang kepeng dan bunga tunjung putih.

| subject | relation | object | source |
|---|---|---|---|
| kawangen _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | dada | dependency_rule |
| kawangen _(SARANA_RITUAL)_ | `BERISI` | 7 biji uang kepeng _(SARANA_RITUAL)_ | dependency_rule |
| kawangen _(SARANA_RITUAL)_ | `BERISI` | bunga tunjung putih | dependency_rule |

## S3753

> di kedua lutut kaki, diisi masing-masing kawangen yang berisi 5 biji uang kepeng dan pusuh bunga cempaka kuning.

| subject | relation | object | source |
|---|---|---|---|
| kawangen _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | kedua lutut kaki | dependency_rule |
| kawangen _(SARANA_RITUAL)_ | `BERISI` | 5 biji uang kepeng _(SARANA_RITUAL)_ | dependency_rule |
| kawangen _(SARANA_RITUAL)_ | `BERISI` | pusuh bunga cempaka kuning | dependency_rule |

## S3755

> uang kepeng yang asli diyakini mengandung lima unsur logam yang terdiri dari : (1) perak (putih), tempatnya di timur, dewanya adalah dewa iswara.

| subject | relation | object | source |
|---|---|---|---|
| perak | `BERDEWA` | dewa iswara _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| perak | `BERWARNA` | putih | manual_addition |
| perak | `BERADA_DI` | timur | manual_addition |
| uang kepeng asli _(SARANA_RITUAL)_ | `MENGANDUNG` | lima unsur logam | manual_addition |

## S3756

> (2) tembaga (merah), tempatnya di selatan, dewanya adalah dewa brahma.

| subject | relation | object | source |
|---|---|---|---|
| tembaga | `BERDEWA` | dewa brahma _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| tembaga | `BERWARNA` | merah | manual_addition |
| tembaga | `BERADA_DI` | selatan _(Place)_ | manual_addition |

## S3757

> (3) emas (kuning), tempatnya di barat, dewanya adalah dewa mahadewa.

| subject | relation | object | source |
|---|---|---|---|
| emas | `BERADA_DI` | barat | manual_addition |
| emas | `BERDEWA` | dewa mahadewa _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| emas | `BERWARNA` | kuning | manual_addition |

## S3758

> (4) besi (hitam), tempatnya di utara, dewanya adalah dewa wishnu, dan (5) logam campuran (manca warna), tempatnya di tengah-tengah, dewanya adalah dewa siwa.

| subject | relation | object | source |
|---|---|---|---|
| besi | `BERDEWA` | dewa wishnu _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| besi | `BERWARNA` | hitam | manual_addition |
| besi | `BERADA_DI` | utara | manual_addition |
| logam campuran | `BERDEWA` | dewa siwa _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| logam campuran | `BERWARNA` | manca warna | manual_addition |
| logam campuran | `BERADA_DI` | tengah | manual_addition |

## S3760

> a di beberapa tempat atau desa, pada akhir acara "melelet" sebelum jenazah digulung atau sebelum "pangringkesan", ada yang menaruhkan jarum (jaum) dan besi paku pada lengan jenazah.

| subject | relation | object | source |
|---|---|---|---|
| besi paku | `DITARUH_DI` | lengan jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |
| jarum (jaum) | `DITARUH_DI` | lengan jenazah _(ISTILAH_UMUM_RITUAL)_ | manual_addition |

## S3783

> ketiga, tirtha tersebut dipercikkan ke semua badan hingga ke kaki jenazah, setelah itu priuk tempat tirtha pangringkes tersebut dipecahkan dan dibuang di kolong bawah pepaga atau asagan.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `DIPERCIKKAN_PADA` | seluruh badan hingga ke kaki jenazah | manual_edit |
| priuk (tempat tirtha pangringkes) | `DIPECAHKAN` | setelah tirtha dipercikkan _(TIRTHA_SUCI)_ | manual_addition |
| priuk (yang pecah) | `DIBUANG_DI` | kolong bawah pepaga/asagan _(SARANA_RITUAL)_ | manual_addition |

## S3791

> mula-mula jenazah dibungkus dengan kain putih, biasanya akan dibungkus sampai tiga lapis kemudian diikat dengan tali benang tukelan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBUNGKUS_DENGAN` | kain putih _(SARANA_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBUNGKUS` | tiga lapis | dependency_rule |
| jenazah (setelah dibungkus tiga lapis) | `DIIKAT_DENGAN` | tali benang tukelan _(SARANA_RITUAL)_ | manual_addition |

## S3799

> selesai membungkus (ngeringkes), maka jenazah ditutupi dengan selembar kain putih yang panjangnya kira-kira dua sampai dua setengah meter, sedangkan di atas kain tersebut diisi rurub sinom sebanyak lima buah.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DITUTUPI_DENGAN` | kain putih (panjang kira-kira 2 sampai 2,5 meter) _(SARANA_RITUAL)_ | manual_addition |
| kain (penutup jenazah) | `DIISI_DENGAN` | rurub sinom sebanyak lima buah _(SARANA_RITUAL)_ | manual_addition |

## S3800

> rurub sinom adalah hiasan yang terbuat dari blangsah (bunga pinang yang belum mekar) dijarit bersama daun kelapa muda (busung), dengan panjang kira-kira 40 sampai 45 sentimeter.

| subject | relation | object | source |
|---|---|---|---|
| rurub sinom _(SARANA_RITUAL)_ | `ADALAH` | hiasan | dependency_rule |
| hiasan | `TERBUAT_DARI` | blangsah _(SARANA_RITUAL)_ | object_decomposition |
| blangsah _(SARANA_RITUAL)_ | `ADALAH` | bunga pinang yang belum mekar | manual_edit |
| hiasan | `TERBUAT_DARI` | daun kelapa muda (busung) | manual_addition |
| rurub sinom _(SARANA_RITUAL)_ | `BERUKURAN_PANJANG` | kira-kira 40 sampai 45 sentimeter | manual_addition |

## S3802

> setelah semua sudah selesai dilakukan, barulah kemudian jenazah dibawa ke balai-balai (bale semanggen) tempat jenazah disemayamkan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | balai-balai | dependency_rule |
| balai-balai | `ADALAH` | bale semanggen _(BANGUNAN_RITUAL)_ | object_decomposition |

## S3811

> untuk jenazah yang dimasukkan ke dalam peti, biasanya rurub sinom yang tadinya telah ditaruh di atas gulungan jenazah, diambil terlebih dulu.

| subject | relation | object | source |
|---|---|---|---|
| rurub sinom | `DIAMBIL_DARI` | gulungan jenazah (sebelum dimasukkan ke peti) | manual_addition |

## S3812

> setelah jenazah dimasukkan ke dalam peti, dan peti telah ditutup rapat maka rurub sinom tadi ditaruh di atas peti dengan posisi menaruhnya sama seperti sebelumnya yaitu di atas kepala, leher, perut, paha dan kaki dengan posisi melintang, seperti ketika menaruh di atas jenazah.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | peti | dependency_rule |
| rurub sinom tadi _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | atas peti | manual_edit |
| rurub sinom tadi _(SARANA_RITUAL)_ | `DILETAKKAN_MELINTANG_DI` | kepala, leher, perut, paha dan kaki | manual_addition |

## S3816

> adapun "ante" yang digunakan untuk "ngeringkes" adalah terbuat dari bilahan-bilahan bambu yang disebut dengan "galar".

| subject | relation | object | source |
|---|---|---|---|
| ante _(SARANA_RITUAL)_ | `TERBUAT_DARI` | bilahan-bilahan bambu | dependency_rule |
| bilahan-bilahan bambu (ante) | `DIKENAL_SEBAGAI` | galar _(SARANA_RITUAL)_ | manual_addition |

## S3836

> cawan, "galar" yang ketekannya jatuh pada "cawan", maka bale-bale / dipan yang menggunakan "galar" dengan ketekan "cawan" sangat baik digunakan untuk dipan /plangkan di warung ataupun di dapur.

| subject | relation | object | source |
|---|---|---|---|
| bale-bale/dipan | `DIPAKAI_UNTUK` | warung atau dapur | manual_addition |

## S3843

> oleh karena itu "galar' dengan ketekan "guling" sangat bagus digunakan pada bele-bale atau dipan di kamar tidur, dengan harapan bisa cepat membuat ngantuk dan bisa tidur nyenyak.

| subject | relation | object | source |
|---|---|---|---|
| galar (dengan ketekan guling) | `DIGUNAKAN_DENGAN_HARAPAN` | membuat ngantuk dan tidur nyenyak | manual_addition |

## S3845

> cekur, kata "cekur" artinya bertembang, maka "galar" yang ketekannya jatuh pada "cekur", maka bale-bale tersebut sangat baik ditaruh di pura atau di merajan, karena diharapkan kepada setiap yang menduduki bale-bale tersebut timbul keinginannya untuk bertembang seperti makidung atau makekawin, yang sesuai dengan tempatnya di tempat suci.

| subject | relation | object | source |
|---|---|---|---|
| bale-bale | `DILETAKKAN_DI` | pura atau merajan _(BANGUNAN_RITUAL)_ | manual_addition |

## S3852

> apabila ingin mendapatkan ketekan "cekur", maka "galar" akan dibuat jumlahnya kelipatan 5, misalnya 5, 10, 15, 20, 25, 30 dan seterusnya.

| subject | relation | object | source |
|---|---|---|---|
| jumlah galar | `CONTOH` | 5, 10, 15, 20, 25, 30, dan seterusnya (kelipatan 5) | manual_addition |

## S3860

> upacara mesulub hanyalah merupakan suatu kepercayaan setempat (kepercayaan lokal) yang telah diwarisi turun temurun dari sejak jaman dulu di daerah atau desa setempat.

| subject | relation | object | source |
|---|---|---|---|
| upacara mesulub _(RITUAL_KEMATIAN)_ | `ADALAH` | kepercayaan setempat yang telah diwarisi turun temurun sejak jaman dulu di daerah atau desa setempat | manual_edit |
| kepercayaan setempat | `ADALAH` | kepercayaan lokal | object_decomposition |

## S3862

> disamping itu "upacara mesulub" adalah merupakan konsep "satya" atau kesetiaan.

| subject | relation | object | source |
|---|---|---|---|
| upacara mesulub _(RITUAL_KEMATIAN)_ | `ADALAH` | konsep satya (kesetiaan) | manual_edit |

## S3868

> apabila upacara suluban ini selesai, maka jenazah akan dibawa ke bale tempat jenazah disemayamkan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | bale tempat jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |

## S3904

> di beberapa tempat ada yang melakukan upacara mesaji atau memunjung ketika jenazah masih berada di atas pepaga/asagan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `BERADA_DI` | atas pepaga/asagan _(SARANA_RITUAL)_ | dependency_rule |
| masyarakat setempat | `MELAKUKAN` | upacara mesaji (atau memunjung), ketika jenazah masih di atas pepaga/asagan | manual_addition |

## S3906

> setelah upacara mesaji selesai barulah jenazah dipindahkan ke balai-balai tempat jenazah disemayamkan.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | balai-balai tempat jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |

## S3909

> bagaimana jika jenazah tersebut akan langsung dibawa ke setra untuk segera di kuburkan, bukan diaben?

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBAWA_KE` | setra untuk segera dikuburkan (bukan diaben) | manual_edit |

## S3914

> namun apabila jenazah akan di "aben" maka ada rangkaian upacara lain yang harus dilakukan sebelum jenazah di bawa ke setra.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `MENJALANI` | rangkaian upacara lain sebelum dibawa ke setra (jika diaben) | manual_addition |

## S3936

> mamakaikan kain (mewastra), dengan selesainya memandikan pada tahap pertama maka jenazah akan diberi pakaian seperti layaknya orang masih hidup dengan tatanannya sebagai berikut:

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBERI` | pakaian seperti layaknya orang masih hidup | manual_edit |

## S3963

> setelah selesai upacara sembah bhakti ini, semua kawangen yang tadi dipakai sembahyang dikumpulkan dan ditaruh di samping jenazah.

| subject | relation | object | source |
|---|---|---|---|
| kawangen _(SARANA_RITUAL)_ | `DILETAKKAN_DI` | samping jenazah _(ISTILAH_UMUM_RITUAL)_ | dependency_rule |
| kawangen _(SARANA_RITUAL)_ | `DIKUMPULKAN` | (setelah upacara sembah bhakti) _(TAHAPAN_UPACARA)_ | manual_addition |

## S3964

> setelah upacara sembah bhakti selesai, maka jenazah diperciki dan diminumkan tirta yang berasal dari bhatara hyang guru yaitu tirta yang dimohonkan di sanggah atau pamerajan keluarga orang yang meninggal.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPERCIKI_DAN_DIMINUMKAN` | tirta _(TIRTHA_SUCI)_ | manual_addition |
| tirta | `BERASAL_DARI` | bhetara hyang guru _(KONSEP_FILOSOFIS)_ | manual_addition |
| tirta | `DIMOHONKAN_DI` | sanggah/pamerajan keluarga orang yang meninggal | manual_addition |

## S3973

> itik-itik, setelah kesepuluh kuku tangan dan kuku kaki dikerik, maka kedua jempol jari-jari tangan (ibu jari) diikat jadi satu dengan seutas tali benang tukelan.

| subject | relation | object | source |
|---|---|---|---|
| jempol jari tangan (kedua ibu jari) | `DIIKAT_DENGAN` | tali benang tukelan _(SARANA_RITUAL)_ | manual_addition |

## S3977

> umbi sikapa / sekapa (umbi gadung): jenazah disabuni (digosok) dengan umbi sikapa/sekapa, kemudian dibilas dengan air dan dikeringkan dengan kain kering.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DISABUNI_DENGAN` | umbi sikapa/sekapa _(SARANA_RITUAL)_ | dependency_rule |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIBILAS_DENGAN` | air | manual_addition |
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIKERINGKAN_DENGAN` | kain kering _(SARANA_RITUAL)_ | manual_addition |
| pemakaian umbi sikapa/sekapa | `BERMAKNA` | agar kulit orang yang meninggal putih bersih (jika numitis lagi) | manual_addition |

## S3984

> mewastra (berpakaian): setelah semuanya kering maka jenazah dikenakan pakaian putih-putih.

| subject | relation | object | source |
|---|---|---|---|
| jenazah _(ISTILAH_UMUM_RITUAL)_ | `DIPAKAIKAN` | pakaian putih-putih | dependency_rule |

## S4035

> ketiga, tirtha tersebut dipercikkan ke semua badan hingga ke kaki jenazah, setelah itu periuk tempat tirtha pangringkes tersebut dipecahkan dan dibuang di kolong bawah pepaga atau asagan.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `DIPERCIKKAN_PADA` | seluruh badan hingga ke kaki jenazah | manual_edit |
| priuk (tempat tirtha pangringkes) | `DIPECAHKAN` | (setelah tirtha dipercikkan) _(TIRTHA_SUCI)_ | manual_addition |
| priuk (yang pecah) | `DIBUANG_DI` | kolong bawah pepaga/asagan _(SARANA_RITUAL)_ | manual_addition |

## S4062

> tirtha ini digunakan untuk ngalukat (pembersihan tingkat awal) pada banten, pada adegan dan yang lainnya.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `DIPAKAI_UNTUK` | ngalukat | dependency_rule |
| ngalukat | `ADALAH` | pembersihan tingkat awal | object_decomposition |
| tirtha _(TIRTHA_SUCI)_ | `DIPAKAI_UNTUK` | adegan _(SARANA_RITUAL)_ | dependency_rule |
| tirtha _(TIRTHA_SUCI)_ | `DIPAKAI_UNTUK` | banten _(SARANA_RITUAL)_ | manual_edit |

## S4065

> tirtha pabersihan ini juga dibuat oleh ida sang sulinggih, yang pada akhekatnya tidak jauh berbeda dengan tirtha panglukatan, namun ada sedikit perbedaan yaitu dalam sarananya tidak memakai "samsam" serta puja yang dipakai berbeda dengan puja pada tirtha panglukatan, dan periuknya tanpa kalung benang dengan uang kepeng.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pabersihan _(TIRTHA_SUCI)_ | `DIBUAT_OLEH` | ida sang sulinggih _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| tirtha pabersihan _(TIRTHA_SUCI)_ | `TIDAK_MEMAKAI` | samsam (tidak seperti tirtha panglukatan) _(TIRTHA_SUCI)_ | manual_addition |
| tirtha pabersihan (periuknya) | `TANPA` | kalung benang dengan uang kepeng _(SARANA_RITUAL)_ | manual_addition |

## S4074

> tirtha ening berfungsi sebagai symbol dari pikiran dan perasaan sang yajamana (orang yang punya upacara), sehingga roh atau atman yang di upacarai tidak mengalami kegoncangan, sehingga dapat mencapai alam sorga dengan tenang.

| subject | relation | object | source |
|---|---|---|---|
| tirtha ening _(TIRTHA_SUCI)_ | `BERFUNGSI_SEBAGAI` | simbol pikiran dan perasaan sang yajamana (orang yang punya upacara) | manual_edit |
| roh atau atman _(KONSEP_FILOSOFIS)_ | `DAPAT_MENCAPAI` | alam sorga dengan tenang _(KONSEP_FILOSOFIS)_ | manual_addition |
| roh atau atman yang diupacarai _(KONSEP_FILOSOFIS)_ | `TIDAK_MENGALAMI` | kegoncangan | manual_addition |

## S4077

> tirtha pemanah adalah tirtha yang dibuat pada hari "pabersihan" atau juga disebut hari "pengaskaran" yang biasanya bersamaan dengan upacara "pamrasan".

| subject | relation | object | source |
|---|---|---|---|
| tirtha pemanah _(TIRTHA_SUCI)_ | `ADALAH` | tirtha yang dibuat pada hari " pabersihan " atau juga disebut hari " pengaskaran " yang biasanya bersamaan dengan upacara " pamrasan " | dependency_rule |

## S4079

> tirtha pemanah berbeda dengan tirtha-tirtha yang telah disebut diatas, karena tirtha pemanah seperti telah disebutkan diatas dibuat tepat pada waktu upacara "pengaskaran", sedangkan tirtha tersebut dibuat langsung oleh ida sang sulinggih.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pemanah _(TIRTHA_SUCI)_ | `BERBEDA_DENGAN` | tirtha-tirtha yang telah disebut diatas | dependency_rule |
| tirtha pemanah _(TIRTHA_SUCI)_ | `DIBUAT_SAAT` | upacara pengaskaran _(TAHAPAN_UPACARA)_ | manual_addition |

## S4082

> perlu diketahui bahwa tirtha pemanah ini hanya digunakan pada upacara pengabenan sawa wedana yang menggunakan "tumpang salu".

| subject | relation | object | source |
|---|---|---|---|
| tirtha pemanah _(TIRTHA_SUCI)_ | `DIPAKAI_UNTUK` | upacara pengabenan sawa wedana yang menggunakan " tumpang salu " | dependency_rule |

## S4086

> tirtha penembak ini adalah merupakan tirtha yang wajib dipersembahkan oleh "sang yajamana" atau orang yang memiliki upacara tersebut.

| subject | relation | object | source |
|---|---|---|---|
| tirtha penembak _(TIRTHA_SUCI)_ | `ADALAH` | tirtha yang wajib dipersembahkan oleh " sang yajamana " atau orang yang memiliki upacara tersebut | dependency_rule |

## S4087

> tirtha penembak ini juga memiliki hubungan herat dengan itihasa, tepatnya pada bisma parwa bagian dari mahabharata, yaitu ketika rsi bisma dalam keadaan sekarat karena luka parah oleh anak panah yang menembus badannya.

| subject | relation | object | source |
|---|---|---|---|
| tirtha penembak _(TIRTHA_SUCI)_ | `MEMILIKI` | hubungan erat dengan itihasa (Bisma Parwa, bagian dari Mahabharata) | manual_edit |

## S4090

> sedangkan cucunya yang dari pandawa, yaitu arjuna menyuguhkan air dengan cara memanah tanah yang berada disamping rsi bisma berbaring sehingga air mancur keluar dari tanah, dan langsung mengenai bibir rsi bisma yang sedang berbaring.

| subject | relation | object | source |
|---|---|---|---|
| air (dari tanah yang dipanah arjuna) | `MENGENAI` | bibir rsi bisma | manual_addition |
| arjuna _(ENTITAS_KEAGAMAAN)_ | `MEMANAH` | tanah (di samping rsi bisma) | manual_addition |

## S4096

> tirtha ini akan dibawa ke setra untuk dipergunakan pada waktu pembakaran,

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `DIBAWA_KE` | setra untuk dipergunakan pada waktu pembakaran | manual_edit |

## S4103

> tirtha kawitan ini dapat dimohon dari merajan kawitan atau merajan pusat dari orang yang meninggal.

| subject | relation | object | source |
|---|---|---|---|
| tirtha kawitan _(TIRTHA_SUCI)_ | `DIMOHON_DARI` | merajan kawitan _(KONSEP_FILOSOFIS)_ | dependency_rule |
| tirtha kawitan _(TIRTHA_SUCI)_ | `DIMOHON_DARI` | merajan pusat _(BANGUNAN_RITUAL)_ | dependency_rule |

## S4105

> tirtha ini akan dimohonkan oleh pemangku kawitan setempat, dimana terlebih dulu dipersiapkan sarana dan prasarana berupa pras, ajuman, daksina, suci serta rayunan dan kadang-kadang ditambah pajegan.

| subject | relation | object | source |
|---|---|---|---|
| sarana dan prasarana (upacara pemujaan) | `BERUPA` | pras, ajuman, daksina, suci, rayunan, dan kadang-kadang pajegan | manual_addition |
| tirtha _(TIRTHA_SUCI)_ | `DIMOHONKAN_OLEH` | pemangku kawitan setempat _(ENTITAS_KEAGAMAAN)_ | manual_addition |

## S4106

> tirtha ini memiliki fungsi sebagai sarana untuk mengucapkan permohonan pamit terhadap leluhur, agar nantinya dapat ikut masuk kealam kedewataan.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `MEMILIKI` | fungsi sarana untuk mengucapkan permohonan pamit terhadap leluhur , agar nanti nya dapat ikut masuk kealam kedewataan | dependency_rule |

## S4109

> tirtha kahyangan tiga ini dapat dimohon dari pura desa, pura puseh, pura dalem, pura mrajapti, karena dalam upacara ngaben belumlah lengkap tanpa tirtha kahyangan tiga dimana tempat orang yang meninggal itu berada.

| subject | relation | object | source |
|---|---|---|---|
| tirtha kahyangan tiga _(TIRTHA_SUCI)_ | `DIMOHON_DARI` | pura desa _(BANGUNAN_RITUAL)_ | dependency_rule |
| tirtha kahyangan tiga _(TIRTHA_SUCI)_ | `DIMOHON_DARI` | pura puseh _(BANGUNAN_RITUAL)_ | dependency_rule |
| tirtha kahyangan tiga _(TIRTHA_SUCI)_ | `DIMOHON_DARI` | pura dalem _(BANGUNAN_RITUAL)_ | dependency_rule |
| tirtha kahyangan tiga _(TIRTHA_SUCI)_ | `DIMOHON_DARI` | pura mrajapti _(BANGUNAN_RITUAL)_ | dependency_rule |

## S4110

> tirtha ini akan dimohonkan oleh pemangku kahyangan tiga setempat, dimana terlebih dulu dipersiapkan sarana dan prasarana berupa pras, ajuman, daksina, suci serta rayunan dan kadang-kadang ditambah pajegan.

| subject | relation | object | source |
|---|---|---|---|
| sarana dan prasarana (upacara pemujaan) | `BERUPA` | pras, ajuman, daksina, suci, rayunan, dan kadang-kadang pajegan | manual_addition |
| tirtha _(TIRTHA_SUCI)_ | `DIMOHONKAN_OLEH` | pemangku _(ENTITAS_KEAGAMAAN)_ | manual_addition |

## S4111

> tirtha ini memiliki fungsi sebagai sarana yang dapat mengantarkan agar roh orang yang meninggal mendapatkan tempat yang baik atau dalam kata lain roh tersebut tidak mengalami kesengsaraan.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `MEMILIKI` | fungsi sarana yang dapat mengantarkan agar roh orang yang meninggal mendapatkan tempat yang baik atau dalam kata lain roh tersebut tidak mengalami kesengsaraan | dependency_rule |

## S4112

> tirtha ini juga berfungsi sebagai sarana pengembalian roh (atma) kepada sang pencipta, karena pura kahyangan tiga adalah tempat pemujaan sang pencipta dalam fungsi sebagai utpeti, shtiti dan pralina.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `BERFUNGSI_SEBAGAI` | sarana pengembalian roh (atma) kepada sang pencipta | manual_edit |
| pura kahyangan tiga _(BANGUNAN_RITUAL)_ | `ADALAH` | tempat pemujaan sang pencipta | manual_edit |
| pura kahyangan tiga _(BANGUNAN_RITUAL)_ | `BERFUNGSI_SEBAGAI` | pralina _(TAHAPAN_UPACARA)_ | manual_addition |
| pura kahyangan tiga _(BANGUNAN_RITUAL)_ | `BERFUNGSI_SEBAGAI` | sthiti | manual_addition |
| pura kahyangan tiga _(BANGUNAN_RITUAL)_ | `BERFUNGSI_SEBAGAI` | utpeti _(KONSEP_FILOSOFIS)_ | manual_addition |

## S4116

> tirtha ini juga berguna sebagai sarana untuk meningkatkan kedudukan roh orang yang meninggal yang masih dalam tingkatan preta menjadi pitara.

| subject | relation | object | source |
|---|---|---|---|
| tirtha _(TIRTHA_SUCI)_ | `BERFUNGSI_SEBAGAI` | sarana untuk meningkatkan kedudukan roh orang yang meninggal yang masih dalam tingkatan preta menjadi pitara | dependency_rule |

## S4121

> oleh sebab itu tirtha pangentas dibuat di gria ida sang sulinggih atau dirumah atau ditempat upacara pengabenan dilaksanakan yaitu saat upacara pengaskaran yang kebetulan dilaksanakan bertepatan pada hari puncak pengabenan dilaksanakan.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `DIBUAT_DI` | gria ida sang sulinggih (kediaman pendeta) atau di rumah | manual_addition |
| tirtha pangentas _(TIRTHA_SUCI)_ | `DIBUAT_SAAT` | upacara pengaskaran (bertepatan dengan puncak upacara pengabenan) | manual_addition |

## S4126

> dari beberapa jenis-jenis tirtha penting yang diperlukan dan yang dipergunakan dalam upacara pengabenanan maka tirtha pangentas adalah tirtha yang paling terpenting dalam hal ini.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | tirtha dari beberapa jenis-jenis tirtha penting yang diperlukan dan yang dipergunakan dalam upacara pengabenanan yang paling terpenting dalam hal ini | dependency_rule |

## S4128

> sebab tirtha pangentas memiliki fungsi utama sebagai sarana untuk "ngentas" atau memberikan jalan dan membersihan noda-noda para roh atau atma orang yang meninggal agar dapat menuju ketempat yang lebih tinggi yaitu ke alam kedewataan sedangkan upacara pengabenan adalah merupakan upacara penyucikan roh atau atman (purusa) orang-orang yang telah meninggal agar terlepas dari ikatan panca mahabhuta (prakerti) sehingga lebih mudah dapat menuju ke alam dewa (swah loka).

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `MEMILIKI` | fungsi utama sebagai sarana untuk "ngentas": memberikan jalan dan membersihkan noda-noda roh atau atma orang yang meninggal, agar dapat menuju ke alam kedewataan | manual_edit |
| upacara pengabenan _(RITUAL_KEMATIAN)_ | `ADALAH` | upacara penyucian roh atau atman (purusa) orang yang telah meninggal, agar terlepas dari ikatan panca mahabhuta, sehingga dapat menuju alam dewa (swah loka) | manual_addition |

## S4167

> seperti telah disebutkan diatas bahwa tirtha pangentas adalah air suci gangga yang di mohonkan untuk menyucikan serta melepaskan ikatan roh dari ikatan-ikatan duniawi agar bisa meningkat menuju alam bhwah loka.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | air suci gangga yang di mohonkan untuk menyucikan serta melepaskan ikatan roh dari ikatan-ikatan duniawi agar bisa meningkat menuju alam bhwah loka | dependency_rule |

## S4169

> tirtha pangentas adalah seuatu yang memiliki arti yang erat dengan upacara pitra yadnya.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | sesuatu yang memiliki arti erat dengan upacara pitra yadnya | manual_edit |

## S4170

> karena tirtha pangentas adalah tirtha yang diharapkan dan diyakini sebagai alat atau sarana sangat penting bagi umat hindu, khususnya dalam hubungannya untuk dapat melepaskan roh para leluhur dari ikatan-ikatan keduniawian, sehingga para leluhur dapat bebas dan bisa meningkat menuju alam bhwah loka.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | tirtha yang diharapkan dan diyakini sebagai alat atau sarana sangat penting bagi umat hindu, khususnya dalam hubungannya untuk dapat melepaskan roh para leluhur dari ikatan-ikatan keduniawian, sehingga para leluhur dapat bebas dan bisa meningkat menuju alam bhwah loka | manual_edit |

## S4171

> seperti disebutkan diatas bahwa tirtha pangentas adalah air suci gangga yang diturunkan untuk menyucikan para leluhur.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | air suci gangga seperti disebutkan diatas yang diturunkan untuk menyucikan para leluhur | dependency_rule |

## S4175

> karena upacara mapulang lingga artinya "ngelinggihang lingga" dalam diri, atau dengan kata lain, bahwa tuhan atau brahman di-stanakan atau ditempatkan dalam diri sendiri.

| subject | relation | object | source |
|---|---|---|---|
| tuhan atau brahman _(ENTITAS_KEAGAMAAN)_ | `DITEMPATKAN` | diri | dependency_rule |
| upacara mapulang lingga | `BERARTI` | "ngelinggihang lingga" (dalam diri) _(TAHAPAN_UPACARA)_ | manual_addition |

## S4177

> atma lingga adalah mewujudkan sanghyang ongkans dan tri aksara dalam diri yang berstana dalam bathin.

| subject | relation | object | source |
|---|---|---|---|
| atma lingga _(KONSEP_FILOSOFIS)_ | `MEWUJUDKAN` | sanghyang ongkara dan tri aksara dalam diri (yang berstana dalam bathin) | manual_addition |

## S4192

> seperti telah diuraikan di atas bahwa tirtha pangentas adalah sesunguhnya tirtha gangga yang diturunkan atau dibuat oleh pendeta atau sang sulinggih.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | tirtha gangga yang diturunkan atau dibuat oleh pendeta/sang sulinggih | manual_edit |

## S4212

> setelah itu dilakukan amrethi karana, yaitu mengucurkan tirtha amertha dalam diri sehingga abu abu kekototan musnah dan badan mulai bersinar bagaikan matahari.

| subject | relation | object | source |
|---|---|---|---|
| abu abu kekototan (kekotoran) _(SARANA_RITUAL)_ | `MUSNAH` | melalui ritual amrethi karana | manual_addition |
| amrethi karana | `DILAKUKAN_DENGAN` | mengucurkan tirtha amertha dalam diri _(KONSEP_FILOSOFIS)_ | manual_addition |
| badan | `BERSINAR_BAGAIKAN` | matahari | manual_addition |

## S4266

> sebelum pramakusa dimasukkan dalam priuk maka terlebih dulu di mantrai.

| subject | relation | object | source |
|---|---|---|---|
| pramakusa _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | priuk | dependency_rule |
| pramakusa _(SARANA_RITUAL)_ | `DIMANTRAI` | sebelum dimasukkan ke dalam priuk | manual_addition |

## S4273

> setelah itu padang lepas dimasukan ke dalam periuk tadi, dan selanjutnya sarana-sarana yang lainnya juga seperti biji padi (jijih), pripih emas, recadana, ulantaga, kalpika juga dimasukkan kedalam periuk tadi yang sebelumnya terlebih dulu masing-masing sarana tersebut dimantrai oleh ida sang sulinggih.

| subject | relation | object | source |
|---|---|---|---|
| kalpika _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | periuk | dependency_rule |
| jijih (biji padi) | `DIMASUKKAN_KE_DALAM` | periuk | manual_addition |
| padang lepas _(SARANA_RITUAL)_ | `DIMASUKKAN_KE_DALAM` | periuk | manual_addition |
| pripih emas | `DIMASUKKAN_KE_DALAM` | periuk | manual_addition |
| recadana | `DIMASUKKAN_KE_DALAM` | periuk | manual_addition |
| sarana-sarana tersebut | `DIMANTRAI_OLEH` | ida sang sulinggih (sebelum dimasukkan) _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| ulantaga | `DIMASUKKAN_KE_DALAM` | periuk | manual_addition |

## S4300

> pretiwi sangkaning ganda mulih ring pretiwi,

| subject | relation | object | source |
|---|---|---|---|
| ganda _(KONSEP_FILOSOFIS)_ | `BERASAL_DARI` | pretiwi _(KONSEP_FILOSOFIS)_ | manual_addition |
| ganda _(KONSEP_FILOSOFIS)_ | `KEMBALI_KE` | pretiwi _(KONSEP_FILOSOFIS)_ | manual_addition |

## S4301

> apah sangkaning rasa.

| subject | relation | object | source |
|---|---|---|---|
| rasa _(KONSEP_FILOSOFIS)_ | `BERASAL_DARI` | apah _(KONSEP_FILOSOFIS)_ | manual_addition |

## S4303

> teja sangkaning rupa mulih maring teja,

| subject | relation | object | source |
|---|---|---|---|
| rupa _(KONSEP_FILOSOFIS)_ | `BERASAL_DARI` | teja _(KONSEP_FILOSOFIS)_ | manual_addition |
| rupa _(KONSEP_FILOSOFIS)_ | `KEMBALI_KE` | teja _(KONSEP_FILOSOFIS)_ | manual_addition |

## S4304

> bayu sangkaning ambekan mulih maring bayu.

| subject | relation | object | source |
|---|---|---|---|
| ambekan _(KONSEP_FILOSOFIS)_ | `KEMBALI_KE` | bayu _(KONSEP_FILOSOFIS)_ | manual_addition |
| ambekan _(KONSEP_FILOSOFIS)_ | `BERASAL_DARI` | bayu _(KONSEP_FILOSOFIS)_ | manual_addition |

## S4305

> akasa sangkaning sabda mulih maring akasa,

| subject | relation | object | source |
|---|---|---|---|
| sabda _(KONSEP_FILOSOFIS)_ | `BERASAL_DARI` | akasa _(KONSEP_FILOSOFIS)_ | manual_addition |
| sabda _(KONSEP_FILOSOFIS)_ | `KEMBALI_KE` | akasa _(KONSEP_FILOSOFIS)_ | manual_addition |

## S4336

> seperti telah disebutkan diatas bahwa tirtha pangentas merupakan tirtha yang terpenting dalam upacara pengabenan, karena tanpa tirtha pangentas maka pengabenan itu dianggap belum dilaksanakan.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | tirtha yang terpenting dalam upacara pengabenan | dependency_rule |
| pengabenan (tanpa tirtha pangentas) | `DIANGGAP` | belum dilaksanakan | manual_addition |

## S4337

> karena kenyataannya tirtha pangentas memiliki nilai filosofis yang sangat tinggi sekali yaitu :

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `MEMILIKI` | nilai filosofis yang sangat tinggi sekali | dependency_rule |

## S4338

> tirtha pangentas secara filosofis adalah sebagai alat sangaskara atau penyucian kepada roh atau atman orang yang telah meninggal dunia, sehingga roh atau atman tersebut kedudukannya menjadi terangkat, yaitu dari roh yang tingkatannya masih preta (atman yang disebut antah karana sarira yang masih terikat suksma sarira/sifat keduniawian) menjadi pitara, sehingga bisa memasuki alam bwah loka yaitu sebagai tumpuan untuk menuju ke alam swah loka.

| subject | relation | object | source |
|---|---|---|---|
| pitara _(KONSEP_FILOSOFIS)_ | `DAPAT_MEMASUKI` | alam bwah loka (tumpuan menuju alam swah loka) | manual_addition |
| roh atau atman (orang yang telah meninggal) _(KONSEP_FILOSOFIS)_ | `NAIK_KEDUDUKAN_DARI` | preta menjadi pitara _(ENTITAS_KEAGAMAAN)_ | manual_addition |
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | alat sangaskara atau penyucian kepada roh atau atman orang yang telah meninggal dunia | manual_addition |

## S4339

> tirtha pangentas secara filosofis adalah sebagai lambang penunjuk jalan bagi roh atau atman untuk kembali ke asalnya yaitu brahman atau alam swah loka, nan sebagai tujuan terakhir.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `ADALAH` | lambang penunjuk jalan bagi roh atau atman untuk kembali ke asalnya (brahman/alam swah loka) sebagai tujuan terakhir | manual_edit |

## S4340

> tirtha pangentas secara filosofis adalah berfungsi sebagai pelebur unsur karma wasana yang mengikat roh atau atman, yang disebut "ngentas" atma atau ulub roh.

| subject | relation | object | source |
|---|---|---|---|
| tirtha pangentas _(TIRTHA_SUCI)_ | `BERFUNGSI_SEBAGAI` | pelebur unsur karma wasana yang mengikat roh atau atman _(KONSEP_FILOSOFIS)_ | manual_edit |
| pelebur unsur karma wasana | `DIKENAL_SEBAGAI` | ngentas atma | object_decomposition |
| pelebur unsur karma wasana | `DIKENAL_SEBAGAI` | ulub roh | object_decomposition |


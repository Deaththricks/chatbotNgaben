"""Regenerate data/nlu.yml: the intents that route a question (plan #13, 2026-10-13).

Run from Chatbot/bot/:  python scripts/gen_nlu.py
Reads KB_DIR (.env) or defaults to ../../Graphing/kb.

The NLU decides only WHICH KIND of question a message is; the term itself is found by
kb_resolver in actions.py, so no entity is annotated. Each simple intent's template answers it
with no LLM call (ActionTemplateAnswer); tanya_kompleks goes to the LLM pipeline (ActionGraphRAG).

The frames below are the hand-written part: formal, casual and short follow-up forms of each
question. "{t}" (and "{u}" for a second term) is filled from one fixed set of KB names (seeded),
and every intent cycles through ALL of them, so a name never hints at an intent -- the classifier
has to learn the question words. Drawing each fill from every KB name instead tied a rare name to
the one intent it happened to land in: "banten pamegat itu lambang dari apa" made "apa itu banten
pamegat" a tanya_makna question at 1.00 (Tier B 2026-10-13). Edit the frames here, not data/nlu.yml.
"""
import hashlib
import json
import os
import random
import re
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

BOT_DIR = Path(__file__).resolve().parent.parent
KB_DIR = (BOT_DIR / os.getenv("KB_DIR", "../../Graphing/kb")).resolve()
OUT = BOT_DIR / "data" / "nlu.yml"
FILLS_PER_FRAME = 2
# names in the fill set: every intent uses each of them at least once
NAME_SET_SIZE = 72
# names of the set given bare as definition questions: with only the "{t}" / "{t}?" frames' few
# fills, one retrain sent a bare "patulangan" to nlu_fallback (2026-10-14)
BARE_NAMES = 36

# names that are themselves question or aspect words would teach the classifier the wrong thing
_ASPECT_NAME_WORDS = frozenset("""
apa siapa mana kapan berapa bagaimana makna arti fungsi tujuan peran jenis macam tahapan tahap urutan
isi bahan komponen unsur sarana nama sebutan waktu tempat hari cara proses bagian asal kata tingkat
warna bentuk hubungan beda alasan lontar sumber
""".split())

SAPA = """
halo
hai
hi
hey
halo kak
hai min
halo admin
pagi
selamat pagi
selamat siang
selamat sore
selamat malam
permisi
om swastiastu
om swastyastu
om swastiastu, saya mau bertanya
halo, saya mau tanya
permisi, mau tanya
saya mau bertanya
boleh tanya?
mau tanya dong
""".split("\n")

PAMIT = """
dah
dadah
bye
sampai jumpa
sampai jumpa lagi
sampai ketemu lagi
terima kasih
terima kasih ya
terima kasih banyak
terima kasih atas penjelasannya
matur suksma
makasih
makasih ya
makasih banyak ya
terimakasih banyak
thanks
thanks ya
thank you
oke makasih
sudah cukup, terima kasih
cukup dulu
itu saja dulu
oke saya paham
baik, saya sudah paham
om santih santih santih om
om shanti shanti shanti om
""".split("\n")

BOT_CHALLENGE = """
kamu bot ya?
kamu bot?
apakah kamu bot
apakah saya bicara dengan robot?
kamu manusia atau mesin?
kamu manusia atau robot?
kamu ini siapa
siapa kamu
kamu siapa sih
kamu AI?
apakah kamu chatbot?
ini chatbot atau orang beneran?
siapa yang membuat kamu
kamu dibuat siapa
kamu bisa bantu apa saja?
apa saja yang bisa kamu jawab?
kamu bisa menjawab apa?
""".split("\n")

DIGIDAW = """
digidaw
Digidaw
DIGIDAW
digidaw!
digidaww
digidaw digidaw
""".split("\n")

# Off-topic only (Tier A checks that none of these names a KB term outright). Question words are
# in every intent on purpose: with every "bagaimana ..." example here, "bagaimana proses ngaben"
# was classified out_of_scope (conersation.md 2026-09-29).
OUT_OF_SCOPE = """
cuaca hari ini
cuaca besok bagaimana
resep lawar bali
siapa presiden indonesia
jam berapa sekarang
berikan aku resep nasi goreng
apa itu machine learning
ceritakan lelucon
berapa harga tiket pesawat ke bali
apa itu python programming
bagaimana cara membuat kue coklat
bagaimana cara membuat nasi goreng
bagaimana cara memperbaiki motor
siapa pemenang piala dunia terakhir
rekomendasikan film bagus
berapa jarak jakarta ke bali
kapan pertandingan sepak bola berikutnya
bagaimana cara belajar bahasa inggris
rekomendasi hotel murah di kuta
berapa kurs dolar hari ini
bagaimana cara install windows
apa hasil pemilu kemarin
jika x=2, berapa hasil dari 2x+x^2
berapa 15 dikali 8
hitung 125 dibagi 5
berapa 12 tambah 5
3 ditambah 4 berapa
berapa 20 dikurangi 7
50 dibagi 2 sama dengan berapa
berapa hasil 9 kali 9
siapa itu pewdiepie
siapa penemu lampu pijar
di mana letak menara eiffel
kapan indonesia merdeka
apa fungsi ram di komputer
bagaimana cara daftar kuliah
""".split("\n")

# simple-question intents: frames with {t}, then follow-ups that point back at the topic
FRAMES = {
    "tanya_definisi": """
apa itu {t}
apa itu {t}?
{t} itu apa
{t} itu apa?
{t} itu apa sih
{t} tuh apaan
{t} tuh apa ya
apaan sih {t}
apa sih {t} itu
apa yang dimaksud dengan {t}
apa yang dimaksud {t}?
yang dimaksud {t} itu apa
apa pengertian {t}
pengertian {t}
pengertian dari {t} apa
apa definisi {t}
definisi {t}
jelaskan {t}
jelaskan tentang {t}
tolong jelaskan {t}
bisa jelaskan {t}?
coba jelasin {t} dong
terangkan apa itu {t}
maksudnya {t} apa?
{t} maksudnya apa
apa arti {t}
{t} artinya apa
saya ingin tahu tentang {t}
aku mau tau {t} itu apa
kasih tau dong {t} itu apa
{t}?
{t}
apa sebenarnya {t}
{t} itu sebenarnya apa
saya kurang paham {t} itu apa
bisa kasih penjelasan soal {t}?
min, {t} itu apa ya?
kak, apa itu {t}?
siapa itu {t}
cari istilah {t}
""",
    "tanya_makna": """
apa makna {t}
apa makna dari {t}?
makna {t} apa
{t} maknanya apa
apa makna simbolis {t}
apa arti simbolis {t}
{t} melambangkan apa
apa yang dilambangkan oleh {t}
{t} itu lambang dari apa
{t} simbol dari apa
apa simbolisme {t}
apa filosofi {t}
filosofi di balik {t} apa
makna filosofis {t} apa
{t} itu menyimbolkan apa
jelaskan makna {t}
tolong jelaskan makna {t}
maknanya {t} apa ya
apa maksud simbolis dari {t}
{t} punya makna apa
sebenarnya {t} bermakna apa
apa yang disimbolkan {t}
lambang {t} apa
makna {t} dalam upacara itu apa
""",
    "tanya_fungsi": """
apa fungsi {t}
fungsi {t} apa
{t} fungsinya apa
apa kegunaan {t}
kegunaan {t} apa
{t} gunanya apa
{t} itu buat apa
{t} untuk apa
{t} dipakai untuk apa
{t} digunakan untuk apa
untuk apa {t}
apa tujuan {t}
tujuan {t} apa
{t} bertujuan untuk apa
apa peran {t}
peran {t} apa
apa manfaat {t}
{t} berfungsi sebagai apa
jelaskan fungsi {t}
{t} itu gunanya buat apa sih
apa tujuan dilakukannya {t}
buat apa ada {t}
{t} dipake buat apa
peranan {t} apa
{t} itu untuk apa
{t} untuk apa ya
""",
    "tanya_jenis": """
apa saja jenis {t}
jenis {t} apa saja
ada berapa jenis {t}
ada berapa macam {t}
macam-macam {t}
sebutkan jenis-jenis {t}
{t} ada jenis apa aja
{t} ada berapa jenis
contoh {t} apa saja
apa saja macam {t}
jenis-jenis {t}
ragam {t} apa saja
{t} terbagi menjadi apa saja
klasifikasi {t}
apa aja jenis {t}
tipe {t} apa saja
""",
    "tanya_tahapan": """
apa saja tahapan {t}
tahapan {t} apa saja
bagaimana tahapan {t}
sebutkan tahapan {t}
urutan {t} bagaimana
bagaimana urutan {t}
bagaimana proses {t}
bagaimana prosesi {t}
proses {t} seperti apa
rangkaian {t} apa saja
bagaimana alur {t}
alur {t} gimana
langkah-langkah {t}
bagaimana cara melakukan {t}
bagaimana {t} dilaksanakan
bagaimana tata cara {t}
tata cara {t}
jelaskan tahapan {t}
jelaskan proses {t} dari awal sampai akhir
{t} prosesnya gimana
{t} tahapannya apa aja
apa saja rangkaian upacara {t}
tahap-tahap {t}
bagaimana pelaksanaan {t}
bagaimana cara membuat {t}
bagaimana {t} disiapkan
""",
    "tanya_komponen": """
{t} terbuat dari apa
{t} dibuat dari apa
apa bahan {t}
bahan {t} apa saja
apa saja bahan untuk membuat {t}
apa isi {t}
isi {t} apa saja
{t} isinya apa aja
{t} berisi apa
{t} terdiri dari apa
{t} terdiri dari apa saja
apa saja komponen {t}
komponen {t} apa saja
apa saja unsur {t}
unsur-unsur {t}
{t} dilengkapi apa
kelengkapan {t} apa saja
apa yang ada di dalam {t}
apa saja yang dibutuhkan untuk membuat {t}
bagian-bagian {t} apa saja
{t} pakai bahan apa
rincian bahan {t}
{t} tersusun dari apa
""",
    "tanya_sarana": """
apa saja sarana {t}
sarana {t} apa saja
sarana apa yang dipakai dalam {t}
sarana upacara {t}
apa saja sarana upacara yang digunakan dalam {t}
perlengkapan {t} apa saja
apa saja perlengkapan untuk {t}
upakara apa saja yang digunakan dalam {t}
alat apa saja yang dipakai saat {t}
sesajen apa yang dipakai di {t}
apa yang perlu disiapkan untuk {t}
{t} butuh sarana apa aja
{t} pakai sarana apa
apa saja yang digunakan dalam {t}
sarananya {t} apa
banten apa yang dipakai saat {t}
""",
    "tanya_lokasi": """
di mana {t} dilakukan
dimana {t} dilaksanakan
{t} dilakukan di mana
{t} diletakkan di mana
di mana letak {t}
letak {t} di mana
tempat {t} di mana
{t} ditaruh di mana
ke mana {t} dibawa
{t} dibawa ke mana
dari mana {t} diperoleh
{t} didapat dari mana
di mana {t} ditempatkan
lokasi {t} di mana
{t} itu di mana
{t} diadakan di mana
{t} dimasukkan ke dalam apa
{t} ditempelkan di mana
""",
    "tanya_waktu": """
kapan {t} dilakukan
kapan {t} dilaksanakan
{t} dilakukan kapan
{t} diadakan kapan
kapan waktu {t}
waktu pelaksanaan {t}
{t} dilakukan pada saat apa
{t} dilakukan setelah apa
{t} dilakukan sebelum apa
kapan {t} digunakan
{t} dipakai kapan
saat apa {t} digunakan
kapan biasanya {t}
{t} itu kapan
""",
    "tanya_pelaku": """
siapa yang memimpin {t}
{t} dipimpin oleh siapa
siapa yang melakukan {t}
{t} dilakukan oleh siapa
siapa yang membuat {t}
{t} dibuat oleh siapa
siapa pelaku {t}
siapa saja yang terlibat dalam {t}
siapa yang berperan dalam {t}
siapa yang bertugas saat {t}
siapa yang memuput {t}
{t} dipuput oleh siapa
oleh siapa {t} dilaksanakan
siapa yang mengerjakan {t}
yang mimpin {t} siapa
""",
    "tanya_sebutan_lain": """
apa nama lain {t}
nama lain {t} apa
{t} disebut juga apa
apa sebutan lain untuk {t}
sebutan lain {t}
{t} dikenal juga sebagai apa
istilah lain untuk {t}
sinonim {t}
{t} sering disebut apa lagi
apa sebutan halus {t}
{t} punya nama lain?
""",
    "tanya_asal_kata": """
apa arti kata {t}
arti kata {t}
{t} berasal dari kata apa
asal kata {t}
dari mana asal kata {t}
apa asal usul istilah {t}
{t} secara harfiah berarti apa
etimologi {t}
kata dasar {t} apa
apa makna kata {t}
istilah {t} berasal dari mana
apa arti dari kata {t}
asal-usul nama {t}
arti harfiah {t}
""",
    "tanya_bagian_dari": """
{t} termasuk bagian dari apa
{t} bagian dari apa
{t} termasuk apa
{t} termasuk jenis apa
{t} termasuk dalam upacara apa
{t} termasuk kategori apa
{t} masuk kelompok apa
{t} merupakan bagian dari upacara apa
{t} digunakan dalam upacara apa
{t} dipakai di upacara apa
induk dari {t} apa
{t} masuk ke dalam rangkaian apa
{t} termasuk tahapan dari apa
{t} itu bagian dari ritual apa
{t} jenis dari apa
""",
}

FOLLOW_UPS = {
    "tanya_definisi": ["itu apa?", "itu maksudnya apa?", "apa itu tadi?"],
    "tanya_makna": ["apa maknanya?", "maknanya apa?", "lalu maknanya apa?", "terus maknanya?",
                    "itu melambangkan apa?", "apa makna dari itu?", "apa filosofinya?", "simbolnya apa?"],
    "tanya_fungsi": ["apa fungsinya?", "fungsinya apa?", "gunanya apa?", "tujuannya apa?", "itu buat apa?",
                     "untuk apa itu?", "perannya apa?"],
    "tanya_jenis": ["jenisnya apa saja?", "ada berapa jenisnya?", "macamnya apa aja?", "contohnya apa?"],
    "tanya_tahapan": ["apa saja tahapannya?", "tahapannya apa aja?", "prosesnya bagaimana?", "urutannya gimana?",
                      "caranya bagaimana?"],
    "tanya_komponen": ["isinya apa aja?", "terbuat dari apa?", "terbuat dari apa itu", "bahannya apa?",
                       "terdiri dari apa saja?", "komponennya apa?"],
    "tanya_sarana": ["apa saja sarananya?", "apa saja sarananya", "sarananya apa aja?", "perlengkapannya apa?"],
    "tanya_lokasi": ["di mana tempatnya?", "letaknya di mana?", "dilakukan di mana?", "diletakkan di mana?"],
    "tanya_waktu": ["kapan dilakukannya?", "kapan itu dilakukan?", "waktunya kapan?", "dilakukan kapan?"],
    "tanya_pelaku": ["siapa yang melakukannya?", "dipimpin siapa?", "siapa pelakunya?", "siapa yang membuatnya?"],
    "tanya_sebutan_lain": ["nama lainnya apa?", "sebutan lainnya apa?", "disebut juga apa?"],
    "tanya_asal_kata": ["asal katanya apa?", "arti katanya apa?"],
    "tanya_bagian_dari": ["itu bagian dari apa?", "termasuk upacara apa?"],
}

# The questions answered before plan #13 (the old ask_ngaben_detail examples), filed by kind
FIXED = {
    "tanya_definisi": """
apa itu ngaben
jelaskan tentang tirtha pangentas
panca maha butha itu apa
apa itu upacara ngaskara
apa itu daksina tapakan
apa itu tirtha kawitan
apa itu wuku kuningan
apa itu caru pengelambuk
apa itu sorohan
akasa itu apa
apa itu bali dataran
apa itu upacara ngerorasin
apa itu sasih kaenem
apa itu nglungah
apakah sekah
apakah itu lembu
apakah tirtha pangentas itu
""",
    "tanya_makna": "nganyut melambangkan apa\napa makna banten\n",
    "tanya_fungsi": "bade dipakai untuk apa\napa peran tirtha dalam pengabenan\n",
    "tanya_jenis": "ada berapa macam ngaben\n",
    "tanya_tahapan": """
sebutkan tahapan upacara ngaben
bagaimana proses ngaben
bagaimana alur prosesi ngaben pada umumnya
bagaimana cara nyiramang layon
bagaimana tata cara nganyut
bagaimana urutan upacara atma wedana
bagaimana cara membuat tirtha pangentas
bagaimana jenazah disucikan
bagaimana layon dibersihkan
bagaimana cara memandikan jenazah
bagaimana abu jenazah dihanyutkan
""",
    "tanya_komponen": "pripih emas terbuat dari apa\n",
    "tanya_sarana": """
apa saja sarana upacara yang digunakan untuk ngaben
banten apa saja yang dipakai saat pabersihan mati
sarana apa yang dipakai untuk nyiramang layon
""",
    "tanya_lokasi": "di mana sekah diletakkan\n",
    "tanya_waktu": "nganyut dilakukan kapan\n",
    "tanya_pelaku": "siapa yang memandikan layon\n",
}

# Everything else goes to the LLM: two or more terms, two questions in one, why, yes/no, may/must,
# what-if-not, scenarios, counts and forms, sources, days, narration, order, earlier items.
KOMPLEKS_FRAMES = """
apa hubungan {t} dan {u}
apa hubungan antara {t} dengan {u}
apa kaitan {t} dengan {u}
bagaimana hubungan {t} dengan {u}
{t} berhubungan dengan {u} bagaimana
apa perbedaan {t} dan {u}
apa bedanya {t} sama {u}
bedanya {t} dan {u} apa
{t} dan {u} itu sama atau beda
apa itu {t} dan apa maknanya
apa itu {t} dan apa fungsinya
apa itu {t} dan bagaimana prosesnya
apa itu {t}, dari mana diperoleh, dan apa fungsinya
jelaskan {t} dan {u}
apa itu {t} dan {u}
kenapa {t} harus dilakukan
mengapa {t} digunakan dalam {u}
kenapa {t} dibakar
apa alasan {t} dilakukan
kenapa harus ada {t}
kenapa disebut {t}
apakah {t} boleh dilakukan saat {u}
apakah {t} wajib
apakah {t} harus dilakukan dalam tujuh hari
bolehkah {t} dilakukan pada {u}
{t} boleh gak dilakukan pas {u}
kalau tidak melakukan {t} apa akibatnya
apa yang terjadi kalau {t} tidak dilakukan
kalo gak {t} gimana
{t} tanpa {u} bisa gak
apa yang terjadi jika {t} dilakukan tanpa {u}
berapa tingkat {t}
berapa jumlah {t} yang dipakai
apa warna {t}
bentuk {t} seperti apa
{t} dijelaskan dalam lontar apa
lontar apa yang membahas {t}
ceritakan {t} dari awal sampai akhir
uraikan tentang {t} secara lengkap
ceritakan proses {t}
ceritakan prosesi {t} secara runtut
uraikan proses {t} dari awal
ceritakan bagaimana {t} berlangsung
hari baik untuk {t} kapan
hari apa yang harus dihindari untuk {t}
sasih apa yang baik untuk {t}
apa tahapan setelah {t}
apa yang dilakukan setelah {t}
{t} dilakukan sebelum atau sesudah {u}
apa makna {t} tingkat 9
kenapa {t} ada yang bertingkat 11
apakah {u} juga dipakai dalam {t}?
apa ketentuan penggunaan {t}
aturan pemakaian {t} bagaimana
apa syarat melakukan {t}
apa larangan saat {t}
"""

KOMPLEKS_FIXED = """
kenapa tidak boleh menangis saat ngaben
apa hubungan sekah dan pitra
apa beda bade dan wadah
itu panjangnya berapa
kenapa begitu
maksudnya gimana
bagaimana jenazah dibungkus saat pangringkes
bagaimana hubungan sasih dengan ngaben
berapa tingkat bade untuk raja
berapa harga upacara ngaben
kenapa tirtha ada harganya
berapa uang kepeng dalam gegaleng
kapan ngaben boleh dilaksanakan
hari baik apa yang cocok untuk ngaben
sasih apa yang baik untuk pitra yadnya
kenapa sasih malamasa harus dihindari
apakah bade boleh dipakai masyarakat umum
apakah ngaben harus dilakukan dalam tujuh hari
apakah hal tersebut tidak boleh
apakah ngaben wajib
bolehkah ngaben dilakukan pada sasih kadasa
hanya itu sarananya?
itu saja?
kenapa bade ada yang bertingkat 11
apa itu wangsa dan apa hubungannya dengan ngaben
jadi, kenapa tidak boleh?
kenapa itu harus dihindari?
kenapa orang bali membakar mayat
mengapa jenazah dibakar
kenapa mayat harus dibakar
kenapa umat hindu di bali membakar jenazah
mengapa orang meninggal di bali dikremasi
apa alasan jenazah dibakar dalam ngaben
yang kedua itu apa maksudnya
yang pertama tadi apa artinya
jelaskan keduanya
apa bedanya keduanya
emang kalau nggak ngaben kenapa?
kalao misalnya di bali tidak ngaben bagaimana
keluarga saya meninggal di perantauan dan jenazahnya tidak bisa dibawa pulang, upacaranya bagaimana
kakek sudah lama dikubur, sekarang tulangnya mau diupacarai, namanya apa
anak umur 4 bulan meninggal, perlu dibuatkan upacara apa
kalau di desa cuma ada pemangku, ngabennya tetep bisa jalan gak?
ngaben pas purnama boleh gak?
bayi yang giginya belum tanggal boleh dibakar?
apa yang harus dilakukan keluarga pertama kali saat ada yang meninggal
"""


def lines(block):
    return [x.strip() for x in block.strip().splitlines() if x.strip()]


def term_pool():
    ents = json.loads((KB_DIR / "output" / "entities.json").read_text(encoding="utf-8"))
    pool = set()
    for e in ents:
        n = e["name"].strip().lower()
        words = n.split()
        if (1 <= len(words) <= 3 and 3 <= len(n) <= 30 and re.fullmatch(r"[a-z][a-z' -]*", n)
                and not _ASPECT_NAME_WORDS & set(words)):
            pool.add(n)
    return sorted(pool)


def stable_sample(pool, k):
    """k names picked by a hash of each name, not by their position in the pool: a node added to the
    KB changes the set only when its own hash ranks among the first k, so a KB pass mostly leaves
    nlu.yml as it was. rng.sample(pool, k) drew a new set whenever the pool grew -- the 23 nodes of
    2026-10-14 rewrote 1,500 of nlu.yml's 1,760 lines, and a retrain on it moves the near-tie
    messages."""
    return sorted(pool, key=lambda n: hashlib.sha1(n.encode("utf-8")).hexdigest())[:k]


def fill_intent(frames, rng, names):
    """The intent's examples: its frames in turn, at least FILLS_PER_FRAME each and until every name
    of the set has been used, names taken from the set in a shuffled cycle."""
    order = names[:]
    rng.shuffle(order)
    slots = max(FILLS_PER_FRAME * len(frames), len(names))
    examples, k = [], 0

    def name():
        nonlocal k
        if k and k % len(order) == 0:
            # a new round in another order: with as many frames as names, the same order paired every
            # frame with the same name again
            rng.shuffle(order)
        n = order[k % len(order)]
        k += 1
        # some users capitalize their terms
        return n.title() if rng.random() < 0.2 else n
    for i in range(slots):
        frame = frames[i % len(frames)]
        t = name()
        u = name() if "{u}" in frame else ""
        examples.append(frame.replace("{t}", t).replace("{u}", u))
    return examples


def block(intent, examples):
    seen, out = set(), []
    for x in examples:
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    body = "\n".join(f"    - {x}" for x in out)
    return f"- intent: {intent}\n  examples: |\n{body}\n", len(out)


def main():
    rng = random.Random(13)
    pool = term_pool()
    # the KB names the fixed examples use join the set, so each is in every intent too: with
    # "bagaimana jenazah dibungkus saat pangringkes" only in tanya_kompleks, "apa itu pangringkes" was
    # tanya_kompleks at 1.00 (Tier B 2026-10-13)
    fixed_text = " ".join([KOMPLEKS_FIXED] + list(FIXED.values())).lower()
    fixed_names = [n for n in pool if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", fixed_text)]
    names = list(dict.fromkeys(stable_sample(pool, NAME_SET_SIZE) + fixed_names))
    parts, counts = [], {}
    for intent, examples in [("sapa", SAPA), ("pamit", PAMIT), ("bot_challenge", BOT_CHALLENGE),
                             ("digidaw", DIGIDAW), ("out_of_scope", OUT_OF_SCOPE)]:
        text, counts[intent] = block(intent, [x.strip() for x in examples])
        parts.append(text)
    for intent, frames in FRAMES.items():
        examples = fill_intent(lines(frames), rng, names)
        examples += FOLLOW_UPS[intent] + lines(FIXED.get(intent, ""))
        if intent == "tanya_definisi":
            examples += names[:BARE_NAMES]
        text, counts[intent] = block(intent, examples)
        parts.append(text)
    examples = fill_intent(lines(KOMPLEKS_FRAMES), rng, names)
    examples += lines(KOMPLEKS_FIXED)
    text, counts["tanya_kompleks"] = block("tanya_kompleks", examples)
    parts.append(text)
    OUT.write_text(
        "# AUTO-GENERATED by scripts/gen_nlu.py -- edit the frames there, not this file.\n"
        'version: "3.1"\nnlu:\n' + "".join(parts), encoding="utf-8")
    print(f"wrote {OUT} ({sum(counts.values())} examples, names: {', '.join(names)})")
    for intent, n in counts.items():
        print(f"  {intent:20} {n}")


if __name__ == "__main__":
    main()

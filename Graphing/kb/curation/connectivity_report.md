# Connectivity audit report

Source: relation_results_ngaben.normalized.json (1020 rows), entities.json (547 entities)

Read the module docstring before acting on anything here -- every
line is a candidate, not a verdict.

## Mixed ENTITY/LITERAL sibling groups (23)

Same sentence+subject+relation, some siblings already ENTITY, some
still LITERAL -- the LITERAL ones are invisible to the bot/graph.

- S124 `bali dataran` -MENGGUNAKAN-> ENTITY: ['bade', 'patulangan'] | LITERAL: ['sarana mewah']
- S265 `tegteg` -DILETAKKAN_DI-> ENTITY: ['tumpang salu'] | LITERAL: ['bungkusan tulang belulang']
- S271 `tirta yadnya pranawa` -ADALAH-> ENTITY: ['atiwa-tiwa'] | LITERAL: ['istilah lain untuk raçadana dalam kategori ngaben svasta, yaitu ngaben yang sawanya diganti dengan simbol tirtha (toyo çarira) karena jenazah tidak dapat ditemukan, dengan tata pelaksanaan yang sama dengan atiwa-tiwa asti vedana']
- S354 `pepaga` -TERBUAT_DARI-> ENTITY: ['hitungan galar', 'hitungan galir', 'hitungan galur', 'hitungan likah', 'hitungan wangke', 'hitungan wangkong'] | LITERAL: ['bambu']
- S1465 `jun pere` -BERISI-> ENTITY: ['alang-alang', 'sembilan batang kayu cendana'] | LITERAL: ['air']
- S1468 `upakara` -DISUCIKAN_DENGAN-> ENTITY: ['tirtha panglukatan'] | LITERAL: ['sajen']
- S1474 `sesajen` -MELIPUTI-> ENTITY: ['diuskamaligi', 'nasi angkeb'] | LITERAL: ['saji']
- S1717 `adegan` -ADALAH-> ENTITY: ['tempat atma mendiang'] | LITERAL: ['alat upakara']
- S1738 `mendiang` -ADALAH-> ENTITY: ['pemangku'] | LITERAL: ['pejabat', 'sastrawan']
- S1783 `mendiang` -MENYERAHKAN-> ENTITY: ['swadharma'] | LITERAL: ['beban', 'hak dan berbagai milik yang dulunya ada pada mendiang', 'tanggung jawab']
- S1963 `pering` -MELAMBANGKAN-> ENTITY: ['purusa-pradana'] | LITERAL: ['mahkota']
- S2056 `patulangan` -BERBENTUK-> ENTITY: ['gadarba', 'macan', 'singa'] | LITERAL: ['binatang buas lainnya']
- S2183 `bale salunglung` -DIBUAT_DI-> ENTITY: ['bale banjar'] | LITERAL: ['rumah']
- S2337 `kajang` -DILIPAT_DI-> ENTITY: ['jenazah'] | LITERAL: ['simbol']
- S2502 `sawa wedana` -BERTUJUAN_MENYUCIKAN-> ENTITY: ['badan halus mendiang'] | LITERAL: ['arwah', 'roh']
- S2558 `ngroras` -BERASAL_DARI-> ENTITY: ['kata roras'] | LITERAL: ['kata roras']
- S2619 `sekah kangsen` -MENGGUNAKAN-> ENTITY: ['dulang'] | LITERAL: ['meja pendek kecil']
- S2623 `sekah kangsen` -DISUCIKAN_DENGAN-> ENTITY: ['tirtha'] | LITERAL: ['sajen kecil sebagai pengantar']
- S2748 `sekah` -DIALASI-> ENTITY: ['dulang'] | LITERAL: ['meja rendah']
- S2843 `santapan istimewa` -DIPERSEMBAHKAN_KEPADA-> ENTITY: ['sulinggih'] | LITERAL: ['sulinggih, tukang banten, tamu terhormat, dan tamu khusus lainnya']
- S3333 `bale` -TERBUAT_DARI-> ENTITY: ['galar'] | LITERAL: ['bambu']
- S3654 `gegaleng` -TERBUAT_DARI-> ENTITY: ['uang kepeng sebanyak 250 biji'] | LITERAL: ['potongan-potongan dahan kayu dapdap yang dibungkus dengan kain putih']
- S3728 `penggunaan wewangian` -BERTUJUAN_AGAR-> ENTITY: ['tubuh jenazah kelak berbau harum'] | LITERAL: ['orang yang numitis memperoleh pujian keharuman dalam tingkah lakunya']

## All-LITERAL compositional groups (13)

No ENTITY sibling survives in these -- judge each LITERAL on its
own: specific ritual-object noun phrase (candidate to flip) vs generic
word / abstract quality / descriptive clause (correctly stays LITERAL).

- S58 `nganyut` -BERUPA-> ['pelarungan abu ke sungai atau laut']
- S338 `soda` -BERUPA-> ['buah-buahan', 'jajan', 'minum', 'nasi']
- S788 `pitra yadnya` -TERDIRI_DARI-> ['dua kata']
- S801 `pitra yadnya` -TERDIRI_DARI-> ['beberapa jenis yang pelaksanaannya ber-bhinneka']
- S1197 `jun pere` -BERISI-> ['gambar', 'tulisan aksara']
- S1657 `panguryagan` -BERISI-> ['bermacam-macam ramuan']
- S2455 `pangabenan` -TERDIRI_DARI-> ['berbagai jenis']
- S3080 `punjung` -BERISI-> ['kopi', 'nasi dengan lauknya', 'rokok']
- S3118 `daun dapdap` -DIISI_DENGAN-> ['air']
- S3134 `lekesan` -DIISI_DENGAN-> ['bawang putih']
- S3142 `kawangen` -DIISI_DENGAN-> ['bawang putih sebagai lambang kuku di ujungnya']
- S3237 `lekesan` -BERISI-> ['tembakau']
- S3816 `ante` -TERBUAT_DARI-> ['bilahan-bilahan bambu']

## Isolated nodes: 65 total, 52 with a definition self-reference

Isolated = zero relations.jsonl edges in either direction (same
definition Neo4/load_ngaben_to_neo4j.py's :Isolated tag uses). Of these,
the ones below have their own definition text naming another known
entity (hub words already filtered out) -- candidate broader_overrides
targets. The rest of the isolated set had NO such hit; that's a normal,
expected outcome (see docstring), not a sign this pass missed something.

- `amrethi_karana`: tirtha amertha->tirtha_amertha, atma wedana->ngerorasin, tirtha->tirtha
- `api_takep`: hyang agni->hyang_agni, upasaksi->upasaksi, pepaga->pepaga
- `arjuna`: tirtha penembak->tirtha_penembak, ksatria->ksatria, tirtha->tirtha
- `asti_wedana`: tulang belulang->tulang_belulang, kuburan->kuburan
- `bhuta`: bhuta yadnya->bhuta_yadnya
- `boma`: adegan->adegan, hiasan->hiasan, wadah->bade, pura->pura
- `brahman`: pepaga->pepaga, moksa->moksa
- `bubur_pirata`: nasi angkeb->nasi_angkeb, sesajen->sesajen
- `bwah_loka`: swah loka->swah_loka, manusia->manusia
- `cuntaka`: bhuwana alit->bhuwana_alit, manusia->manusia
- `dadia`: pamrajan->pamrajan
- `daksinayana`: bhuta yadnya->bhuta_yadnya, dewasa madya->dewasa_madya, pitra yadnya->pitra_yadnya, sasih kaenem->sasih_kaenem, selatan->selatan, bhuta->bhuta, madya->madya, sasih->sasih
- `dasa_mala`: pabersihan mati->pabersihan_mati, pengerikan kuku->pengerikan_kuku, pabersihan->pabersihan, numitis->numitis
- `formalin`: tabunan->tabunan
- `guru_tiga`: penebusan->penebusan, prajuru->prajuru
- `ilih`: bayu->bayu
- `indrayana`: bhuta yadnya->bhuta_yadnya, dewa yadnya->dewa_yadnya, sasih kapat->sasih_kapat, selatan->selatan, lontar->lontar, bhuta->bhuta, sasih->sasih
- `kelompok_paksa_mahayana`: peranda buddha->peranda_buddha, naga banda->naga_banda, swadharma->swadharma, manusia->manusia
- `kikir`: kuncup teratai->kuncup_teratai
- `kuncup_teratai`: bunga teratai->bunga_teratai, bunga->bunga, kikir->kikir
- `leteh`: diuskamaligi->diuskamaligi, upakara->banten
- `madiksa`: panca yadnya->panca_yadnya, sulinggih->sulinggih, pandita->pandita, tirtha->tirtha
- `ngajum`: pawedan->pawedan, sangge->sangge, sekah->sekah
- `ngelinggihang`: upacara mapulang lingga->upacara_mapulang_lingga, sulinggih->sulinggih, brahman->brahman, tuhan->tuhan
- `nguyeg`: pancamahabutha->pancamahabutha, akasa->akasa, bhuta->bhuta, bayu->bayu, teja->teja
- `niskala`: mapegat->mapegat, pandita->pandita, pralina->pralina
- `numitis`: pengerikan kuku->pengerikan_kuku, lengan jenazah->lengan_jenazah, dasa mala->dasa_mala, besi->besi
- `nyiru`: alat upakara->alat_upakara, panguryagan->panguryagan, upakara->banten
- `payadnyan`: manusia->manusia
- `pelangkiran`: pamrajan rong tiga->pamrajan_rong_tiga, atma wedana->ngerorasin, ngangsen->ngangsen, pamrajan->pamrajan, bhatari->bhatari
- `pengutangan`: caru pengelambuk->caru_pengelambuk, upacara ngaskara->upacara_ngaskara, bale gede->bale_gede, pelebon->upacara_palebon_ngaben, usungan->usungan, setra->setra, bale->bale
- `peranda_shiwa`: peranda buddha->peranda_buddha, utama->utama
- `perlambang`: adegan dan pengawak->adegan, pengawak->pengawak
- `pisang_jati`: upakara->banten, daksina->daksina
- `pitraloka`: badan halus mendiang->badan_halus_mendiang, pangenteg linggih->pangenteg_linggih, bale salunglung->bale_salunglung, atma wedana->ngerorasin, ngangsen->ngangsen, bale->bale
- `piuning`: sedahan setra->sedahan_setra, ngelungah->upacara_ngelungah, ngulapin->ngulapin, kuburan->kuburan, niskala->niskala, setra->setra
- `prajuru`: guru tiga->guru_tiga, penebusan->penebusan
- `punia`: purusa-pradana->purusa_pradana
- `purnama`: masekeh->masekeh, tilem->tilem
- `raja_bali`: pangabenan->ngaben, bade->bade
- `satu_dua_perhiasan_pusaka`: perlambang->perlambang, pamerasan->pamerasan, swadharma->swadharma, upakara->banten
- `sukra`: wuku kuningan->wuku_kuningan
- `sumpe`: sawa wedana->sawa_wedana, pangabenan->ngaben
- `swah_loka`: upacara pengabenan->upacara_pengabenan, manusia->manusia, bhuta->bhuta
- `tabunan`: formalin->formalin
- `tilem`: masekeh->masekeh, purnama->purnama
- `tuhan`: upacara mapulang lingga->upacara_mapulang_lingga, sulinggih->sulinggih, bhatari->bhatari, brahman->brahman
- `ukur`: manusia->manusia, wadah->bade, lembu->lembu, singa->singa
- `upasaksi`: hyang agni->hyang_agni, api takep->api_takep, pepaga->pepaga
- `uttarayana`: pitra yadnya->pitra_yadnya, sasih kadasa->sasih_kadasa, sasih->sasih
- `wawu_lampus`: nyiramang layon->nyiramang_layon, kain putih->kain_putih, layon->layon
- `yama_purwana_tattwa`: ngaben cara yama purwana tatwa->ngaben_cara_yama_purwana_tatwa, lontar->lontar

## Self-loops (0)

subject_id == object_id -- almost always a coreference/anaphora
mis-resolution, not a real reflexive fact.


## Dangling references (0)

An edge or broader-pointer whose endpoint id isn't in entities.json.


## Near-duplicate ids (53)

Spelling-similarity candidates for force_merge or a SAMA_DENGAN edge --
read both entities before deciding; a shared root word alone (e.g. the
sasih_* family) is not by itself evidence of duplication.

- `brahman` ~ `brahmana` (ratio=0.93)
- `hitungan_galar` ~ `hitungan_galir` (ratio=0.93)
- `hitungan_galar` ~ `hitungan_galur` (ratio=0.93)
- `hitungan_galir` ~ `hitungan_galur` (ratio=0.93)
- `sasih_kadasa` ~ `sasih_kasa` (ratio=0.91)
- `arang_pembakaran_jaja_gina` ~ `arang_pembakaran_jaja_uli` (ratio=0.9)
- `bwah_loka` ~ `swah_loka` (ratio=0.89)
- `hitungan_wangke` ~ `hitungan_wangkong` (ratio=0.88)
- `sasih_kapat` ~ `sasih_kapitu` (ratio=0.87)
- `sasih_kasa` ~ `sasih_kasanga` (ratio=0.87)
- `bhatara` ~ `bhatari` (ratio=0.86)
- `sasih_kapat` ~ `sasih_kasa` (ratio=0.86)
- `pura_kahyangan_tiga` ~ `tirtha_kahyangan_tiga` (ratio=0.85)
- `kain_putih_untuk_bantal` ~ `kain_putih_untuk_saput` (ratio=0.84)
- `daksina` ~ `pradaksina` (ratio=0.82)
- `pamerasan` ~ `pamrajan` (ratio=0.82)
- `panca_datu` ~ `panca_dewata` (ratio=0.82)
- `sasih_kasa` ~ `sasih_katiga` (ratio=0.82)
- `daun_pisang` ~ `daun_pisang_saba` (ratio=0.81)
- `pengerikan_kuku` ~ `pengerikan_kuku_mutlak` (ratio=0.81)
- `suku_tunggal_abu` ~ `sukutunggal` (ratio=0.81)
- `uang_kepeng` ~ `uang_kepeng_asli` (ratio=0.81)
- `dewa_iswara` ~ `dewa_siwa` (ratio=0.8)
- `isi_pengawak` ~ `pengawak` (ratio=0.8)
- `jenazah_bayi` ~ `jenazah_bibir` (ratio=0.8)
- `kata_roras` ~ `saka_roras` (ratio=0.8)
- `lengan_jenazah` ~ `paplengkungan_jenazah` (ratio=0.8)
- `madyaning_madya` ~ `madyaning_utama` (ratio=0.8)
- `madyaning_madya` ~ `utamaning_madya` (ratio=0.8)
- `madyaning_nista` ~ `madyaning_utama` (ratio=0.8)
- `madyaning_nista` ~ `utamaning_nista` (ratio=0.8)
- `madyaning_utama` ~ `utamaning_utama` (ratio=0.8)
- `manah_tirtha_ening` ~ `tirtha_ening` (ratio=0.8)
- `nistaning_madya` ~ `nistaning_utama` (ratio=0.8)
- `nistaning_madya` ~ `utamaning_madya` (ratio=0.8)
- `nistaning_nista` ~ `nistaning_utama` (ratio=0.8)
- `nistaning_nista` ~ `utamaning_nista` (ratio=0.8)
- `nistaning_utama` ~ `utamaning_utama` (ratio=0.8)
- `pabersihan` ~ `pabersihan_mati` (ratio=0.8)
- `payadnyan` ~ `yadnya` (ratio=0.8)
- `perbandingan_kepala_lembu` ~ `perbandingan_kepala_singa` (ratio=0.8)
- `pranawa` ~ `prasawya` (ratio=0.8)
- `sasih_kadasa` ~ `sasih_kasanga` (ratio=0.8)
- `sasih_karo` ~ `sasih_kasa` (ratio=0.8)
- `sasih_kasanga` ~ `sasih_katiga` (ratio=0.8)
- `sekah_kangsen` ~ `sekah_sangge` (ratio=0.8)
- `upacara_palebon_ngaben` ~ `upacara_pengabenan` (ratio=0.8)
- `utamaning_madya` ~ `utamaning_utama` (ratio=0.8)
- `utamaning_nista` ~ `utamaning_utama` (ratio=0.8)
- `hitungan_galir` ~ `hitungan_likah` (ratio=0.79)
- `pitra_yadnya_dataran_rendah` ~ `pitra_yadnya_tahap_kedua` (ratio=0.78)
- `sasih_kadasa` ~ `sasih_kapat` (ratio=0.78)
- `sasih_kapat` ~ `sasih_katiga` (ratio=0.78)


# Deney protokolü (önceden kaydedildi)

Amaç: kurallı sistemin zayıf sonuçlarını açıklayan beş hipotezi, sonuçlara bakarak ayar yapmadan sınamak.

## Dönemler
| Ad | Aralık | Kullanım |
|---|---|---|
| dev | 2022-01-01 → 2024-01-01 | karşılaştırma ve eleme |
| validation | 2024-01-01 → 2025-01-01 | eleme kararı için ikinci onay |
| test | 2025-01-01 → 2026-10-22 | **en sonda, bir kez**, `--allow-test` ile; her çalıştırma `test_log.jsonl`'a yazılır |

Not: saatlik temel sistemin takvim yılı 2022–2025 sonuçlarını bu protokolden önce gördük. 2025 ve sonrası bu yüzden
"tamamen temiz" sayılmaz; rapor bunu belirtir.

## Hipotezler (merdiven; her basamak öncekine ekler)
| Id | Değişiklik | Sabit parametreler |
|---|---|---|
| E0 | Mevcut oylama sistemi, günlük mumlar | `config.toml` ile aynı eşikler, stop 2×ATR |
| E1 | Donchian topluluğu, stop yok | bakış 20/50/100, giriş ≥ 2/3 long, çıkış ≤ 1/3 long |
| E2 | + hedef volatilite büyüklüğü | hedef %20 yıllık, 20 günlük pencere, tavan %30 |
| E3 | + BTC > 200 günlük ortalama (yeni long için) | 200 gün |
| E4 | + giriş onayı | 2 gün üst üste, hacim ≥ 20 günlük ortalama |

Tüm parametreler literatürdeki yaygın varsayılanlardan seçildi, veriye bakılarak ayarlanmadı.
Ortak ayarlar: komisyon %0,10, kayma %0,05, kill switch kapalı (`max_drawdown = 0.99`, çok yıllık koşuyu erken
bitirmesin), `max_atr_pct = 0.20` (0,05 saatlik mumlara göre ayarlıydı).

## Kabul kuralı
Basamak k, o ana kadar **kabul edilen en iyi yapılandırmaya** göre kabul edilir ancak ve ancak hem `dev` hem
`validation` dönemlerinde Sharpe oranı daha yüksekse. Kabul edilmeyen basamak sonraki basamaklara dahil
edilmez (gerekirse yeniden kurulur ve ayrı deney olarak kaydedilir).

## Test dönemi
Kabul edilen son yapılandırma, E0 ve al-tut ile birlikte `test` döneminde **bir kez** çalıştırılır.
Sonuç ne olursa olsun rapor edilir. Sonuca göre parametre değişirse bu yeni bir deney olur ve test dönemi
artık geliştirme verisi sayılır.

## Sınırlar
* Üç coin bugünden bakınca seçildi (hepsi hayatta kaldı), al-tut'u biraz şişirir.
* Tek piyasa döngüsü, az sayıda bağımsız gözlem: sonuçlar kesin değil, ipucudur.
* Rejim filtresi ve onay yalnızca long girişe uygulanır (spot).

---

## Ek 1 (2026-10-22) — ilk sonuçlardan SONRA yazıldı

Bu ek, dev ve validation sonuçları görüldükten sonra eklendi; aşağıdaki karar sonuçlara bakılarak verildi ve bu açıkça kayıt altındadır.

**Ladder sonucu (özet).** Kabul kuralı uygulandığında hiçbir basamak E0'ı hem dev hem validation Sharpe'ında geçemedi.
Resmî sonuç: kabul edilen yapılandırma **E0**. E3/E4 her iki dönemde de tutarlıydı (Sharpe ≈ 1,0) ama dev'de E0'ın gerisinde kaldı.

**Karar (araştırmacı).** E3 ve E4, kabul kuralını geçmedikleri hâlde *ileriye dönük izleme adayı* olarak sürdürülür. Bu, kuralı geçtikleri anlamına gelmez.

**Test bölgesi (2025-01-01 → 2026-10-22).**
* E0 için resmî, tek seferlik test koşulur (protokolün aslı).
* E3/E4 için bu bölgeden alınan her sonuç **keşif amaçlıdır**, temiz doğrulama değildir: seçim, sonuçlar görüldükten sonra yapıldı.
* Test bölgesine düşen her koşu (`y2025`, `y2026` dahil) `--allow-test` ister ve `test_log.jsonl`'a yazılır.

**Yıl dilimleri.** `y2022 … y2026`: boğa/ayı rejiminde davranışı görmek içindir. Kabul kararı vermez.

**Gerçek dışarıdan doğrulama.** 2026-10-22'den sonraki veri. E3 ve E4 bu tarihten itibaren ayrı durum dosyalarıyla paper trading'de (`sim`) izlenir.
* Parametre, eşik veya yapılandırma izleme sürecinde **değiştirilmez**; değişirse yeni bir deney sayılır ve izleme sıfırlanır.
* Değerlendirme zamanı: en az **180 gün** *ve* en az **15 tamamlanmış işlem*, hangisi geç gelirse.
* Ölçüt: aynı dönemde al-tut'a göre Sharpe ve maksimum drawdown. Getiri tek başına ölçüt değildir.
* Sonuç olumsuz olsa da yayınlanır.

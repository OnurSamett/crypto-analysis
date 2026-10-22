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

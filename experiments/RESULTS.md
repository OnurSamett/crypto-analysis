# Deney sonuçları (2026-10-22)

Tüm sayılar komisyon (%0,10) ve kayma (%0,05) sonrası, spot, BTC/ETH/SOL eşit ağırlık. Protokol: `PROTOCOL.md`.
Kural: sonuçlar ne olursa olsun yayınlanır. "Test" ve "y2025/y2026" satırları test bölgesindedir (bkz. Ek 1).

## E0–E4 merdiveni (günlük mumlar)
| Yapılandırma | dev (2022–23) getiri / Sharpe / maxDD | validation (2024) getiri / Sharpe / maxDD |
|---|---|---|
| E0 günlük oylama | +30,4% / 1,23 / −8,2% | −2,6% / −0,31 / −8,8% |
| E1 Donchian | +15,2% / 0,55 / −20,2% | +16,7% / 0,88 / −14,8% |
| E2 + hedef vol. | +5,2% / 0,23 / −46,8% | +39,4% / 0,99 / −29,4% |
| E3 + BTC 200g filtre | +63,0% / 1,08 / −27,2% | +37,8% / 0,96 / −29,4% |
| E4 + giriş onayı | +62,1% / 1,07 / −26,5% | +40,4% / 1,01 / −29,2% |
| Al-tut | −31,4% / 0,04 / −77,0% | +75,0% / 1,23 / −34,0% |

Kabul kuralı sonucu: hiçbir basamak E0'ı hem dev hem validation Sharpe'ında geçmedi (resmî sonuç: E0). E3/E4 araştırmacı kararıyla ileriye dönük izlemeye alındı (Ek 1).

## Resmî test (yalnızca E0, tek seferlik, 2025-01-01 → 2026-10-22)
E0: **+0,0%**, Sharpe 0,04, maxDD −5,7%, 6 işlem, ortalama maruziyet %9. Al-tut: −27,6% (maxDD −63,4%).

## Yıl yıl (keşif amaçlı; 2025/2026 test bölgesi)
| Yıl | Al-tut | E3 | E4 |
|---|---|---|---|
| 2022 | −76,0% | 0,0% | 0,0% |
| 2023 | +386,8% | +63,0% | +62,1% |
| 2024 | +75,0% | +37,8% | +40,4% |
| 2025 | −18,4% | −13,9% | −19,7% |
| 2026 (22 Eki'ye) | −13,0% | +11,7% | +8,4% |

2022: BTC yıl boyunca 200 günlük ortalamanın altında kaldı (0/365 gün), rejim filtresi tüm girişleri engelledi; sıfır işlem.

## E5: 4 saatlik hızlı Donchian (5/10/20 gün) — Sharpe, E3'e göre
| | dev | validation |
|---|---|---|
| E3 (günlük) | 1,08 | 0,96 |
| **E5 (4S)** | **1,46** | **1,21** |

| | dev getiri / maxDD / tamamlanan işlem / komisyon | validation getiri / maxDD / tamamlanan işlem / komisyon |
|---|---|---|
| E3 | +63,0% / −27,2% / 9 / 52 USDT | +37,8% / −29,4% / 5 / 42 USDT |
| E5 | +119,1% / −25,5% / 23 / 143 USDT | +45,5% / −25,3% / 31 / 209 USDT |

Ön kayıtlı kural (E3'e göre iki dönemde de daha yüksek Sharpe) **sağlandı**. E5 yine de 2024'te al-tut'un (+83,6%) gerisinde.
İşlem sıklığı: ~1 işlem/ay (dev), ~2,6 işlem/ay (validation) tamamlanmış gidiş-dönüş.

## E6: DCA (haftalık 100 USDT)
| Dönem | Varyant | Yatırılan | Bitiş | Getiri | maxDD |
|---|---|---|---|---|---|
| dev | D0 düz | 10.400 | 22.621 | +117,5% | −79,2% |
| dev | D1 bear'da alma | 4.100 | 9.260 | +125,8% | −27,1% |
| dev | D2 bear'da 2× | 16.700 | 35.982 | +115,5% | −79,2% |
| validation | D0 | 5.300 | 6.931 | +30,8% | −34,2% |
| validation | D1 | 4.300 | 5.506 | +28,0% | −34,2% |
| validation | D2 | 6.300 | 8.356 | +32,6% | −34,2% |

Kabul kuralı sonucu: D1 ve D2 reddedildi (validation'da D1 getirisi ve IRR'si düşük; dev'de D2 getirisi düşük). IRR bu kısa/az nakit akışlı pencerede
aşırı oynak, yorumlanmamalı.

## Denetim
`audit`: E0, E3 ve E5 sinyalleri BTC/ETH/SOL'de kesme (look-ahead) testini fark 0 ile geçti. E3 skoru son 300 günlük mumla tam aynı; E5 skoru son ≥900 4S mumla tam aynı.

## Sınırlar
* Üç coin bugünden bakınca seçildi (hepsi hayatta kaldı); al-tut'u şişirir.
* Tek piyasa döngüsü, az sayıda bağımsız gözlem. Sonuçlar ipucudur, kanıt değil.
* Yıllık dilimlerin bileşiği, her yıl yeniden kurulumla hesaplanır; sürekli koşudan farklıdır.
* Kill switch araştırmada kapalı; gerçek kullanımda açık olacak ve drawdown'lar kesilecektir.

## Registry (kanıt kapısı) sonuçları — R01, 2026-10-22
Plan, kod ve sonuç sırasıyla commit'lendi (`95bc64a`, `544caa6`, `baf0860`). Sayılar %0,30 maliyet sonrası; p-değerleri dairesel zaman kaydırma permütasyonuyla, Holm düzeltmesi K = 12.

| Varyant (hepsi "düşük funding") | dev ortalama | Holm p | validation ortalama | Karar |
|---|---|---|---|---|
| z0=2,0 · 1 gün | +0,18% | 1,00 | −0,24% | 4. ölçütte elendi |
| z0=2,5 · 1 gün | −0,40% | 1,00 | −0,16% | 3. ölçütte elendi |
| **z0=2,0 · 3 gün** | **+1,86%** | **0,0096** | +0,40% (90% aralık −0,67% … +1,56%) | 5. ölçütte elendi |

Sayım aşamasında 12 varyanttan yalnızca 3'ü eşikleri geçti; "yüksek funding" varyantlarının hepsi yetersiz kaldı (en yakını dev'de 29 olay, eşik 30). 3 günlük varyant dev'de düzeltme sonrası anlamlıydı ama validation etkisi dev etkisinin %21'i kadardı (kural en az %50). Hiçbir varyant geçmedi.
R08, bu varyantın yalnızca 2026-10-23 sonrası veriyle, tek hipotez olarak ileriye dönük doğrulamasıdır.

# İleriye dönük paper trading kaydı

Protokol Ek 1'e göre (bkz. `../PROTOCOL.md`). Yapılandırma, eşik ve parametre bu süreçte **değiştirilmez**.

| | E3 (rejim filtresi) | E4 (rejim + giriş onayı) |
|---|---|---|
| Yapılandırma | `experiments/e3_regime.toml` | `experiments/e4_confirm.toml` |
| config_hash | `52813d434468` | `07eb693eccb5` |
| Başlangıç | 2026-10-22 08:19 UTC | 2026-10-22 08:19 UTC |
| Yürütücü | `sim` (yerel defter, gerçek emir yok) | `sim` |
| Başlangıç sermayesi | 10.000 USDT | 10.000 USDT |
| İlk işlemler | BTC, ETH, SOL alındı | BTC, ETH alındı; SOL onay yok diye bekledi |

Çalıştırma (günlük mum kapanışı UTC 00:00'dan sonra bir tur; döngü kendi bekler):

```bash
python3 -m okx_karar --config experiments/e3_regime.toml paper --executor sim
python3 -m okx_karar --config experiments/e4_confirm.toml paper --executor sim
```

Değerlendirme: en az 180 gün **ve** en az 15 tamamlanmış işlem (hangisi geç gelirse). Ölçüt: aynı dönemde al-tut'a göre
Sharpe ve maksimum drawdown. Durum dosyaları `state/` altındadır (git'e girmez); değerlendirme sırasında işlem kayıtları
(`trades_*.csv`) ve günlük sermaye özeti bu klasöre eklenecek.

Bilinen sınır: paper, borsada bekleyen emir kullanmaz ve dolumları kapanış fiyatından simüle eder (backtest sonraki
açılıştan doldurur). E3/E4 stop'suz çalıştığı için stop sınırı bu iki yapılandırmayı etkilemez.

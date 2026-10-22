# crypto-analysis

Python paketi `okx_karar`: OKX için kurallı (LLM'siz) karar sistemi, backtest ve paper trading.

TradingAgents'taki **analist → tartışma → risk → trader** rollerini LLM kullanmadan, deterministik
kodla uygulayan bir karar sistemi. Amaç, ileride LLM ajanlarının yenmesi gereken **baz çizgisini**
oluşturmak. Aynı backtest motoru ve aynı `Sinyal → Karar` arayüzü ajanlar için de kullanılır.

> Bu bir araştırma aracıdır, yatırım tavsiyesi değildir. Gerçek hesapla işlem bu sürümde kapalıdır.

## Not: deneylerin ön kaydı

`experiments/` altındaki protokol ve E0–E4 yapılandırmaları, ilk koşudan önce SmartInvest AI deposunda
(`finans analiz programı`, `okx_karar/` altında) commit'lendi. Bu depo o dosyaların kopyasıyla başlar;
sonradan değiştirilirse yeni bir deney sayılır.

## Kurulum

```bash
cd crypto-analysis
python3 -m pip install -r requirements.txt
python3 -m pytest
```

## Kullanım

```bash
python3 -m okx_karar fetch --days 365            # mumları indir (data/ önbelleği)
python3 -m okx_karar backtest --days 365          # strateji vs al-tut, results/ altına kaydeder
python3 -m okx_karar backtest --start 2024-01-01 --end 2025-01-01 --offline
python3 -m okx_karar paper --executor sim         # yerel paper trading, her mum kapanışında karar
python3 -m okx_karar paper --executor demo        # OKX demo hesabında (anahtar gerekir)
python3 -m okx_karar status --executor sim
```

## Bildirim botu ve veri toplayıcı (emir vermez)

```bash
python3 -m okx_karar notify --dry-run     # sinyal durumunu ekrana yazar (E3 günlük + E5 4 saatlik)
python3 -m okx_karar notify               # değişiklik varsa Telegram'a gönderir
python3 -m okx_karar collect              # funding, açık pozisyon, derinlik, uzun/kısa oranı → data/collector.db
```
Mac mini kurulumu ve Telegram botu için: [`deploy/README.md`](deploy/README.md).

## Karar akışı

| Rol | Modül | Ne yapar |
|---|---|---|
| Veri | `data.py`, `okx_client.py` | OKX public API'den kapanmış mumlar (anahtar gerekmez) |
| Analist | `signals.py` | trend (EMA 20/50), MACD, RSI, hacim, (swap) funding → her biri −1…+1 |
| Tartışma | `decision.py` | ağırlıklı oylama → tek skor; histerezisli giriş/çıkış eşikleri |
| Risk | `risk.py` | ATR'ye göre pozisyon büyüklüğü, stop, volatilite vetosu, drawdown kill switch |
| Trader | `backtest.py`, `paper.py`, `executors.py` | hedef pozisyon → emir (simülasyon veya OKX demo) |

Tüm ayarlar `config.toml` içindedir.

## Geleceğe bakmama kuralları

* Karar **t mumunun kapanışında**, yalnızca o ana kadarki veriyle verilir; emir **t+1 açılışında** dolar.
* Kapanmamış mum (`confirm = "0"`) hiçbir zaman kullanılmaz.
* Funding oranı, bir barın kapanış anında bilinen son değerle eşlenir.
* `tests/test_no_lookahead.py`, geleceğe ait mumlar rastgele değiştirildiğinde geçmiş kararların
  değişmediğini doğrular.
* `decision.scores_from_callable` bar bar karar veren bir stratejiye (ör. LLM ajanı) yalnızca
  geçmişi verir. Ajan bu yolla takılırsa geleceğe bakması yapısal olarak imkânsız olur.

## Parametreleri sabitleme

Backtest raporu `config.toml` dosyasının SHA-256 özetini (`config_hash`) yazar. Adil bir test için:

1. Parametreleri bir **geliştirme döneminde** belirleyin, ör. `--start 2023-01-01 --end 2025-01-01`.
2. `config.toml`'u commit'leyin.
3. **Test dönemine** (`--start 2025-01-01`) bir kez bakın. Bu dönemin sonucuna göre ayar
   değiştirirseniz test dönemi artık geliştirme verisi olur.

## Paper trading

* `sim`: yerel defter (`state/sim_account.json`), backtest ile aynı maliyet modeli. Anahtar gerekmez.
* `demo`: OKX demo trading. okx.com → Demo Trading → API'den bir anahtar oluşturun, yalnızca
  **Okuma + İşlem** yetkisi verin, `.env.example` dosyasını `.env` olarak kopyalayıp doldurun.
  İstemci her özel isteğe `x-simulated-trading: 1` ekler. Canlı mod kodda kapalıdır.
* Aynı mum iki kez işlenmez (`state/paper_*.json`), emir kimliği (`clOrdId`) mum zamanından türetilir.
* Sınırlama: stop bot tarafından mum kapanışlarında kontrol edilir, borsada bekleyen bir stop emri
  yoktur. Bu yüzden mum içinde stop'un çok altına inen bir hareket ancak kapanışta yakalanır.

## Vadeli (swap) — devre dışı

`futures.py` short pozisyon, kaldıraçlı tavan, funding sinyali ve funding ödemelerini içerir; backtest ve
demo yürütücüsü hazırdır ve testlidir. Açmak için:

```toml
[market]
mode = "swap"
[futures]
enabled = true
```

`enabled = false` iken swap modu yapılandırma yüklenirken reddedilir. Demo swap için hesap **net**
pozisyon modunda olmalıdır. Likidasyon modellenmez; kaldıracı düşük ve stop'u likidasyondan uzak tutun.

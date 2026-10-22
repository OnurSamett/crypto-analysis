[English](README.md) | **Türkçe**

# Mac mini'de kurulum (Telegram bildirimi + veri toplayıcı)

Bu kurulum **emir vermez**. Yalnızca (1) sinyal durumu değişince Telegram'a mesaj atar, (2) 5 dakikada bir kendi verimizi toplar.

## 1) Hazırlık
```bash
git clone https://github.com/OnurSamett/crypto-analysis.git && cd crypto-analysis
python3 --version            # 3.11 veya üstü olmalı (tomllib için)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q   # hepsi geçmeli
```

## 2) Telegram botu
1. Telegram'da **@BotFather** → `/newbot` → ad ve kullanıcı adı verin → size bir **token** verir.
2. `cp .env.example .env` ve `.env` içine `TELEGRAM_BOT_TOKEN=...` yazın. **Token'ı kimseyle, bu sohbette bile, paylaşmayın.**
3. Telegram'da yeni botunuza girip **/start** yazın.
4. `.venv/bin/python -m okx_karar notify --get-chat-id` → çıkan `TELEGRAM_CHAT_ID=...` satırını `.env`'e ekleyin.
5. `.venv/bin/python -m okx_karar notify --test` → telefonunuza "bağlantı testi" gelmeli.

`.env` git'e girmez (`.gitignore`). Bot yalnızca `TELEGRAM_CHAT_ID` ile eşleşen sohbete yazar.

## 3) Deneme ve ilk özet
```bash
.venv/bin/python -m okx_karar notify --dry-run     # yalnızca ekrana yazar, durum kaydetmez
.venv/bin/python -m okx_karar notify               # ilk özet mesajı Telegram'a gider, durum kaydedilir
.venv/bin/python -m okx_karar collect --summary    # veri toplayıcı özeti
```
İlk çalıştırmada eski kırılımlar yeni giriş sayılmaz; yalnızca "mevcut durum" özeti gelir. Sonraki mesajlar yalnızca **olay** olduğunda
(giriş, çıkış, filtreye takılma, rejim değişimi) ve her pazartesi haftalık özet olarak gelir.

## 4) Otomatik çalıştırma (launchd)
```bash
./deploy/install_macos.sh
```
* `notify`: her saat :05'te çalışır, yeni kapanmış mum yoksa hiçbir şey göndermez.
* `collect`: 5 dakikada bir veri toplar (`data/collector.db`).

Günlükler: `~/Library/Logs/crypto-analysis/`. Kaldırmak için `./deploy/uninstall_macos.sh`.

## 5) Mac mini ayarları (kritik)
* **Sistem Ayarları → Enerji**: "Ekran kapalıyken bilgisayarın otomatik uyumasını engelle" **açık**; "Elektrik kesintisinden sonra otomatik olarak başlat" **açık**.
* Otomatik oturum açma açık olmalı (LaunchAgent kullanıcı oturumunda çalışır).
* Saat/zaman bölgesi otomatik; sistem ayarlarında "Tarih ve saati otomatik ayarla" açık.

## 6) Sorun giderme
* Telegram'a gelmiyorsa: `notify --test`, sonra `~/Library/Logs/crypto-analysis/notify.err.log`.
* Aynı bar iki kez gelmez: durum `state/notify_*.json` içindedir. Sıfırdan özet için `notify --force-snapshot`.
* Hata olursa günde en fazla bir "⚠️ hata verdi" mesajı gelir.

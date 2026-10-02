# Grok Trading Bot (50 EUR Budget)

Fragt Grok (xAI) alle paar Minuten nach einer Handelsentscheidung (buy/sell/hold)
basierend auf den letzten Kerzen, und führt sie über die Exchange-API aus.
Startet standardmäßig im Dry-Run (keine echten Trades), bis du `DRY_RUN=false` setzt.

## Setup

1. **xAI API-Key holen**: auf https://console.x.ai registrieren, API-Key erstellen.
2. **Exchange-API-Key holen** (Beispiel Binance):
   - Account erstellen, Verifizierung durchlaufen.
   - Unter API-Management einen neuen Key erstellen.
   - Nur **"Spot Trading"** aktivieren, **"Withdrawals" ausgeschaltet lassen**.
3. **Python-Abhängigkeiten installieren**:
   ```bash
   cd trading-bot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Konfiguration**:
   ```bash
   cp .env.example .env
   ```
   Dann `.env` öffnen und ausfüllen: `XAI_API_KEY`, `EXCHANGE_API_KEY`, `EXCHANGE_API_SECRET`.
   `STARTING_CAPITAL_EUR` ist bereits auf `50` gesetzt. `DRY_RUN=true` lassen für den ersten Test.
   - `TRADING_PAIRS`: kommagetrennte Liste, z. B. `BTC/USDT,ETH/USDT,SOL/USDT` — Grok
     wählt selbst, welches davon (falls überhaupt) gekauft wird.
   - `RISK_LEVEL`: `conservative` (nur bei sehr klaren Signalen handeln),
     `balanced` (Standard) oder `aggressive` (handelt auch bei kleineren Chancen).
5. **Dry-Run starten** (keine echten Trades, nur Logging):
   ```bash
   python3 main.py
   ```
   Lass es eine Weile laufen und beobachte in den Logs, ob die Entscheidungen von Grok
   sinnvoll aussehen, bevor du live gehst.
6. **Live schalten**: in `.env` `DRY_RUN=false` setzen und neu starten.
   Ab jetzt werden echte Market-Orders auf der Exchange ausgeführt.

## Kapital wächst (und schrumpft) automatisch mit

`STARTING_CAPITAL_EUR` ist nur der **Startwert**. Nach jedem abgeschlossenen Trade
merkt sich der Bot in `state.json`, wie viel sein Kapital durch Gewinn/Verlust jetzt
wert ist, und setzt genau diesen Betrag beim nächsten Kauf ein — kein manuelles
Nachstellen in der `.env` nötig. Macht er Gewinn, wird die nächste Position
entsprechend größer; macht er Verlust, entsprechend kleiner.

## Mehrere Positionen gleichzeitig + Positionsgröße nach Sicherheit

Der Bot ist nicht mehr auf eine einzige offene Position begrenzt — er kann in
mehreren der `TRADING_PAIRS` gleichzeitig investiert sein (z. B. BTC und ETH
zur selben Zeit), solange noch freies Kapital übrig ist.

Jede Kauf-Entscheidung von Grok kommt mit einer Sicherheits-Einschätzung:
- **high** → setzt das komplette verfügbare freie Kapital ein
- **medium** → setzt die Hälfte ein
- **low** → setzt ein Viertel ein

So muss er sich nicht zwischen "ganz oder gar nicht" entscheiden, wenn ein
Signal nur mittelmäßig überzeugend ist.

## Sicherheitsmechanismen

- **Stop-Loss**: verkauft eine Position automatisch, wenn ihr Kurs seit dem
  Einstieg um `STOP_LOSS_PERCENT` gefallen ist — unabhängig davon, was Grok
  sagt. Gilt für jede offene Position einzeln.
- **State** liegt in `state.json` (wird nicht committed) — merkt sich alle
  offenen Positionen und das freie Kapital über Neustarts hinweg.

## Laufen lassen, auch wenn dein PC aus ist

Lokal läuft der Bot nur, solange `main.py` läuft. Für 24/7-Betrieb:
- günstiger VPS (z. B. Hetzner, ~5 €/Monat), oder
- `systemd`-Service / `screen`/`tmux`-Session auf einem Server, die `python3 main.py`
  dauerhaft am Laufen hält.

## Risiko

Das ist ein einfacher, selbst gebauter Bot ohne Backtesting-Historie. Die LLM-Entscheidung
ist kein Garant für Profit — bei 50 € Einsatz ist der maximale Verlust auf diese 50 €
begrenzt (plus eventuelle Exchange-Gebühren), aber ein Totalverlust ist jederzeit möglich.

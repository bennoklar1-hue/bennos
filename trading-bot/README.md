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
   `MAX_TRADE_EUR` ist bereits auf `50` gesetzt. `DRY_RUN=true` lassen für den ersten Test.
5. **Dry-Run starten** (keine echten Trades, nur Logging):
   ```bash
   python3 main.py
   ```
   Lass es eine Weile laufen und beobachte in den Logs, ob die Entscheidungen von Grok
   sinnvoll aussehen, bevor du live gehst.
6. **Live schalten**: in `.env` `DRY_RUN=false` setzen und neu starten.
   Ab jetzt werden echte Market-Orders auf der Exchange ausgeführt, begrenzt auf
   dein `MAX_TRADE_EUR`-Budget.

## Sicherheitsmechanismen

- **Budget-Cap**: kauft nie mehr als `MAX_TRADE_EUR` insgesamt.
- **Stop-Loss**: verkauft automatisch, wenn der Kurs seit dem Einstieg um
  `STOP_LOSS_PERCENT` gefallen ist — unabhängig davon, was Grok sagt.
- **Ein Trade gleichzeitig**: kauft nicht nach, solange eine Position offen ist.
- **State** liegt in `state.json` (wird nicht committed) — merkt sich Position
  über Neustarts hinweg.

## Laufen lassen, auch wenn dein PC aus ist

Lokal läuft der Bot nur, solange `main.py` läuft. Für 24/7-Betrieb:
- günstiger VPS (z. B. Hetzner, ~5 €/Monat), oder
- `systemd`-Service / `screen`/`tmux`-Session auf einem Server, die `python3 main.py`
  dauerhaft am Laufen hält.

## Risiko

Das ist ein einfacher, selbst gebauter Bot ohne Backtesting-Historie. Die LLM-Entscheidung
ist kein Garant für Profit — bei 50 € Einsatz ist der maximale Verlust auf diese 50 €
begrenzt (plus eventuelle Exchange-Gebühren), aber ein Totalverlust ist jederzeit möglich.

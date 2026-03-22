# ₿ BTC Divergence Dashboard

Ein modernes, dockerisiertes Bitcoin-Divergenz-Scanner Dashboard mit RSI & MACD Analyse über mehrere Timeframes.

![Dashboard](https://img.shields.io/badge/Stack-Python%20%7C%20Flask%20%7C%20Docker-blue)

## Features

- **RSI-Divergenz Erkennung** über 4 Timeframes (15m, 1h, 4h, 1d)
- **MACD Bestätigung** für jeden Divergenz-Signal
- **Parallele Datenabfrage** via ThreadPoolExecutor (schneller als sequenziell)
- **60s Auto-Refresh** mit Caching
- **RSI Gauge** Visualisierung pro Timeframe
- **Modernes, helles Dashboard** – Syne + DM Mono Typografie

## Schnellstart

```bash
# 1. Klonen / Dateien ablegen
cd bitcoin-dashboard

# 2. Starten
docker compose up --build -d

# 3. Öffnen
open http://localhost:8080
```

## Stoppen

```bash
docker compose down
```

## Struktur

```
bitcoin-dashboard/
├── backend/
│   ├── app.py           # Flask API + Caching
│   ├── scanner.py       # Optimierter RSI/MACD Scanner
│   └── requirements.txt
├── frontend/
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## API Endpunkte

| Endpoint      | Beschreibung                    |
|---------------|---------------------------------|
| `GET /`       | Dashboard UI                    |
| `GET /api/scan` | JSON Scan-Ergebnisse          |
| `GET /api/health` | Health Check                |

## Konfiguration

In `backend/scanner.py`:

```python
SYMBOL_PAIR = 'BTCUSDT'
TIMEFRAMES  = ['15m', '1h', '4h', '1d']
RSI_LENGTH  = 14
LOOKBACK    = 5
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9
```

## Optimierungen gegenüber Original

| Alt | Neu |
|-----|-----|
| Sequenzieller API-Abruf | Parallele Requests (4x schneller) |
| Keine Fehlerbehandlung bei RSI/0 | `replace(0, NaN)` Division-Guard |
| Nur Terminal-Ausgabe | Web-Dashboard + REST API |
| Kein Caching | 60s In-Memory Cache |
| Manuelle Ausführung | Docker Compose + Health Check |
# bitcoin-divergenzen

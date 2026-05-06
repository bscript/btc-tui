# btc-tui

A live BTC/USDT trade terminal in your terminal — real-time candlestick chart, trade feed, and buy/sell pressure bar. Powered by the Binance public WebSocket. No API key required.

```
─ ₿ BTC/USDT  [10s candles] ──────────────────────── 10:42:31 ─
▲ $103,241.50  +2.14%    Hi $104,100  Lo $101,200  Vol 8,432 BTC
████████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░░
BUY 68%  SELL 32%  (session)
────────────────────────────────────────────────────────────────
104,500 │                               ── TRADES ──
        │  ██ ██                        TIME     S      PRICE     QTY
103,800 │  ██ ██ ██                     10:42:31 B  103,241.5   0.012
        │▓▓██ ██ ██                     10:42:30 S  103,238.0   0.500
103,100 │▓▓   ██                        10:42:29 B  103,245.0   1.204
```

## Install

### Homebrew (recommended)

```sh
brew install YOUR_USERNAME/tap/btc-tui
```

### pip / pipx

```sh
# pipx keeps it isolated (recommended)
pipx install btc-tui

# or plain pip
pip install btc-tui
```

### From source

```sh
git clone https://github.com/YOUR_USERNAME/btc-tui
cd btc-tui
pip install .
```

## Usage

```sh
btc-tui
```

Press `q` or `Esc` to quit.

## Keys

| Key | Action |
|-----|--------|
| `q` / `Q` / `Esc` | Quit |

## Configuration

Edit `CANDLE_SECONDS` at the top of `btc_tui/main.py` to change the candle interval (default: `10` seconds, set to `60` for 1-minute candles).

## Requirements

- Python 3.9+
- A terminal at least 80×24 characters (bigger is better)
- Internet connection (connects to `stream.binance.com`)

## License

MIT

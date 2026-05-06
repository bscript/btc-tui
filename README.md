# btc-tui

A live BTC/USDT trade terminal in your terminal — real-time candlestick chart, trade feed, and buy/sell pressure bar. Powered by the Binance public WebSocket. No API key required.

<img width="1324" height="856" alt="Image" src="https://github.com/user-attachments/assets/f0dccb17-dbaa-4045-a7b4-e481a4fc5480" />

## Install

### Homebrew (recommended)

```sh
brew install bscript/btc-tui/btc-tui
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
git clone https://github.com/bscript/btc-tui
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

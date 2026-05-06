# btc-tui

A live BTC trade terminal in your terminal — real-time candlestick chart, trade feed, and buy/sell pressure bar. Supports Binance, Coinbase, and Bybit. No API key required.

<img width="1324" height="856" alt="Image" src="https://github.com/user-attachments/assets/6828cce7-4b14-4bd7-8ed4-b6e28a665c60" />

## Install

### Homebrew (recommended)

```sh
brew install bscript/btc-tui/btc-tui
```

To upgrade later:

```sh
brew update && brew upgrade btc-tui
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
btc-tui                       # Binance (default)
btc-tui --exchange coinbase   # Coinbase
btc-tui --exchange bybit      # Bybit
```

Press `q` or `Esc` to quit.

## Exchanges

| Flag | Exchange | Pair |
| ---- | -------- | ---- |
| *(default)* | Binance | BTC/USDT |
| `--exchange coinbase` | Coinbase | BTC/USD |
| `--exchange bybit` | Bybit | BTC/USDT |

All exchanges stream live trades and ticker data with no API key required.

## Keys

| Key               | Action |
| ----------------- | ------ |
| `q` / `Q` / `Esc` | Quit   |

## Configuration

Edit `CANDLE_SECONDS` at the top of `btc_tui/main.py` to change the candle interval (default: `10` seconds, set to `60` for 1-minute candles).

## Requirements

- Python 3.9+
- A terminal at least 80×24 characters (bigger is better)
- Internet connection

## License

MIT
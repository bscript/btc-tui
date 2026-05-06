#!/usr/bin/env python3
"""
BTC Live Trade Terminal — with candlestick chart.
Connects to Binance public WebSocket, no API key needed.
"""

import argparse
import asyncio
import json
import curses
from collections import deque
from datetime import datetime

import websockets

BINANCE_WS = "wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/btcusdt@ticker"
COINBASE_WS = "wss://advanced-trade-ws.coinbase.com"
BYBIT_WS    = "wss://stream.bybit.com/v5/public/spot"

EXCHANGE_LABELS = {
    "binance":  "Binance BTC/USDT",
    "coinbase": "Coinbase BTC/USD",
    "bybit":    "Bybit BTC/USDT",
}

CANDLE_SECONDS = 10   # change to 60 for 1-min candles
MAX_CANDLES = 80
MAX_TRADES = 300


class Candle:
    def __init__(self, open_price, ts):
        self.open = open_price
        self.high = open_price
        self.low = open_price
        self.close = open_price
        self.volume = 0.0
        self.buy_vol = 0.0
        self.ts = ts

    def update(self, price, qty, is_buy):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += qty
        if is_buy:
            self.buy_vol += qty

    @property
    def is_bull(self):
        return self.close >= self.open

    @property
    def body_top(self):
        return max(self.open, self.close)

    @property
    def body_bot(self):
        return min(self.open, self.close)


class TUI:
    def __init__(self, stdscr, exchange="binance"):
        self.stdscr = stdscr
        self.exchange = exchange
        self.trades = deque(maxlen=MAX_TRADES)
        self.ticker = {}
        self.candles = deque(maxlen=MAX_CANDLES)
        self.current_candle = None
        self.last_price = 0.0
        self.prev_price = 0.0
        self.buy_vol = 0.0
        self.sell_vol = 0.0
        self.connected = False
        self.running = True

        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_CYAN, -1)
        curses.init_pair(4, curses.COLOR_YELLOW, -1)
        curses.init_pair(5, curses.COLOR_WHITE, -1)
        curses.init_pair(6, curses.COLOR_MAGENTA, -1)
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_RED)
        curses.curs_set(0)
        self.stdscr.nodelay(True)

    def _bucket(self, ts_ms):
        return int(ts_ms / 1000 / CANDLE_SECONDS) * CANDLE_SECONDS

    def _ingest(self, price: float, qty: float, is_buy: bool, ts_ms: int):
        """Common ingestion path used by all exchange adapters."""
        ts = self._bucket(ts_ms)
        self.prev_price = self.last_price or price
        self.last_price = price

        if is_buy:
            self.buy_vol += qty
        else:
            self.sell_vol += qty

        if self.current_candle is None:
            self.current_candle = Candle(price, ts)
        elif ts > self.current_candle.ts:
            self.candles.append(self.current_candle)
            self.current_candle = Candle(price, ts)
        else:
            self.current_candle.update(price, qty, is_buy)

        self.connected = True
        # store as a normalised dict so the draw loop stays exchange-agnostic
        self.trades.append({"p": str(price), "q": str(qty), "m": not is_buy, "T": ts_ms})

    def ingest_trade(self, data):
        """Binance aggTrade adapter."""
        self._ingest(
            price=float(data["p"]),
            qty=float(data["q"]),
            is_buy=not data["m"],
            ts_ms=data["T"],
        )

    # ── Coinbase adapters ────────────────────────────────────────────────────

    def ingest_coinbase_trades(self, trades: list):
        for t in trades:
            try:
                ts_ms = int(datetime.fromisoformat(
                    t["time"].replace("Z", "+00:00")
                ).timestamp() * 1000)
                self._ingest(
                    price=float(t["price"]),
                    qty=float(t["size"]),
                    is_buy=(t["side"] == "BUY"),
                    ts_ms=ts_ms,
                )
            except (KeyError, ValueError):
                pass

    def ingest_coinbase_ticker(self, tickers: list):
        for t in tickers:
            try:
                self.ticker = {
                    "P": t.get("price_percent_chg_24_h", "0.00"),
                    "h": t.get("high_24_h", "0"),
                    "l": t.get("low_24_h", "0"),
                    "v": t.get("volume_24_h", "0"),
                }
            except (KeyError, ValueError):
                pass

    # ── Bybit adapters ───────────────────────────────────────────────────────

    def ingest_bybit_trades(self, trades: list):
        for t in trades:
            try:
                self._ingest(
                    price=float(t["p"]),
                    qty=float(t["v"]),
                    is_buy=(t["S"] == "Buy"),
                    ts_ms=int(t["T"]),
                )
            except (KeyError, ValueError):
                pass

    def ingest_bybit_ticker(self, data: dict):
        try:
            pct = float(data.get("price24hPcnt", 0)) * 100
            self.ticker = {
                "P": f"{pct:.2f}",
                "h": data.get("highPrice24h", "0"),
                "l": data.get("lowPrice24h", "0"),
                "v": data.get("volume24h", "0"),
            }
        except (KeyError, ValueError):
            pass

    def handle_bybit_message(self, msg: dict):
        topic = msg.get("topic", "")
        if "publicTrade" in topic:
            self.ingest_bybit_trades(msg.get("data", []))
        elif "tickers" in topic:
            self.ingest_bybit_ticker(msg.get("data", {}))

    def handle_coinbase_message(self, msg: dict):
        channel = msg.get("channel", "")
        for event in msg.get("events", []):
            if channel == "market_trades":
                self.ingest_coinbase_trades(event.get("trades", []))
            elif channel == "ticker":
                self.ingest_coinbase_ticker(event.get("tickers", []))

    def _draw_candles(self, start_row, height, start_col, width):
        all_candles = list(self.candles) + ([self.current_candle] if self.current_candle else [])
        if not all_candles:
            label = EXCHANGE_LABELS.get(self.exchange, self.exchange)
            status = f"Connecting to {label}..." if not self.connected else "Waiting for candles..."
            try:
                self.stdscr.addstr(start_row + height // 2, start_col + 4,
                                   status, curses.color_pair(4))
            except curses.error:
                pass
            return

        slot = 3   # 2 chars body + 1 gap
        label_width = 10
        chart_col = start_col + label_width
        chart_width = width - label_width
        n_candles = min(len(all_candles), chart_width // slot)
        visible = all_candles[-n_candles:]

        prices = [p for c in visible for p in (c.high, c.low)]
        if not prices:
            return
        lo, hi = min(prices), max(prices)
        price_range = hi - lo or 1

        def p2r(p):
            frac = (p - lo) / price_range
            return start_row + int((1.0 - frac) * (height - 1))

        steps = max(2, height // 4)
        for s in range(steps + 1):
            r = start_row + int(s / steps * (height - 1))
            p = hi - (s / steps) * price_range
            label = f"{p:9,.1f} "
            try:
                self.stdscr.addstr(r, start_col, label, curses.color_pair(3))
            except curses.error:
                pass

        for i, candle in enumerate(visible):
            col = chart_col + i * slot
            if col + 1 >= start_col + width:
                break

            r_wick_top = p2r(candle.high)
            r_body_top = p2r(candle.body_top)
            r_body_bot = p2r(candle.body_bot)
            r_wick_bot = p2r(candle.low)

            color = curses.color_pair(1) if candle.is_bull else curses.color_pair(2)
            is_current = (candle is self.current_candle)

            for r in range(start_row, start_row + height):
                if r < r_wick_top or r > r_wick_bot:
                    ch0, ch1 = " ", " "
                elif r_body_top <= r <= r_body_bot:
                    ch0 = "▓" if is_current else "█"
                    ch1 = "▓" if is_current else "█"
                else:
                    ch0 = "│"
                    ch1 = " "
                try:
                    self.stdscr.addstr(r, col,     ch0, color | curses.A_BOLD)
                    self.stdscr.addstr(r, col + 1, ch1, color | curses.A_BOLD)
                except curses.error:
                    pass

        xrow = start_row + height
        h_total, _ = self.stdscr.getmaxyx()
        if xrow < h_total:
            for i, candle in enumerate(visible):
                if i % 5 == 0:
                    col = chart_col + i * slot
                    label = datetime.fromtimestamp(candle.ts).strftime("%H:%M")
                    try:
                        self.stdscr.addstr(xrow, col, label, curses.color_pair(3))
                    except curses.error:
                        pass

    def draw(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()

        now = datetime.now().strftime("%H:%M:%S")
        self.stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
        self.stdscr.addstr(0, 0, "─" * (w - 1))
        label = EXCHANGE_LABELS.get(self.exchange, self.exchange)
        title = f" ₿ {label}  [{CANDLE_SECONDS}s candles] "
        self.stdscr.addstr(0, 2, title)
        self.stdscr.addstr(0, w - len(now) - 3, now)
        self.stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)

        direction = "▲" if self.last_price >= self.prev_price else "▼"
        pcolor = curses.color_pair(1) if self.last_price >= self.prev_price else curses.color_pair(2)
        pct = self.ticker.get("P", "0.00")
        self.stdscr.attron(pcolor | curses.A_BOLD)
        self.stdscr.addstr(1, 2, f"{direction} ${self.last_price:,.2f}  {pct}%")
        self.stdscr.attroff(pcolor | curses.A_BOLD)
        hi24 = float(self.ticker.get("h", 0))
        lo24 = float(self.ticker.get("l", 0))
        vol24 = float(self.ticker.get("v", 0))
        stats = f"Hi ${hi24:,.0f}  Lo ${lo24:,.0f}  Vol {vol24:,.0f} BTC"
        self.stdscr.addstr(1, 32, stats[: w - 34], curses.color_pair(4))

        total = self.buy_vol + self.sell_vol
        if total > 0:
            bar_w = w - 6   # 1 char each side for B/S labels
            buy_w = int(self.buy_vol / total * bar_w)
            sell_w = bar_w - buy_w
            try:
                self.stdscr.addstr(2, 2, "B", curses.color_pair(1) | curses.A_BOLD)
                self.stdscr.addstr(2, 3, "█" * buy_w, curses.color_pair(1) | curses.A_BOLD)
                self.stdscr.addstr(2, 3 + buy_w, "█" * sell_w, curses.color_pair(2) | curses.A_BOLD)
                self.stdscr.addstr(2, 3 + bar_w, "S", curses.color_pair(2) | curses.A_BOLD)
            except curses.error:
                pass
            buy_pct = self.buy_vol / total * 100
            self.stdscr.addstr(3, 2,
                f"BUY {buy_pct:.0f}%  SELL {100-buy_pct:.0f}%  (session)",
                curses.color_pair(5))

        div = 4
        self.stdscr.addstr(div, 0, "─" * (w - 1), curses.color_pair(3))

        split = int(w * 0.65)
        chart_start = div + 1
        chart_h = h - chart_start - 3

        if chart_h > 4:
            self._draw_candles(chart_start, chart_h, 0, split)

        for r in range(div, h - 1):
            try:
                self.stdscr.addstr(r, split, "│", curses.color_pair(3))
            except curses.error:
                pass

        fc = split + 2
        fw = w - fc - 1

        try:
            self.stdscr.addstr(div + 1, fc, "── TRADES ──"[:fw],
                               curses.color_pair(3) | curses.A_BOLD)
            self.stdscr.addstr(div + 2, fc,
                               f"{'TIME':8} {'S':1} {'PRICE':>10} {'QTY':>7}"[:fw],
                               curses.color_pair(3))
            self.stdscr.addstr(div + 3, fc, "─" * fw, curses.color_pair(3))
        except curses.error:
            pass

        feed_start = div + 4
        feed_rows = h - feed_start - 1

        if not self.connected:
            label = EXCHANGE_LABELS.get(self.exchange, self.exchange)
            msg = f"Connecting to {label}..."
            try:
                self.stdscr.addstr(feed_start + feed_rows // 2, fc,
                                   msg[:fw], curses.color_pair(4))
            except curses.error:
                pass
        else:
            significant = [t for t in self.trades if float(t["q"]) >= 0.001]
            visible_trades = significant[-(feed_rows):]

            for i, t in enumerate(reversed(visible_trades)):
                row = feed_start + (feed_rows - 1 - i)
                if row < feed_start or row >= h - 1:
                    continue
                is_buy = not t["m"]
                price = float(t["p"])
                qty = float(t["q"])
                value = price * qty
                ts = datetime.fromtimestamp(t["T"] / 1000).strftime("%H:%M:%S")
                color = curses.color_pair(1) if is_buy else curses.color_pair(2)
                bold = curses.A_BOLD if value > 10000 else 0
                side = "B" if is_buy else "S"
                line = f"{ts} {side} {price:>10,.1f} {qty:>7.3f}"
                try:
                    self.stdscr.addstr(row, fc, line[:fw], color | bold)
                except curses.error:
                    pass

        try:
            footer = f" q quit │ {CANDLE_SECONDS}s candles │ {EXCHANGE_LABELS.get(self.exchange, self.exchange)} "
            self.stdscr.addstr(h - 1, 0, footer[: w - 1], curses.color_pair(6))
        except curses.error:
            pass

        self.stdscr.refresh()

    def handle_message(self, msg):
        stream = msg.get("stream", "")
        data = msg.get("data", {})
        if "aggTrade" in stream:
            self.ingest_trade(data)
        elif "ticker" in stream:
            self.ticker = data


async def binance_ws_loop(tui):
    while tui.running:
        try:
            async with websockets.connect(BINANCE_WS, ping_interval=20) as ws:
                while tui.running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        tui.handle_message(json.loads(raw))
                    except asyncio.TimeoutError:
                        pass
        except Exception:
            await asyncio.sleep(2)


async def bybit_ws_loop(tui):
    while tui.running:
        try:
            async with websockets.connect(BYBIT_WS, ping_interval=20) as ws:
                await ws.send(json.dumps({
                    "op": "subscribe",
                    "args": ["publicTrade.BTCUSDT", "tickers.BTCUSDT"],
                }))
                while tui.running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        tui.handle_bybit_message(json.loads(raw))
                    except asyncio.TimeoutError:
                        pass
        except Exception:
            await asyncio.sleep(2)


async def coinbase_ws_loop(tui):
    channels = ["market_trades", "ticker"]
    while tui.running:
        try:
            async with websockets.connect(COINBASE_WS, ping_interval=20) as ws:
                for ch in channels:
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "product_ids": ["BTC-USD"],
                        "channel": ch,
                    }))
                while tui.running:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        tui.handle_coinbase_message(json.loads(raw))
                    except asyncio.TimeoutError:
                        pass
        except Exception:
            await asyncio.sleep(2)


async def input_loop(tui):
    while tui.running:
        try:
            key = tui.stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                tui.running = False
        except Exception:
            pass
        await asyncio.sleep(0.05)


async def draw_loop(tui):
    while tui.running:
        tui.draw()
        await asyncio.sleep(0.1)


async def _main(stdscr, exchange: str):
    tui = TUI(stdscr, exchange=exchange)
    if exchange == "coinbase":
        loop = coinbase_ws_loop
    elif exchange == "bybit":
        loop = bybit_ws_loop
    else:
        loop = binance_ws_loop
    await asyncio.gather(loop(tui), draw_loop(tui), input_loop(tui))


def run():
    """Entry point for the btc-tui command."""
    parser = argparse.ArgumentParser(
        description="BTC live trade terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--exchange",
        choices=["binance", "coinbase", "bybit"],
        default="binance",
        help="Data source (default: binance)",
    )
    args = parser.parse_args()
    try:
        curses.wrapper(lambda s: asyncio.run(_main(s, args.exchange)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()

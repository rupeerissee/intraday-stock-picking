# ============================================================================
#  INTRADAY TRADING ANALYZER  (NSE / BSE · Google Colab · built from scratch)
# ============================================================================
#  WHAT THIS DOES
#  --------------
#  Fetches ALL minute data of the current NSE session (9:15 -> 15:30 IST),
#  snapshots the *current* price at whatever time you run it (e.g. 12:15),
#  checks the MARKET first (NIFTY trend + India VIX), then the company
#  fundamentals, runs 8 popular intraday strategies, and gives you a full trade
#  plan:  "BUY at 12:20 around Rs 490, SL Rs 485, TARGET Rs 500".
#
#  If the plan is NOT safe (bad risk:reward, unrealistic target, weak
#  fundamentals, low trend confidence, choppy/risk-off market, too late in the
#  session, daily loss cap hit...), it shows explicit WARNINGS and automatically
#  scans the whole stock universe to name the BETTER STOCK to trade instead.
#
#  USAGE (one line - type any stock name, you get the whole answer):
#      trade_call("NALCO")                        # details + verdict + suggestion
#      trade_recommendation("SBIN", user_target=500)
#      trade_recommendation("INFY", user_target=1100, replay_at="12:15")
#      scan_universe()          /  best_trade_now()  /  journal_report()
#
#  BUILD PLAN  (basic -> advanced, all implemented below)
#  -------------------------------------------------------
#  LEVEL 1  Basics
#    L1.1  IST market clock (session phases, seconds remaining, no-entry cutoff)
#    L1.2  Data layer: 1-min candles 9:15->now, 5-min rehash, last-30-day dailies
#    L1.3  Snapshot: current price / day Open-High-Low-Close / volume so far
#  LEVEL 2  Technical engine
#    L2.1  Indicators: VWAP, EMA(9/20/50), SMA, RSI(14), MACD, ATR(14),
#          Bollinger(20,2), Supertrend(10,3), volume trend, ORB(15 min)
#    L2.2  Multi-signal trend detector: regression slope (30m/60m/session),
#          price vs VWAP/EMA, higher-high/higher-low structure ->
#          STRONG_UP / UP / SIDEWAYS / DOWN / STRONG_DOWN + confidence %
#  LEVEL 3  Fundamental gate (the "is this stock safe to trade" check)
#    L3.1  Pull P/E, P/B, D/E, ROE, margins, mkt-cap, liquidity, volatility
#    L3.2  Quality score 0-10 with hard REMOVAL rules (illiquid / penny / huge loss)
#  LEVEL 4  Strategy ensemble (8 popularly-used intraday methods)
#    S1 ORB Breakout    S2 VWAP Pullback    S3 EMA 9/20 Crossover
#    S4 RSI Reversal    S5 Supertrend Follow S6 VWAP Fade (mean-revert)
#    S7 Relative Strength vs NIFTY (leader/laggard)  S8 Gap Fill Fade
#    -> weighted voting (trend alignment x market regime x your own journal)
#    -> final call: BUY / SELL / NO TRADE
#  LEVEL 5  Risk & trade-plan engine
#    L5.1  ATR-based stops & targets - every target is built at >= 2R so a
#          partial booking at 1.5R always exists (min R:R enforced)
#    L5.2  Position sizing: risk only CONFIG.risk_pct of capital per trade,
#          additionally capped by intraday notional leverage
#    L5.3  Target-feasibility math: is "sell at 500" reachable with the ATR
#          room left in the session? (directly answers your 490 -> 500 case)
#    L5.4  Trend veto: while a trend is detected, a purely counter-trend idea
#          is down-weighted and then rejected as NO TRADE
#  LEVEL 6  Safety / warning system
#    L6.1  12 automated warnings (risk:reward, target feasibility, counter-trend,
#          quality gate, late entry, stale data, costs, volatility, veto...)
#    L6.2  If the stock is blocked -> auto-scan the watchlist, rank the
#          alternatives, and hand back full trade plans for the better stocks
#  LEVEL 7  Reports & replay
#    L7.1  Matplotlib intraday chart: VWAP/EMAs/ORB + entry/SL/target markers
#    L7.2  Full console trade-call report
#    L7.3  replay_at="12:15" - re-run the whole analysis as the clock stood there
#  LEVEL 8  Quality assurance
#    L8.1  40+ offline self-tests shipped inside this file (trend, sizing, R:R
#          invariant, warnings, vetoes, regime maths, journal, scan, one-command
#          entry) - run with:  --selftest / run_self_tests()
#    L8.2  Deep acceptance suite in test_intraday_acceptance.py: 200+ checks over
#          14 groups (clock, indicators, data layer, risk, fundamentals,
#          ensemble, safety text, chart, Colab compatibility, regime gate,
#          trade journal, universe scan + one-command UX, live Yahoo data)
#          run with:  python test_intraday_acceptance.py   (or --offline)
#  LEVEL 9  Market regime gate (trade-or-don't-trade-the-market check)
#    L9.1  NIFTY 50 daily trend (EMA50/200 + 20-day slope) + live 5-min VWAP
#          position, VWAP-crossing count (chop) and gap size
#    L9.2  India VIX level / one-day spike / 20-day percentile, Bank Nifty slope
#          -> TREND_UP / TREND_DOWN / CHOP / MIXED / RISK_OFF / UNKNOWN
#    L9.3  Each label maps to per-strategy weights, a position-size multiplier
#          and an allow-new-entries switch; RISK_OFF vetoes every fresh trade
#  LEVEL 10 Trade journal & feedback loop
#    L10.1 every live plan is appended to trade_journal.csv (date/time/levels)
#    L10.2 settle_journal() replays the real bars after the close and scores the
#          outcome in R (stop hit / target hit / 15:15 square-off)
#    L10.3 strategy_scoreboard() -> win %, avg R, expectancy, profit factor per
#          strategy; a proven-negative strategy is down-weighted in the ensemble
#    L10.4 daily loss cap (-2R) and max-trades circuit breaker stop new entries
#  LEVEL 11 Universe scan
#    L11.1 scan_universe(): the full engine over CONFIG.universe, ranked best first
#    L11.2 best_trade_now(): the single "what should I trade right now" answer
#    L11.3 3-minute session cache so a 20-stock scan stays inside free quotas
#  LEVEL 12 One-command user interface
#    L12.1 trade_call("NALCO")  -> regime + details + verdict + replacement stock
#    L12.2 stock_details()      -> everything knowable about one symbol, honestly
#    L12.3 load_session_from_csv() -> analyse a broker 1-min export when Yahoo has
#          no feed for the symbol (NALCO and friends)
#    L12.4 export_call()        -> JSON snapshot of any analysis
#
#  DATA HONESTY: nothing is invented. Missing fundamentals stay None, a stale or
#  non-today session is flagged, failed symbols are named, and post-close runs
#  are clearly labelled "NOT an actionable signal".
#
#  GOOGLE COLAB SETUP (this file is a LIBRARY - import it, don't run it as a cell):
#    Cell 1:  !pip install -q yfinance pandas numpy matplotlib
#    Cell 2:  Files sidebar -> Upload to session -> Intraday_Trader_Colab.py
#             (and test_intraday_acceptance.py if you want the deep suite)
#    Cell 3:  from Intraday_Trader_Colab import *
#    Cell 4:  run_self_tests()          -> SELF-TESTS: ALL PASS
#    Cell 5:  trade_call("RELIANCE")    -> details + BUY/SELL/NO-TRADE + suggestion
#    Cell 6:  %run test_intraday_acceptance.py     -> 200+ PASS lines
#    (Running the whole file in one cell is harmless - it just prints these
#     steps instead of trying to trade on kernel command-line arguments.)
# ============================================================================

from __future__ import annotations

import logging
import math
import os
import sys
import json
import shutil
import tempfile
import warnings
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
# Yahoo's own logger dumps "HTTP Error 404 / 1 Failed download" noise on every
# retry. Our DataError message says the same thing clearly, so silence theirs
# (we still detect and report the failure ourselves - nothing is hidden).
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Console-safe output (Windows cp1252 terminals choke on unicode symbols).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

IST_TZ = "Asia/Kolkata"            # pytz/tzlocal-safe name ('IST' alias is unreliable)
IST = pd.Timestamp("2000-01-01", tz=IST_TZ).tz  # IST timezone object
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
NO_ENTRY_AFTER = time(14, 45)   # keep >=45 min of trade time, else no new trades


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
@dataclass
class Config:
    capital: float = 100_000.0        # Rs available for intraday
    risk_pct: float = 0.01            # risk max 1% of capital per trade
    risk_reward_min: float = 1.5      # reject plans below this R:R
    round_trip_cost_pct: float = 0.12  # brokerage+STT+slippage, % of turnover (both legs)
    max_leverage: float = 5.0         # intraday notional cap vs capital
    orb_minutes: int = 15             # opening range = first 15 min
    orb_valid_minutes: int = 120      # an ORB breakout stays tradable for 2 h
    cross_valid_bars: int = 5         # breakout/crossover must be this fresh
    min_quality_score: float = 4.0    # 0-10 fundamental gate
    min_avg_volume: int = 50_000      # >=50k shares/day avg volume (liquidity)
    max_atr_pct: float = 3.0          # 5-min ATR % of price above this = too wild
    watchlist: tuple = (              # used to suggest alternatives (edit freely)
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "TATASTEEL.NS",
    )
    # ---- LEVEL 9: market regime gate (NIFTY + Bank Nifty + India VIX) -------
    regime_enabled: bool = True
    index_symbol: str = "^NSEI"
    bank_symbol: str = "^NSEBANK"
    vix_symbol: str = "^INDIAVIX"
    vix_risk_off: float = 16.0        # VIX at/above this = event day, no new trades
    vix_elevated: float = 13.5        # nervous market: half size, wider stops
    vix_spike_pct: float = 8.0        # one-day VIX jump that large = event risk
    gap_caution_pct: float = 0.6      # NIFTY gap bigger than this -> ORB unreliable
    chop_vwap_crossings: int = 6      # VWAP cross count on 5-min that means 'no trend'
    trend_slope_min: float = 0.03     # NIFTY 20-day slope, % per bar, to call a trend
    # ---- LEVEL 10: trade journal / expectancy -------------------------------
    journal_file: str = "trade_journal.csv"
    journal_auto: bool = True         # log every live call automatically
    daily_loss_cap_r: float = 2.0     # stop opening trades after -2R in a day
    max_trades_per_day: int = 5
    mute_negative_expectancy: bool = True   # down-weight strategies the journal
                                            # proved unprofitable (>= min_trades)
    min_trades_to_judge: int = 8
    # ---- LEVEL 11: scan universe (must have a working free feed) ------------
    universe: tuple = (
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "SBIN.NS", "ITC.NS", "LT.NS", "AXISBANK.NS", "TATASTEEL.NS",
        "TITAN.NS", "BAJFINANCE.NS", "MARUTI.NS", "TATAMOTORS.NS", "TATACHEM.NS",
        "ONGC.NS", "COALINDIA.NS", "JINDALSTEL.NS", "SAIL.NS", "IRCTC.NS",
    )
    # Yahoo renames/drops NSE symbols after demergers - map the old name to a live one
    aliases: dict = field(default_factory=lambda: {
        "TATAMOTORS": "TMCV.NS",     # Tata Motors PV after the 2025 demerger
        "TATAMOTORS.NS": "TMCV.NS",
    })
    # Symbols with no free intraday feed at all (verified Oct 2026) - the tool
    # says so instead of inventing data, then suggests a tradeable substitute.
    no_feed_expected: tuple = ("NALCO", "NALCO.NS", "NALCO.BO")
    # ---- ONE-LINE QUICK START ----------------------------------------------
    # Set this and re-run the file (or the import cell) to get an immediate
    # recommendation without typing another command:
    #   ""          -> just load the functions (the safe default, no internet)
    #   "BEST"      -> scan the universe and tell you what to trade RIGHT NOW
    #   "SCAN"      -> print the whole ranked universe table
    #   "ASK"       -> interactive: it prompts you to type a stock name, then
    #                  analyses it and asks for the next one (blank line to stop)
    #   "RELIANCE"  -> full trade_call() on that one stock (any name works)
    auto_analyze: str = ""


CONFIG = Config()

# ---------------------------------------------------------------------------
# Runtime environment helpers (Colab / Jupyter / plain terminal)
# ---------------------------------------------------------------------------
def _notebook_shell() -> str:
    """'' when plain Python, else the IPython shell class name."""
    try:
        from IPython import get_ipython
        ip = get_ipython()
        return type(ip).__name__ if ip is not None else ""
    except Exception:
        return ""


def in_notebook() -> bool:
    """True inside a Jupyter/Colab kernel (including when the whole file is
    pasted into a cell, which is what `__name__ == '__main__'` looks like there)."""
    if _notebook_shell() == "ZMQInteractiveShell":
        return True
    return "google.colab" in sys.modules or "ipykernel" in sys.modules


def _parse_cli_args(argv: list) -> tuple:
    """Pull (ticker, target, replay) out of argv, ignoring kernel/Jupyter flags.

    A Colab kernel launches with argv like ['ipykernel_launcher.py', '-f',
    '/root/.../kernel-xxxx.json'] - those must never be read as a price.
    """
    value_flags = {"-f", "--file", "--config", "--ConnectionFile"}
    positional, skipping = [], False
    for a in list(argv)[1:]:
        if skipping:
            skipping = False
            continue
        if a in value_flags:
            skipping = True
            continue
        if a.startswith("-"):
            continue
        # ignore anything that looks like a path/module, not a stock symbol
        if any(sep in a for sep in ("/", "\\")) or a.lower().endswith((".py", ".json", ".txt", ".ipynb")):
            continue
        positional.append(a)
    ticker = positional[0] if positional else None
    target = replay = None
    if len(positional) > 1:
        try:
            target = float(positional[1])
        except ValueError:
            replay, target = positional[1], None      # tolerate 'ticker 12:15'
    if len(positional) > 2 and replay is None:
        replay = positional[2]
    return ticker, target, replay


# ---------------------------------------------------------------------------
# LEVEL 1.1 - IST market clock
# ---------------------------------------------------------------------------
def ist_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz=IST_TZ)


def market_status(ts: pd.Timestamp | None = None) -> dict:
    ts = ts or ist_now()
    t = ts.time()
    if t < MARKET_OPEN:
        phase, label = "PRE_OPEN", "Market opens at 9:15 IST"
    elif t > MARKET_CLOSE or ts.weekday() >= 5:
        phase, label = "CLOSED", "Market closed (15:30 IST) / weekend"
    elif t >= NO_ENTRY_AFTER:
        phase, label = "LATE_SESSION", "Open, but too late for NEW intraday trades"
    else:
        phase, label = "OPEN", "Market open - live trading window"
    if phase == "CLOSED":
        mins_left = 0
    else:
        close_dt = ts.normalize() + pd.Timedelta(hours=MARKET_CLOSE.hour,
                                                 minutes=MARKET_CLOSE.minute)
        mins_left = max(0, int((close_dt - ts).total_seconds() // 60))
    return {"phase": phase, "label": label, "ist_time": ts, "minutes_left": mins_left}


# ---------------------------------------------------------------------------
# LEVEL 1.2/1.3 - Data layer
# ---------------------------------------------------------------------------
@dataclass
class Session:
    ticker: str
    m1: pd.DataFrame            # 1-min candles 9:15 -> now (truncated session)
    m5: pd.DataFrame            # 5-min resample of m1
    daily: pd.DataFrame         # last ~30 trading days
    snapshot: dict              # current price / OHLC / volume / time
    fundamentals: dict
    data_note: str = ""         # honest note when something is fallback/stale
    is_replay: bool = False     # True when the session was cut at replay_at


def resolve_ticker(ticker: str) -> str:
    """Accept 'TATASTEEL', 'tatasteel', 'TATASTEEL.NS' -> NSE 'TATASTEEL.NS'.

    CONFIG.aliases is applied first, so a symbol Yahoo renamed after a demerger
    (TATAMOTORS -> TMCV) still resolves instead of failing.
    """
    t = ticker.strip().upper()
    t = CONFIG.aliases.get(t, t)
    if "." in t:
        return t
    return t + ".NS"


def _exchange_fallbacks(ticker: str) -> list:
    base = ticker.split(".")[0]
    out = []
    for suf in (".NS", ".BO"):
        c = base + suf
        if c != ticker:
            out.append(c)
    return out


def _dl(ticker: str, **kw) -> pd.DataFrame:
    try:
        d = yf.download(ticker, progress=False, auto_adjust=True, **kw)
    except Exception:
        d = None
    if d is not None and not d.empty:
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        return d
    return pd.DataFrame()


def _download_1m(ticker: str, now: pd.Timestamp) -> tuple:
    """1-min bars for the latest session. Returns (df, ticker_actually_used)."""
    today = now.normalize()
    start = (today - pd.Timedelta(days=2)).tz_localize(None).to_pydatetime()
    end = (today + pd.Timedelta(days=1)).tz_localize(None).to_pydatetime()
    for t in [ticker] + _exchange_fallbacks(ticker):
        d = _dl(t, period="1d", interval="1m")
        if d.empty:
            d = _dl(t, start=start, end=end, interval="1m")
        if not d.empty:
            return d, t
    return pd.DataFrame(), ticker


def _minutes(ts_index):
    """Minutes-since-midnight for a DatetimeIndex (vectorised)."""
    return ts_index.hour * 60 + ts_index.minute


def fetch_session(ticker: str, require_today: bool = True,
                  replay_at: str | None = None) -> Session:
    """replay_at: 'HH:MM' IST clock - pretend the analysis ran at that time
    (data after it is discarded). Useful for reviewing the 12:15 situation."""
    ticker = resolve_ticker(ticker)
    now = ist_now()
    m1, ticker = _download_1m(ticker, now)
    if m1.empty:
        raise DataError(_no_feed_message(ticker))
    daily = _dl(ticker, period="1mo", interval="1d")
    return _session_from_1m(ticker, m1, daily, fetch_fundamentals(ticker),
                            require_today=require_today, replay_at=replay_at)


def _no_feed_message(ticker: str) -> str:
    """Honest explanation when Yahoo has no bars - naming what was tried and
    how to still analyse the stock with a broker CSV export."""
    alt = ", ".join(_exchange_fallbacks(ticker)) or "no alternates"
    ideas = ", ".join(s.split(".")[0] for s in CONFIG.watchlist[:5])
    help_line = ""
    if ticker.split(".")[0] in CONFIG.no_feed_expected:
        help_line = ("\n  - this symbol is KNOWN to have no free intraday feed. If you "
                     "export 1-min bars\n    from your broker (Zerodha/StockGraph CSV), "
                     "analyse them directly:\n      load_session_from_csv('NALCO_1min.csv', "
                     "'NALCO')")
    return (
        f"No 1-minute data on Yahoo for {ticker} (also tried {alt}).\n"
        f"  - symbol may be renamed/delisted after a corporate split "
        f"(e.g. TATAMOTORS currently has no Yahoo feed)\n"
        f"  - or it needs its exact NSE code (e.g. 'RELIANCE', 'HDFCBANK')"
        f"{help_line}\n  Symbols that do work right now: {ideas}"
    )


def _session_from_1m(ticker: str, raw: pd.DataFrame, daily: pd.DataFrame | None = None,
                     fundamentals: dict | None = None, require_today: bool = True,
                     replay_at: str | None = None) -> Session:
    """Turn a raw 1-min frame (Yahoo OR broker CSV) into a clean Session:
    IST index, single latest session only, 5-min resample, snapshot, notes."""
    now = ist_now()
    today = now.normalize()
    m1 = raw.copy()
    if isinstance(m1.columns, pd.MultiIndex):
        m1.columns = m1.columns.get_level_values(0)
    missing = [c for c in ("Open", "High", "Low", "Close", "Volume") if c not in m1.columns]
    if missing:
        raise DataError(f"{ticker}: bars are missing column(s) {missing} - "
                        f"cannot build candles (nothing is invented).")
    m1.index = m1.index.tz_convert(IST_TZ) if m1.index.tz else m1.index.tz_localize(IST_TZ)
    m1 = m1[~m1.index.duplicated(keep="last")].sort_index()

    # keep only the most recent complete/partial NSE session (9:15-15:30 IST)
    mins = np.asarray(_minutes(m1.index))
    days = m1.index.normalize()
    day_counts = pd.Series(np.asarray(days)[mins >= 9 * 60 + 16]).value_counts()
    if day_counts.empty:
        raise DataError(f"Only pre-open data for {ticker}.")
    session_day = day_counts.index.max()
    in_session = (np.asarray(days) == session_day) & (mins >= 9 * 60 + 15) & (mins <= 15 * 60 + 30)
    m1 = m1[in_session]
    m1 = m1.dropna(subset=["Close"])

    is_replay = False
    if replay_at:
        h, m = map(int, str(replay_at).split(":"))
        cut = int(h) * 60 + int(m)
        keep = np.asarray(_minutes(m1.index)) <= cut
        if not keep.any():
            raise DataError(f"replay_at {replay_at} is before the session data starts.")
        m1, is_replay = m1[keep], True

    note = ""
    if require_today and session_day != today:
        note = (f"WARNING: latest complete session is {session_day.date()} "
                f"(today {today.date()} has no data - holiday/pre-open/run after close).")

    m5 = m1.resample("5min").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last",
         "Volume": "sum"}).dropna()

    last = m1.iloc[-1]
    snapshot = {
        "time": m1.index[-1], "price": float(last["Close"]),
        "open": float(m1["Open"].iloc[0]), "high": float(m1["High"].max()),
        "low": float(m1["Low"].min()),
        "volume": int(m1["Volume"].sum()),
        "elapsed_min": len(m1),
        "day_change_pct": round(100 * (float(last["Close"]) - float(m1["Open"].iloc[0]))
                                / float(m1["Open"].iloc[0]), 2),
    }
    return Session(ticker, m1, m5, daily if daily is not None else pd.DataFrame(),
                   snapshot, fundamentals or {}, note, is_replay)


# Columns broker terminal exports use for the same thing (very inconsistent).
_CSV_COLS = {"Open": ("open", "o", "ohlc_open"),
             "High": ("high", "h", "ohlc_high"),
             "Low": ("low", "l", "ohlc_low"),
             "Close": ("close", "c", "ltp", "last_price", "closed"),
             "Volume": ("volume", "vol", "v", "traded_quantity")}


def load_session_from_csv(path: str, ticker: str | None = None,
                          replay_at: str | None = None,
                          require_today: bool = False) -> Session:
    """LEVEL 12.2 - analyse a stock Yahoo has no feed for (NALCO etc.) from a
    1-min CSV you exported from your broker (Zerodha Kite/StockGraph/Neural).

    Accepts whatever column names that terminal used - it only needs a
    date/time pair (or one datetime column) plus OHLCV. Nothing is invented:
    if the file has no OHLCV the call fails loudly instead of guessing.
    """
    raw = pd.read_csv(path)
    low = {str(c).strip().lower(): c for c in raw.columns}

    def pick(names):
        for n in names:
            if n in low:
                return low[n]
        return None

    dt_col = pick(("datetime", "timestamp", "ohlc_date", "date_time", "dt"))
    d_col, t_col = pick(("date", "day", "stamp_date")), pick(("time", "mins", "stamp_time"))
    if dt_col is not None:
        idx = pd.to_datetime(raw[dt_col], dayfirst=True)
    elif d_col is not None and t_col is not None:
        idx = pd.to_datetime(raw[d_col].astype(str) + " " + raw[t_col].astype(str), dayfirst=True)
    elif d_col is not None:
        idx = pd.to_datetime(raw[d_col], dayfirst=True)
    else:
        raise DataError(f"{path}: no date/time column found (has {list(raw.columns)[:8]}...) "
                        f"- a broker 1-min export is needed.")
    out = pd.DataFrame(index=pd.DatetimeIndex(idx))
    for canon, cands in _CSV_COLS.items():
        src = pick(cands)
        if src is None:
            raise DataError(f"{path}: column for {canon} not found (looked for {list(cands)}).")
        # .to_numpy() is essential: `out` is keyed by the parsed datetime index
        # while `raw` still has its integer RangeIndex - assigning the Series
        # directly would align on label, match nothing and silently fill NaN.
        out[canon] = pd.to_numeric(raw[src], errors="coerce").to_numpy()
    out = out.dropna(subset=["Close"])
    if out.index.tz is not None:
        out.index = out.index.tz_convert(IST_TZ)
    else:
        out.index = out.index.tz_localize(IST_TZ)
    sym = resolve_ticker(ticker or os.path.basename(path).rsplit(".", 1)[0])
    note_src = f"{os.path.basename(path)} (broker CSV)"
    sess = _session_from_1m(sym, out, _dl(sym, period="1mo", interval="1d"),
                            fetch_fundamentals(sym), require_today, replay_at)
    sess.data_note = (sess.data_note + " | " if sess.data_note else "") + \
        f"bars from {note_src} - indicators are exact, fundamentals may be stale"
    return sess


class DataError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# LEVEL 3.1 - Fundamentals (never fabricates - missing stays None)
# ---------------------------------------------------------------------------
def fetch_fundamentals(ticker: str) -> dict:
    out = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    keys = {"marketCap": "market_cap", "trailingPE": "pe", "priceToBook": "pb",
            "debtToEquity": "de", "returnOnEquity": "roe",
            "operatingMargins": "op_margin", "profitMargins": "net_margin",
            "beta": "beta", "averageVolume": "avg_vol",
            "averageVolume3Month": "avg_vol_3m", "fiftyTwoWeekHigh": "wk52_high",
            "fiftyTwoWeekLow": "wk52_low", "shortName": "name"}
    for src, dst in keys.items():
        v = info.get(src)
        out[dst] = v if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)) else None
    out["avg_vol_live"] = None
    if out["avg_vol"] is None and out["avg_vol_3m"] is None:
        # fallback: mean daily volume from the 1-month daily frames we fetched
        try:
            d = yf.download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=True)
            if d is not None and not d.empty:
                if isinstance(d.columns, pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                out["avg_vol_live"] = int(d["Volume"].mean())
                out["avg_vol_src"] = "computed from 1-mo daily bars"
        except Exception:
            pass
    return out


def quality_gate(sess: Session) -> dict:
    """LEVEL 3.2 - score 0-10 + HARD removal rules."""
    f, price = sess.fundamentals, sess.snapshot["price"]
    score, flags, removals = 10.0, [], []

    vol = f.get("avg_vol") or f.get("avg_vol_3m") or f.get("avg_vol_live")
    if vol is None:
        score -= 1.5; flags.append("Volume data unavailable - liquidity unverified")
    elif vol < CONFIG.min_avg_volume:
        removals.append(f"Average volume {vol:,.0f} < {CONFIG.min_avg_volume:,} - too illiquid for intraday")
    if f.get("market_cap") is not None and f["market_cap"] < 500e7:
        removals.append("Micro-cap (< Rs 50 Cr) - manipulation risk, avoid intraday")
    if f.get("pe") is not None and f["pe"] < 0:
        score -= 2; flags.append("Company is loss-making (negative P/E)")
    if f.get("de") is not None and f["de"] > 200:
        score -= 2; flags.append(f"High debt-to-equity {f['de']:.0f}%")
    if f.get("roe") is not None:
        if f["roe"] < 0.05: score -= 1; flags.append(f"Weak ROE {f['roe']*100:.1f}%")
        elif f["roe"] > 0.15: score += 0.5
    if f.get("op_margin") is not None and f["op_margin"] < 0.02:
        score -= 1; flags.append(f"Thin operating margin {f['op_margin']*100:.1f}%")
    if f.get("wk52_high") and f.get("wk52_low") and price:
        rng = f["wk52_high"] - f["wk52_low"]
        pos = (price - f["wk52_low"]) / rng if rng > 0 else 0.5
        if pos > 0.95: flags.append("Price in 52-wk high zone - limited upside room")
        if pos < 0.05: flags.append("Price near 52-wk low - falling knife risk")
    atr_pct = sess.snapshot["price"] and _atr_pct(sess)
    if atr_pct and atr_pct > CONFIG.max_atr_pct:
        removals.append(f"5-min ATR {atr_pct:.1f}% > {CONFIG.max_atr_pct}% - extreme volatility")

    return {"score": round(max(0.0, min(10.0, score)), 1), "flags": flags,
            "removals": removals, "passed": len(removals) == 0 and score >= CONFIG.min_quality_score}


def _atr_pct(sess: Session) -> float | None:
    if len(sess.m5) < 15:
        return None
    a = atr(sess.m5["High"], sess.m5["Low"], sess.m5["Close"]).iloc[-1]
    return None if pd.isna(a) else 100 * a / sess.snapshot["price"]


# ---------------------------------------------------------------------------
# LEVEL 2.1 - Indicators (vectorised, hand-rolled - no external TA library)
# ---------------------------------------------------------------------------
def ema(s: pd.Series, n: int) -> pd.Series: return s.ewm(span=n, adjust=False).mean()
def sma(s: pd.Series, n: int) -> pd.Series: return s.rolling(n).mean()

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)

def macd(close: pd.Series):
    line = ema(close, 12) - ema(close, 26)
    sig = ema(line, 9)
    return line, sig, line - sig

def atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()

def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    mid, sd = sma(close, n), close.rolling(n).std()
    return mid + k * sd, mid, mid - k * sd

def supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0) -> pd.DataFrame:
    """Supertrend(10,3) on any OHLCV frame - TradingView semantics.

    Returns columns: line (trailing stop) and dir (+1 bullish / -1 bearish).
    Bullish: line is the support band (below price) and may only rise.
    Bearish: line is the resistance band (above price) and may only fall.
    The trend flips when price closes through the opposite band.
    """
    hl2 = (df["High"] + df["Low"]) / 2
    a = atr(df["High"], df["Low"], df["Close"], period)
    sup, res = (hl2 - mult * a).values, (hl2 + mult * a).values
    c = df["Close"].values
    n = len(df)
    fsup = np.full(n, np.nan)     # final support band (ratchets up)
    fres = np.full(n, np.nan)     # final resistance band (ratchets down)
    trd = np.ones(n, dtype=int)
    line = np.full(n, np.nan)
    for i in range(n):
        if i == 0 or np.isnan(fsup[i - 1]):
            fsup[i], fres[i] = sup[i], res[i]
            trd[i] = 1 if c[i] >= hl2.values[i] else -1
        else:
            # support only tightens upward unless price closed above it yesterday
            fsup[i] = sup[i] if c[i - 1] > fsup[i - 1] else max(sup[i], fsup[i - 1])
            fres[i] = res[i] if c[i - 1] < fres[i - 1] else min(res[i], fres[i - 1])
            if c[i] < fsup[i - 1]:
                trd[i] = -1
            elif c[i] > fres[i - 1]:
                trd[i] = 1
            else:
                trd[i] = trd[i - 1]
        line[i] = fsup[i] if trd[i] == 1 else fres[i]
    return pd.DataFrame({"line": line, "dir": trd}, index=df.index)


def st_direction(df: pd.DataFrame, period: int = 10, mult: float = 3.0) -> int:
    return int(supertrend(df, period, mult)["dir"].iloc[-1])


def vwap(df: pd.DataFrame) -> pd.Series:
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    return (tp * df["Volume"]).cumsum() / df["Volume"].cumsum().replace(0, np.nan)


# ---------------------------------------------------------------------------
# LEVEL 2.2 - Trend detector
# ---------------------------------------------------------------------------
def _slope_pct(close: pd.Series) -> float:
    """Linear-regression slope as % of price over the series window."""
    if len(close) < 5:
        return 0.0
    x = np.arange(len(close), dtype=float)
    y = close.values.astype(float)
    k = np.polyfit(x, y, 1)[0]
    return 100 * k / y.mean()

def detect_trend(sess: Session) -> dict:
    c, vw = sess.m1["Close"], vwap(sess.m1)
    price = sess.snapshot["price"]
    s30, s60, s_all = (_slope_pct(c.tail(30)), _slope_pct(c.tail(60)), _slope_pct(c))
    win = min(30, len(sess.m1))
    h = sess.m1["High"].tail(win)
    hi_struct = (h.iloc[-win // 2:].mean() > h.iloc[:win // 2].mean()) if win >= 20 else None

    votes, reasons = 0, []
    def check(cond, w, txt):
        """Only contributes when `cond` is a definite True/False (None = no data)."""
        nonlocal votes
        if cond is None: return
        if cond:
            votes += w
            reasons.append(f"+ {txt} (weight {w})")

    check(s30 > 0.02, 2, f"30-min slope rising {s30:+.3f}%/bar")
    check(s30 < -0.02, -2, f"30-min slope falling {s30:+.3f}%/bar")
    check(s60 > 0.01, 1, f"60-min slope rising {s60:+.3f}%/bar")
    check(s60 < -0.01, -1, f"60-min slope falling {s60:+.3f}%/bar")
    check(price > vw.iloc[-1], 2, f"Price above VWAP {vw.iloc[-1]:.2f}")
    check(price < vw.iloc[-1], -2, f"Price below VWAP {vw.iloc[-1]:.2f}")
    e20 = ema(c, 20).iloc[-1]
    check(price > e20, 1, f"Price above EMA20 {e20:.2f}")
    check(price < e20, -1, f"Price below EMA20 {e20:.2f}")
    check(hi_struct is True, 1, "making higher highs (last half vs first half of window)")
    check(hi_struct is False, -1, "making lower highs")
    if not reasons:
        reasons.append("no directional edge - insufficient data/flat")

    label = ("STRONG_UP" if votes >= 5 else "UP" if votes >= 2 else
             "SIDEWAYS" if votes > -2 else "DOWN" if votes > -5 else "STRONG_DOWN")
    conf = min(95, 40 + 9 * abs(votes))
    return {"label": label, "confidence": conf, "votes": votes,
            "slopes": {"30m": round(s30, 4), "60m": round(s60, 4), "session": round(s_all, 4)},
            "reasons": reasons}


# ---------------------------------------------------------------------------
# LEVEL 9 - Market regime gate (NIFTY 50 + Bank Nifty + India VIX)
#   Answers "should I be trading at all today, and which style works?" before
#   any individual stock is judged. Free Yahoo data only (verified working:
#   ^NSEI, ^NSEBANK, ^INDIAVIX daily + ^NSEI 5-min intraday).
# ---------------------------------------------------------------------------
_MARKET_CACHE: dict = {}          # {(date, replay): (fetched_at, ctx)}

STRATEGY_NAMES = ("ORB-15 Breakout", "VWAP Pullback", "EMA 9/20 Crossover",
                  "RSI Reversal", "Supertrend Follow", "VWAP Fade",
                  "Relative Strength Momentum", "Gap Fill Fade")

_REGIME_WEIGHTS = {
    #                       trend-followers   mean-reverters
    "TREND_UP":   {"ORB-15 Breakout": 1.15, "VWAP Pullback": 1.15,
                   "EMA 9/20 Crossover": 1.10, "Supertrend Follow": 1.15,
                   "Relative Strength Momentum": 1.20,
                   "RSI Reversal": 0.80, "VWAP Fade": 0.60, "Gap Fill Fade": 0.70},
    "TREND_DOWN": {"ORB-15 Breakout": 1.15, "VWAP Pullback": 1.15,
                   "EMA 9/20 Crossover": 1.10, "Supertrend Follow": 1.15,
                   "Relative Strength Momentum": 1.20,
                   "RSI Reversal": 0.80, "VWAP Fade": 0.60, "Gap Fill Fade": 0.70},
    "CHOP":       {"ORB-15 Breakout": 0.55, "VWAP Pullback": 0.85,
                   "EMA 9/20 Crossover": 0.60, "Supertrend Follow": 0.70,
                   "Relative Strength Momentum": 0.70,
                   "RSI Reversal": 1.15, "VWAP Fade": 1.30, "Gap Fill Fade": 1.20},
    "MIXED":      {n: 1.00 for n in STRATEGY_NAMES},
    "RISK_OFF":   {n: 0.50 for n in STRATEGY_NAMES},
    "UNKNOWN":    {n: 1.00 for n in STRATEGY_NAMES},
}


def _ist_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten Yahoo's MultiIndex columns, put the index on IST, drop bad rows."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    if df.index.tz is None:
        df.index = df.index.tz_localize(IST_TZ)
    else:
        df.index = df.index.tz_convert(IST_TZ)
    return df.sort_index()


def fetch_market_context(force: bool = False, replay_at: str | None = None) -> dict:
    """Download the market-level series. NEVER raises - if the feed is down the
    engine still analyses the stock, it just skips the regime gate."""
    key = (ist_now().strftime("%Y-%m-%d %H"), replay_at)
    if not force and key in _MARKET_CACHE:
        return _MARKET_CACHE[key][1]
    ctx = {"available": False, "note": "", "replay_at": replay_at}
    try:
        n_d = _ist_ohlcv(_dl(CONFIG.index_symbol, period="1y", interval="1d"))
        n_i = _ist_ohlcv(_dl(CONFIG.index_symbol, period="1d", interval="5m"))
        b_d = _ist_ohlcv(_dl(CONFIG.bank_symbol, period="6mo", interval="1d"))
        v_d = _ist_ohlcv(_dl(CONFIG.vix_symbol, period="3mo", interval="1d"))
        if replay_at and not n_i.empty:
            hh, mm = (int(x) for x in replay_at.split(":"))
            cut = n_i.index.normalize() + pd.Timedelta(hours=hh, minutes=mm)
            n_i = n_i[n_i.index <= cut]
        ctx.update({"nifty_daily": n_d, "nifty_5m": n_i,
                    "bank_daily": b_d, "vix_daily": v_d})
        if n_d.empty:
            ctx["note"] = f"no data for {CONFIG.index_symbol} - regime gate skipped"
        else:
            ctx["available"] = True
    except Exception as e:                      # network/API outage is not fatal
        ctx["note"] = f"market fetch failed ({type(e).__name__}) - regime gate skipped"
    _MARKET_CACHE[key] = (ist_now(), ctx)
    return ctx


def _vwap_crossings(close: np.ndarray, vw: np.ndarray) -> int:
    """How often price flipped sides of VWAP - the textbook chop measurement."""
    side = np.sign(close - vw)
    side = side[~np.isnan(side)]
    return int((np.diff(side) != 0).sum()) if len(side) > 1 else 0


def market_regime(ctx: dict | None = None, ts: pd.Timestamp | None = None) -> dict:
    """Classify the tape and translate it into per-strategy weights.

    Labels: TREND_UP / TREND_DOWN / CHOP / MIXED / RISK_OFF / UNKNOWN.
    Returns bias, size_mult, allow_new_entries and strategy_mult, all consumed
    by build_trade_call(); pure maths on `ctx`, so it is fully offline-testable.
    """
    ts = ts or ist_now()
    out = {"label": "UNKNOWN", "bias": 0, "confidence": 0, "available": False,
           "size_mult": 1.0, "allow_new_entries": True, "strategy_mult":
           dict(_REGIME_WEIGHTS["UNKNOWN"]), "notes": [], "asof": ts,
           "vix": None, "vix_chg_pct": None, "vix_percentile": None,
           "nifty": None, "nifty_slope20": None, "nifty_gap_pct": None,
           "nifty_intraday_slope": 0.0,
           "vwap_crossings": None, "above_vwap": None, "index_atr_pct": None}
    ctx = ctx if ctx is not None else fetch_market_context(replay_at=None)
    if not ctx or not ctx.get("available"):
        out["notes"].append("MARKET DATA UNAVAILABLE: " +
                            (ctx or {}).get("note", "no context") +
                            " - judging this stock on its own bars only.")
        return out

    nd = ctx["nifty_daily"]
    c = nd["Close"].astype(float)
    e50 = float(ema(c, 50).iloc[-1])
    e200 = float(ema(c, 200).iloc[-1]) if len(c) >= 200 else e50
    slope20 = _slope_pct(c.tail(20))
    out["nifty"] = round(float(c.iloc[-1]), 2)
    out["nifty_slope20"] = round(slope20, 4)
    out["index_atr_pct"] = round(100 * float(atr(nd["High"], nd["Low"], nd["Close"], 14).iloc[-1]) /
                                 float(c.iloc[-1]), 2)
    above_ma = float(c.iloc[-1]) > e50 > e200 * 0.999
    below_ma = float(c.iloc[-1]) < e50 < e200 * 1.001

    # --- live intraday state of the index -----------------------------------
    ni = ctx.get("nifty_5m")
    if ni is not None and not ni.empty:
        today = ni[ni.index.normalize() == ts.normalize()]
        if today.empty:
            today = ni.tail(75)                 # after-close / holiday: last session
        vw = vwap(today)
        cross = _vwap_crossings(today["Close"].values.astype(float), vw.values.astype(float))
        last_px = float(today["Close"].iloc[-1])
        out["vwap_crossings"] = cross
        out["above_vwap"] = bool(last_px > float(vw.iloc[-1]))
        intraday_slope = _slope_pct(today["Close"].tail(6))      # last ~30 min
        out["nifty_intraday_slope"] = round(intraday_slope, 4)
        prior = c[nd.index.normalize() < today.index[0].normalize()]
        prev_close = float(prior.iloc[-1]) if len(prior) else float(c.iloc[-1])
        out["nifty_gap_pct"] = round(100 * (float(today["Open"].iloc[0]) / prev_close - 1), 2)
    else:
        cross, intraday_slope, out["nifty_gap_pct"] = 99, 0.0, None

    # --- India VIX ----------------------------------------------------------
    vd = ctx.get("vix_daily")
    if vd is not None and not vd.empty:
        vc = vd["Close"].astype(float)
        out["vix"] = round(float(vc.iloc[-1]), 2)
        if len(vc) > 1 and float(vc.iloc[-2]) > 0:
            out["vix_chg_pct"] = round(100 * (float(vc.iloc[-1]) / float(vc.iloc[-2]) - 1), 1)
        if len(vc) >= 5:
            out["vix_percentile"] = round(100 * float((vc.tail(20) <= float(vc.iloc[-1])).mean()), 0)

    # --- breadth confirmation ----------------------------------------------
    bd = ctx.get("bank_daily")
    bank_slope = _slope_pct(bd["Close"].astype(float).tail(20)) if bd is not None and len(bd) > 25 else 0.0

    vix_high = out["vix"] is not None and out["vix"] >= CONFIG.vix_risk_off
    vix_spike = out["vix_chg_pct"] is not None and out["vix_chg_pct"] >= CONFIG.vix_spike_pct
    vix_nervous = out["vix"] is not None and out["vix"] >= CONFIG.vix_elevated
    chop = cross >= CONFIG.chop_vwap_crossings or abs(slope20) < CONFIG.trend_slope_min * 0.5
    up_t = slope20 >= CONFIG.trend_slope_min and above_ma and out["above_vwap"] and intraday_slope > 0
    dn_t = slope20 <= -CONFIG.trend_slope_min and below_ma and out["above_vwap"] is False and intraday_slope < 0

    if vix_high or vix_spike:
        label = "RISK_OFF"
    elif up_t:
        label = "TREND_UP"
    elif dn_t:
        label = "TREND_DOWN"
    elif chop:
        label = "CHOP"
    else:
        label = "MIXED"

    out["label"] = label
    out["available"] = True
    out["bias"] = 1 if label == "TREND_UP" else -1 if label == "TREND_DOWN" else 0
    out["strategy_mult"] = dict(_REGIME_WEIGHTS[label])

    conf = 40
    conf += min(25, abs(slope20) / CONFIG.trend_slope_min * 12)
    conf += 15 if (out["above_vwap"] and slope20 > 0) or (out["above_vwap"] is False and slope20 < 0) else -10
    conf += 10 if np.sign(bank_slope) == np.sign(slope20) and slope20 else -5
    conf -= min(20, max(0, cross - CONFIG.chop_vwap_crossings) * 4)
    out["confidence"] = int(max(5, min(95, conf)))

    if label == "RISK_OFF":
        out["allow_new_entries"] = False
        out["size_mult"] = 0.0
        out["notes"].append(
            f"RISK-OFF tape (VIX {out['vix']}, {out['vix_chg_pct']}% on the day): "
            f"fresh intraday positions are blocked - option hedging / cash only.")
    else:
        if vix_nervous:
            out["size_mult"] = min(out["size_mult"], 0.6)
            out["notes"].append(f"VIX {out['vix']} is elevated: half size, wider stops "
                                f"(assume 1.5x normal slippage).")
        if label == "CHOP":
            out["size_mult"] = min(out["size_mult"], 0.7)
            out["notes"].append(f"CHOPPY market ({out['vwap_crossings']} VWAP crossings): "
                                f"breakout strategies are muted, mean-reversion favoured.")
        if label in ("TREND_UP", "TREND_DOWN"):
            out["notes"].append(f"Market is {label.replace('_', ' ')} (NIFTY slope "
                                f"{out['nifty_slope20']}%/day, {'above' if out['above_vwap'] else 'below'} "
                                f"VWAP): trade with that direction, fade nothing.")
    if out["nifty_gap_pct"] is not None and abs(out["nifty_gap_pct"]) >= CONFIG.gap_caution_pct \
            and ts.time() < time(9, 45):
        out["strategy_mult"]["ORB-15 Breakout"] *= 0.5
        out["notes"].append(f"NIFTY gapped {out['nifty_gap_pct']:+.2f}% - the opening range "
                            f"is distorted, wait for the first retest after 09:45.")
    return out


def regime_summary(r: dict) -> str:
    """One-line market banner used at the top of every report."""
    if not r or not r.get("available"):
        return "REGIME: UNKNOWN (no market data) - gate skipped"
    arrow = {1: "bullish", -1: "bearish", 0: "neutral"}[r["bias"]]
    bits = [f"REGIME: {r['label']} ({arrow}, confidence {r['confidence']}%)"]
    if r["nifty"]:
        bits.append(f"NIFTY {r['nifty']:,} slope {r['nifty_slope20']}%/day")
    if r["vix"]:
        bits.append(f"India VIX {r['vix']} ({r['vix_chg_pct']:+.1f}%)" if r["vix_chg_pct"] is not None
                    else f"India VIX {r['vix']}")
    if r["vwap_crossings"] is not None:
        bits.append(f"{r['vwap_crossings']} VWAP crossings")
    bits.append(f"size x{r['size_mult']:.1f}" if r["size_mult"] != 1.0 else "full size allowed")
    if not r["allow_new_entries"]:
        bits.append("NEW ENTRIES BLOCKED")
    return "  |  ".join(bits)


# ---------------------------------------------------------------------------
# LEVEL 4 - Strategies. Each returns Signal or None.
# ---------------------------------------------------------------------------
@dataclass
class Signal:
    name: str
    side: str            # BUY / SELL
    strength: float      # 0..1
    why: str
    entry: float
    stop: float
    target: float
    aligned: str = ""    # with / against / neutral vs the detected trend
    weight: float = 1.0  # final voting weight (trend x regime x journal expectancy)
    muted: str = ""      # why the weight was cut, when it was


def _risk_props(sess: Session) -> dict:
    a = atr(sess.m5["High"], sess.m5["Low"], sess.m5["Close"]).iloc[-1]
    if pd.isna(a):
        a = sess.snapshot["price"] * 0.004
    return {"atr": float(a)}


def _levels(price: float, stop: float, side: str, min_rr: float = 2.0,
            far_target: float | None = None):
    """Build a target that respects a minimum reward:risk ratio.

    Returns (target, ok). `far_target` lets a strategy use its own structural
    level (e.g. VWAP) when that is even better than min_rr.
    """
    risk = abs(price - stop)
    if risk <= 0:
        return price, False
    d = price - stop
    sign = 1 if d > 0 else -1              # BUY when target above stop
    tgt = price + sign * min_rr * risk
    if far_target is not None and (far_target - price) * sign > (tgt - price) * sign:
        tgt = far_target
    ok = abs(tgt - price) >= CONFIG.risk_reward_min * risk
    return round(float(tgt), 2), bool(ok)


def s1_orb(sess: Session) -> Signal | None:
    """Opening-range breakout - only valid while the breakout is still fresh."""
    orb_end = 9 * 60 + 15 + CONFIG.orb_minutes
    mins = np.asarray(_minutes(sess.m1.index))
    c = sess.m1[mins <= orb_end]
    if len(c) < CONFIG.orb_minutes or len(sess.m1) <= CONFIG.orb_minutes + 3:
        return None
    o_h, o_l = float(c["High"].max()), float(c["Low"].min())
    price, vol = sess.snapshot["price"], sess.m1["Volume"]
    elapsed = int(mins[-1]) - (9 * 60 + 15)
    if elapsed > CONFIG.orb_valid_minutes:      # breakout is stale by now
        return None
    avg_vol = float(vol.iloc[:-5].tail(60).mean() or 0)
    prev = float(sess.m1["Close"].iloc[-CONFIG.cross_valid_bars - 1])
    brk_up = price > o_h and prev <= o_h        # crossed the level recently
    brk_dn = price < o_l and prev >= o_l
    if not (brk_up or brk_dn):
        return None
    vol_ok = avg_vol > 0 and float(vol.iloc[-3:].mean()) > 1.2 * avg_vol
    side = "BUY" if brk_up else "SELL"
    a = _risk_props(sess)["atr"]
    stop = price - 1.5 * a if brk_up else price + 1.5 * a
    lvl = o_h if brk_up else o_l
    tgt, ok = _levels(price, stop, side)
    if not ok:
        return None
    return Signal("ORB-15 Breakout", side, min(1.0, 0.6 + (0.25 if vol_ok else 0) + (0.15 if (brk_up and price > vwap(sess.m1).iloc[-1]) else 0)),
                  f"Price {price:.2f} crossed {'above ORB high' if brk_up else 'below ORB low'} "
                  f"{lvl:.2f} (range {o_h:.2f}/{o_l:.2f}, first {CONFIG.orb_minutes} min) "
                  f"{CONFIG.cross_valid_bars} bars ago"
                  + ("" if vol_ok else " - WEAK volume confirmation"),
                  price, stop, tgt)


def s2_vwap_pullback(sess: Session) -> Signal | None:
    tr = detect_trend(sess)
    vw, c = vwap(sess.m1), sess.m1["Close"]
    price = sess.snapshot["price"]
    if len(c) < 25: return None
    near = abs(price - vw.iloc[-1]) / price < 0.003
    bounced_up = price > c.iloc[-3] > c.iloc[-4] and tr["votes"] >= 2
    bounced_dn = price < c.iloc[-3] < c.iloc[-4] and tr["votes"] <= -2
    if near and bounced_up:
        a = _risk_props(sess)["atr"]
        stop = price - 1.3 * a
        tgt, ok = _levels(price, stop, "BUY")
        if not ok: return None
        return Signal("VWAP Pullback", "BUY", 0.8,
                      f"Uptrend ({tr['label']}): price pulled back to VWAP {vw.iloc[-1]:.2f} and bounced",
                      price, stop, tgt)
    if near and bounced_dn:
        a = _risk_props(sess)["atr"]
        stop = price + 1.3 * a
        tgt, ok = _levels(price, stop, "SELL")
        if not ok: return None
        return Signal("VWAP Pullback", "SELL", 0.8,
                      f"Downtrend ({tr['label']}): price rejected at VWAP {vw.iloc[-1]:.2f}",
                      price, stop, tgt)
    return None


def s3_ema_cross(sess: Session) -> Signal | None:
    c = sess.m5["Close"]
    if len(c) < 55: return None
    e9, e20 = ema(c, 9), ema(c, 20)
    above_now = e9.iloc[-1] > e20.iloc[-1]
    crossed = (e9.shift() <= e20.shift()).iloc[-3:].any() if above_now else (e9.shift() >= e20.shift()).iloc[-3:].any()
    if not crossed: return None
    price = sess.snapshot["price"]
    a = _risk_props(sess)["atr"]
    side = "BUY" if above_now else "SELL"
    stop = price - 1.5 * a if above_now else price + 1.5 * a
    tgt, ok = _levels(price, stop, side)
    if not ok: return None
    return Signal("EMA 9/20 Crossover", side, 0.7,
                  f"EMA9 {'crossed above' if above_now else 'crossed below'} EMA20 on 5-min within last 3 bars",
                  price, stop, tgt)


def s4_rsi_reversal(sess: Session) -> Signal | None:
    r = rsi(sess.m5["Close"]).iloc[-1]
    price = sess.snapshot["price"]
    a = _risk_props(sess)["atr"]
    if r < 28:
        stop = price - 1.2 * a
        tgt, ok = _levels(price, stop, "BUY")
        if not ok: return None
        return Signal("RSI Reversal", "BUY", min(1.0, 0.55 + (28 - r) / 60),
                      f"5-min RSI oversold at {r:.1f} - bounce expected", price, stop, tgt)
    if r > 72:
        stop = price + 1.2 * a
        tgt, ok = _levels(price, stop, "SELL")
        if not ok: return None
        return Signal("RSI Reversal", "SELL", min(1.0, 0.55 + (r - 72) / 60),
                      f"5-min RSI overbought at {r:.1f} - pullback expected", price, stop, tgt)
    return None


def s5_supertrend(sess: Session) -> Signal | None:
    if len(sess.m5) < 20: return None
    st = supertrend(sess.m5)
    d, st_val = int(st["dir"].iloc[-1]), st["line"].iloc[-1]
    if pd.isna(st_val): return None
    price = sess.snapshot["price"]
    a = _risk_props(sess)["atr"]
    if d == 1:
        stop = max(float(st_val), price - 1.5 * a)
        tgt, ok = _levels(price, stop, "BUY", far_target=price + 2.0 * a)
        if not ok: return None
        return Signal("Supertrend Follow", "BUY", 0.65,
                      f"5-min Supertrend(10,3) bullish, trail SL at {st_val:.2f}",
                      price, stop, tgt)
    stop = min(float(st_val), price + 1.5 * a)
    tgt, ok = _levels(price, stop, "SELL", far_target=price - 2.0 * a)
    if not ok: return None
    return Signal("Supertrend Follow", "SELL", 0.65,
                  f"5-min Supertrend(10,3) bearish, trail SL at {st_val:.2f}",
                  price, stop, tgt)


def s6_vwap_fade(sess: Session) -> Signal | None:
    """Mean reversion: price stretched far from VWAP in a SIDEWAYS market."""
    tr = detect_trend(sess)
    if tr["label"] not in ("SIDEWAYS",): return None
    vw = vwap(sess.m1).iloc[-1]
    price = sess.snapshot["price"]
    dev = (price - vw) / vw
    a = _risk_props(sess)["atr"]
    # exit IS the VWAP for a fade - if that doesn't pay enough, skip the trade
    if dev < -0.008:
        stop = price - 1.0 * a
        if abs(vw - price) < CONFIG.risk_reward_min * abs(price - stop):
            return None
        return Signal("VWAP Fade", "BUY", 0.5,
                      f"sideways market but price {dev*100:.2f}% below VWAP {vw:.2f} - fade back to VWAP",
                      price, stop, round(float(vw), 2))
    if dev > 0.008:
        stop = price + 1.0 * a
        if abs(price - vw) < CONFIG.risk_reward_min * abs(stop - price):
            return None
        return Signal("VWAP Fade", "SELL", 0.5,
                      f"sideways market but price +{dev*100:.2f}% above VWAP {vw:.2f} - fade back to VWAP",
                      price, stop, round(float(vw), 2))
    return None


def s7_relative_strength(sess: Session, regime: dict) -> Signal | None:
    """LEVEL 4.7 - Relative strength vs NIFTY: buy leaders, skip laggards.

    Only fires when the market context exists. Compares the last ~30 min of
    5-min slope for the stock against the index, so it measures today's
    leadership rather than yesterday's correlation.
    """
    if not regime or not regime.get("available") or len(sess.m5) < 12:
        return None
    stock_slope = _slope_pct(sess.m5["Close"].tail(6))
    idx_slope = float(regime.get("nifty_intraday_slope") or 0.0)
    rs = stock_slope - idx_slope
    price = sess.snapshot["price"]
    a = _risk_props(sess)["atr"]
    tr = detect_trend(sess)
    if rs > 0.02 and tr["votes"] >= 2 and regime["bias"] >= 0:
        stop = price - 1.5 * a
        tgt, ok = _levels(price, stop, "BUY")
        if not ok:
            return None
        return Signal("Relative Strength Momentum", "BUY", min(1.0, 0.6 + min(0.3, rs * 4)),
                      f"Stock 5-min slope {stock_slope:+.3f}%/bar vs NIFTY {idx_slope:+.3f}% "
                      f"(RS {rs:+.3f}%) - a clear leader on a {regime['label']} tape",
                      price, stop, tgt)
    if rs < -0.02 and tr["votes"] <= -2 and regime["bias"] <= 0:
        stop = price + 1.5 * a
        tgt, ok = _levels(price, stop, "SELL")
        if not ok:
            return None
        return Signal("Relative Strength Momentum", "SELL", min(1.0, 0.6 + min(0.3, -rs * 4)),
                      f"Stock 5-min slope {stock_slope:+.3f}%/bar vs NIFTY {idx_slope:+.3f}% "
                      f"(RS {rs:+.3f}%) - a clear laggard on a {regime['label']} tape",
                      price, stop, tgt)
    return None


def s8_gap_fill(sess: Session) -> Signal | None:
    """LEVEL 4.8 - Gap fade: an unfinished gap is a magnet.

    Needs the previous day's close (from the daily series). Fires only when the
    stock gapped >=0.8% and is still on the far side of that gap.
    """
    d = sess.daily
    if d is None or d.empty:
        return None
    day = sess.snapshot["time"].normalize()
    # daily bars from Yahoo are tz-naive while the intraday snapshot is IST:
    # put the daily index on the same IST clock before comparing, or pandas
    # raises "Cannot compare tz-naive and tz-aware".
    di = d.index.tz_convert(IST_TZ) if d.index.tz else d.index.tz_localize(IST_TZ)
    prior = d[di.normalize() < day]
    if prior.empty:
        return None
    prev_close = float(prior["Close"].iloc[-1])
    open_px = sess.snapshot["open"]
    price = sess.snapshot["price"]
    gap = 100 * (open_px - prev_close) / prev_close
    if abs(gap) < 0.8:
        return None
    unfilled = (gap > 0 and price > prev_close) or (gap < 0 and price < prev_close)
    if not unfilled:
        return None
    a = _risk_props(sess)["atr"]
    side = "SELL" if gap > 0 else "BUY"
    stop = price + 1.2 * a if gap > 0 else price - 1.2 * a
    tgt, ok = _levels(price, stop, side, min_rr=2.0, far_target=prev_close)
    if not ok:
        return None
    return Signal("Gap Fill Fade", side, min(1.0, 0.55 + min(0.35, abs(gap) / 3)),
                  f"{abs(gap):.2f}% {'gap-up' if gap > 0 else 'gap-down'} at the open is still "
                  f"unfilled (prev close {prev_close:.2f}, now {price:.2f}) - gap acts as a magnet",
                  price, stop, round(float(tgt), 2))


STRATEGIES = [s1_orb, s2_vwap_pullback, s3_ema_cross, s4_rsi_reversal, s5_supertrend,
              s6_vwap_fade, s8_gap_fill]
CTX_STRATEGIES = [s7_relative_strength]        # need (sess, regime) - index data


# ---------------------------------------------------------------------------
# LEVEL 5 - Ensemble -> trade call + position sizing
# ---------------------------------------------------------------------------
def build_trade_call(sess: Session, regime: dict | None = None,
                     expectancy: dict | None = None) -> dict:
    """LEVEL 5 - the ensemble.

    regime     : market_regime() output. None = gate skipped (offline tests,
                 or Yahoo index data unavailable).
    expectancy : {strategy name: average R per settled trade} from the journal;
                 strategies the journal proved unprofitable are down-weighted.
    """
    trend = detect_trend(sess)
    gate = quality_gate(sess)
    regime = regime or {}
    signals = [s for s in (fn(sess) for fn in STRATEGIES) if s]
    if regime.get("available"):
        signals += [s for s in (fn(sess, regime) for fn in CTX_STRATEGIES) if s]

    # Trend alignment: a signal that fights the detected trend is discounted,
    # an aligned one is boosted - keeps "trade with the trend" as the priority.
    tdir = 1 if trend["votes"] >= 2 else -1 if trend["votes"] <= -2 else 0
    for s in signals:
        sign = 1 if s.side == "BUY" else -1
        base = 1.0 if tdir == 0 else (1.3 if sign == tdir else 0.55)
        s.aligned = "with" if base > 1 else "against" if base < 1 else "neutral"
        s.weight = base * (regime.get("strategy_mult") or {}).get(s.name, 1.0)
        if expectancy and CONFIG.mute_negative_expectancy:
            e = expectancy.get(s.name)
            if e is not None and e < 0:
                s.weight *= 0.4
                s.muted = f"journal expectancy {e:+.2f}R over its trades"
    buy_w = sum(s.strength * s.weight for s in signals if s.side == "BUY")
    sell_w = sum(s.strength * s.weight for s in signals if s.side == "SELL")
    side = "BUY" if buy_w > sell_w else "SELL" if sell_w > buy_w else "NONE"

    # Any counter-trend entry is vetoed while a trend is detected at all -
    # "trade with the trend" outranks the individual strategy signals.
    veto = ""
    if side != "NONE" and tdir != 0 and (1 if side == "BUY" else -1) != tdir:
        veto = (f"Only counter-trend setups fired inside a {trend['label']} market "
                f"({trend['confidence']}% confidence) - the {side} idea was vetoed.")
        side = "NONE"
    # Market regime gate
    if side != "NONE" and regime.get("available"):
        if not regime.get("allow_new_entries", True):
            veto = (f"{side} idea blocked by the market regime gate ({regime['label']}, "
                    f"VIX {regime['vix']}) - no new intraday positions in this tape.")
            side = "NONE"
        elif regime["bias"] != 0 and tdir == 0 and \
                (1 if side == "BUY" else -1) != regime["bias"]:
            veto = (f"{side} idea vetoed: the stock has no trend of its own and the "
                    f"market is {regime['label']} - counter-trend trades against "
                    f"NIFTY have the worst odds.")
            side = "NONE"
    conf_score = max(buy_w, sell_w) / (len(signals) or 1)

    size_mult = float(regime.get("size_mult", 1.0)) if regime.get("available") else 1.0
    plan = None
    if side != "NONE" and signals:
        chosen = max([s for s in signals if s.side == side],
                     key=lambda s: s.strength * s.weight)
        price = sess.snapshot["price"]
        qty = position_size(price, chosen.stop, side, mult=size_mult)
        plan = {"signal": chosen, "qty": qty, "size_mult": size_mult,
                "risk_rs": abs(price - chosen.stop) * qty,
                "reward_rs": abs(chosen.target - price) * qty,
                "rr": abs(chosen.target - price) / max(abs(price - chosen.stop), 0.01)}
    return {"ticker": sess.ticker, "snapshot": sess.snapshot, "trend": trend,
            "gate": gate, "signals": signals, "side": side,
            "signal_strength": round(conf_score, 2), "plan": plan, "veto": veto,
            "regime": regime, "expectancy": expectancy or {},
            # live clock normally; replayed sessions are judged at their own bar time
            "market": market_status(sess.snapshot["time"] if sess.is_replay else None)}


def position_size(price: float, stop: float, side: str, mult: float = 1.0) -> int:
    """LEVEL 5.2 - risk CONFIG.risk_pct of capital, capped by intraday leverage.

    `mult` is the regime size factor (0.6 on a nervous tape, 0.7 in chop).
    """
    risk_per_share = max(abs(price - stop), 0.05)
    qty_risk = int((CONFIG.capital * CONFIG.risk_pct * max(0.0, min(mult, 1.0))) // risk_per_share)
    qty_notional = int((CONFIG.capital * CONFIG.max_leverage) // price) if price else 0
    return max(min(qty_risk, qty_notional), 0)


def expected_remaining_move(sess: Session) -> float:
    """LEVEL 5.3 - ATR-scaled price room left in the session (sqrt-of-time rule).

    Uses live minutes-left during trading; after close it falls back to the
    session's own remaining time so post-close review stays meaningful.
    """
    mins_left = market_status()["minutes_left"]
    if mins_left == 0 or sess.is_replay:
        last = sess.snapshot["time"]
        close_dt = last.normalize() + pd.Timedelta(hours=MARKET_CLOSE.hour,
                                                   minutes=MARKET_CLOSE.minute)
        mins_left = max(mins_left, max(0, int((close_dt - last).total_seconds() // 60)))
    a5 = _risk_props(sess)["atr"]
    return a5 * math.sqrt(max(mins_left, 1) / 5.0)


# ---------------------------------------------------------------------------
# LEVEL 10 - Trade journal. Every live plan is written to CSV, settled against
# the real bars after the close, and the measured results are fed back into the
# next decision (a strategy the journal proves unprofitable gets down-weighted).
# ---------------------------------------------------------------------------
JOURNAL_COLS = ["date", "time", "ticker", "side", "strategy", "entry", "stop",
                "target", "qty", "rr", "signal_strength", "trend", "regime",
                "quality", "status", "exit_price", "result_r", "settled_on",
                "settle_data", "notes"]


def read_journal(path: str | None = None) -> pd.DataFrame:
    """The journal as a frame - empty frame if nothing logged yet. Never crashes."""
    p = path or CONFIG.journal_file
    if not os.path.exists(p):
        return pd.DataFrame(columns=JOURNAL_COLS)
    try:
        j = pd.read_csv(p)
    except Exception:
        return pd.DataFrame(columns=JOURNAL_COLS)
    for c in JOURNAL_COLS:            # tolerate files from older versions
        if c not in j.columns:
            j[c] = ""
    return j[JOURNAL_COLS]


def log_call(call: dict, notes: str = "", path: str | None = None) -> dict:
    """Append this plan to the journal. NO TRADE writes nothing."""
    p = call.get("plan")
    if not p:
        return {}
    s, sn = p["signal"], call["snapshot"]
    row = {
        "date": f"{sn['time']:%Y-%m-%d}", "time": f"{sn['time']:%H:%M}",
        "ticker": call["ticker"], "side": call["side"], "strategy": s.name,
        "entry": round(s.entry, 2), "stop": round(s.stop, 2),
        "target": round(s.target, 2), "qty": p["qty"], "rr": round(p["rr"], 2),
        "signal_strength": call["signal_strength"], "trend": call["trend"]["label"],
        "regime": (call.get("regime") or {}).get("label", "UNKNOWN"),
        "quality": call["gate"]["score"], "status": "OPEN", "exit_price": "",
        "result_r": "", "settled_on": "", "settle_data": "", "notes": notes,
    }
    if not CONFIG.journal_auto:
        return row
    f = path or CONFIG.journal_file
    try:
        pd.DataFrame([row], columns=JOURNAL_COLS).to_csv(
            f, mode="a", header=not os.path.exists(f), index=False)
    except Exception as e:
        row["notes"] = f"journal write failed: {e}"
    return row


def _settle_one(row) -> tuple:
    """Replay the logged plan against the real bars -> (status, exit, R, data)."""
    entry, stop, target = float(row["entry"]), float(row["stop"]), float(row["target"])
    risk = abs(entry - stop)
    if risk <= 0:
        return "INVALID", None, None, ""
    sign = 1.0 if str(row["side"]).upper() == "BUY" else -1.0
    rr = abs(target - entry) / risk
    day = str(row["date"])[:10]
    bars = _ist_ohlcv(_dl(str(row["ticker"]), period="7d", interval="5m"))
    used, fine = "5-min bars", True
    if bars.empty:
        bars = _ist_ohlcv(_dl(str(row["ticker"]), period="1mo", interval="1d"))
        used, fine = "daily bar (coarse)", False
    if bars.empty:
        return "NO_DATA", None, None, ""
    # bars carry an IST-tz index, so the logged date must be localised to match
    day_ts = pd.Timestamp(day)
    day_ts = day_ts.tz_localize(IST_TZ) if day_ts.tz is None else day_ts.tz_convert(IST_TZ)
    same = bars[bars.index.normalize() == day_ts.normalize()]
    if same.empty:
        return "NO_DATA", None, None, used
    if fine:                                   # only trade bars after entry time
        cut = pd.Timestamp(f"{day} {str(row['time'])[:5]}", tz=IST_TZ)
        later = same[same.index >= cut]
        same = later if not later.empty else same
    for _, b in same.iterrows():
        hit_stop = b["Low"] <= stop if sign > 0 else b["High"] >= stop
        hit_tgt = b["High"] >= target if sign > 0 else b["Low"] <= target
        if hit_stop:                            # both in one bar -> take the loss
            return "STOPPED", round(float(stop), 2), -1.0, used
        if hit_tgt:
            return "TARGET", round(float(target), 2), round(float(rr), 3), used
    last_close = float(same["Close"].iloc[-1])
    r = round(sign * (last_close - entry) / risk, 3)
    return "SQUARE-OFF", round(last_close, 2), r, used


def settle_journal(path: str | None = None, verbose: bool = True) -> pd.DataFrame:
    """Score every OPEN plan whose session is already over."""
    f = path or CONFIG.journal_file
    j = read_journal(f)
    if j.empty:
        if verbose:
            print("JOURNAL: empty - no trades logged yet.")
        return j
    today = f"{ist_now():%Y-%m-%d}"
    changed = 0
    for i, row in j.iterrows():
        if str(row["status"]).upper() != "OPEN":
            continue
        if str(row["date"]) == today and market_status()["phase"] != "CLOSED":
            if verbose:
                print(f"  [open] {row['ticker']} {row['side']} still live - settles after 15:30")
            continue
        status, exit_px, r, used = _settle_one(row)
        j.at[i, "status"], j.at[i, "exit_price"] = status, exit_px if exit_px is not None else ""
        j.at[i, "result_r"] = r if r is not None else ""
        j.at[i, "settled_on"], j.at[i, "settle_data"] = f"{ist_now():%Y-%m-%d %H:%M}", used
        changed += 1
        if verbose:
            rs = f"{r:+.2f}R" if r is not None else "n/a"
            print(f"  [{status:10}] {row['ticker']:16} {row['strategy']:24} "
                  f"entry {row['entry']} -> exit {exit_px} = {rs}  ({used})")
    if changed:
        try:
            j.to_csv(f, index=False)
        except Exception as e:
            print(f"  journal not saved: {e}")
    return j


def strategy_scoreboard(j: pd.DataFrame | None = None) -> dict:
    """LEVEL 10.3 - what the journal actually says about each strategy."""
    j = read_journal() if j is None else j
    done = j[j["result_r"].astype(str).str.match(r"^-?\d", na=False)] if not j.empty else j
    out = {}
    for name in STRATEGY_NAMES:
        sub = done[done["strategy"] == name] if not done.empty else done
        n = len(sub)
        if n == 0:
            out[name] = {"trades": 0, "win_rate": None, "avg_r": None,
                         "expectancy": None, "profit_factor": None}
            continue
        r = sub["result_r"].astype(float)
        wins, losses = r[r > 0], r[r <= 0]
        pf = (wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() != 0 else float("inf")
        out[name] = {"trades": int(n), "win_rate": round(100 * len(wins) / n, 1),
                     "avg_r": round(float(r.mean()), 3),
                     "expectancy": round(float(r.mean()), 3),      # R per trade
                     "profit_factor": None if pf == float("inf") else round(float(pf), 2)}
    settled = [v for v in out.values() if v["trades"]]
    total = sum(v["trades"] for v in out.values())
    out["_overall"] = {"trades": total, "settled": total,
                       "avg_r": round(float(pd.concat(
                           [done["result_r"].astype(float)]).mean()), 3) if total else None,
                       "strategies_tested": len(settled)} if total else {"trades": 0}
    return out


def expectancy_map(j: pd.DataFrame | None = None) -> dict:
    """{strategy: average R} - only for strategies with enough settled trades."""
    board = strategy_scoreboard(j)
    return {k: v["avg_r"] for k, v in board.items()
            if k != "_overall" and v["trades"] >= CONFIG.min_trades_to_judge}


def day_exposure_r(day: str | None = None, j: pd.DataFrame | None = None) -> float:
    """Realised R for one trading day (negative = losing so far)."""
    j = read_journal() if j is None else j
    if j.empty:
        return 0.0
    day = day or f"{ist_now():%Y-%m-%d}"
    done = j[(j["date"].astype(str) == day) &
             (j["result_r"].astype(str).str.match(r"^-?\d", na=False))]
    return round(float(done["result_r"].astype(float).sum()), 2) if len(done) else 0.0


def trades_today(day: str | None = None, j: pd.DataFrame | None = None) -> int:
    j = read_journal() if j is None else j
    if j.empty:
        return 0
    day = day or f"{ist_now():%Y-%m-%d}"
    return int((j["date"].astype(str) == day).sum())


def journal_gate(day: str | None = None, j: pd.DataFrame | None = None) -> str:
    """Daily loss cap / trade-count circuit breaker - text, empty when clear."""
    if j is None:
        if not os.path.exists(CONFIG.journal_file):
            return ""
        j = read_journal()
    d = day_exposure_r(day, j)
    if d <= -CONFIG.daily_loss_cap_r:
        return (f"daily loss cap hit: {d:+.2f}R today (cap -{CONFIG.daily_loss_cap_r}R) - "
                f"stop opening new positions, review the journal instead")
    n = trades_today(day, j)
    if n >= CONFIG.max_trades_per_day:
        return (f"{n} trades already logged today (limit {CONFIG.max_trades_per_day}) - "
                f"over-trading is the most expensive habit in intraday")
    return ""


def journal_report(verbose: bool = True) -> str:
    """Human-readable scoreboard + today's exposure."""
    j = settle_journal(verbose=False)
    board = strategy_scoreboard(j)
    L = ["=" * 74, "  TRADE JOURNAL  (" + CONFIG.journal_file + ")",
         "=" * 74,
         f"  {'STRATEGY':26}{'TRADES':>7}{'WIN%':>8}{'AVG R':>8}{'PF':>7}",
         "-" * 74]
    for k, v in board.items():
        if k == "_overall":
            continue
        L.append(f"  {k:26}{v['trades']:>7}"
                 + (f"{v['win_rate']:>7.1f}%{v['avg_r']:>8.2f}" +
                    (f"{v['profit_factor']:>7.2f}" if v["profit_factor"] is not None else "    n/a")
                    if v["trades"] else f"{'-':>7}{'-':>8}{'-':>7}"))
    o = board["_overall"]
    L.append("-" * 74)
    L.append(f"  settled trades: {o.get('trades', 0)}" +
             (f"   overall expectancy {o['avg_r']:+.2f}R per trade"
              if o.get("trades") and o.get("avg_r") is not None else ""))
    L.append(f"  today ({ist_now():%Y-%m-%d}): {trades_today()} trades logged, "
             f"realised {day_exposure_r():+.2f}R (cap -{CONFIG.daily_loss_cap_r}R)")
    g = journal_gate()
    if g:
        L.append(f"  [CIRCUIT BREAKER] {g.upper()}")
    L.append("=" * 74)
    txt = "\n".join(L)
    if verbose:
        print(txt)
    return txt


def export_call(call: dict, warns: list[str] | None = None,
                alts: list[dict] | None = None, path: str | None = None) -> str:
    """LEVEL 12.4 - machine-readable copy of one analysis (JSON), so results can
    be archived / pushed to a Telegram mail bot / diffed between runs."""
    sn, p = call["snapshot"], call.get("plan")
    d = {
        "generated_ist": f"{ist_now():%Y-%m-%d %H:%M:%S}",
        "ticker": call["ticker"], "as_of": f"{sn['time']:%Y-%m-%d %H:%M}",
        "ltp": sn["price"], "day_change_pct": sn["day_change_pct"],
        "verdict": call["side"], "signal_strength": call["signal_strength"],
        "veto": call.get("veto", ""), "market_phase": call["market"]["phase"],
        "trend": call["trend"]["label"], "trend_confidence": call["trend"]["confidence"],
        "quality_score": call["gate"]["score"], "quality_pass": call["gate"]["passed"],
        "regime": {k: (f"{v:%H:%M}" if isinstance(v, pd.Timestamp) else v)
                   for k, v in (call.get("regime") or {}).items()
                   if k in ("label", "bias", "confidence", "vix", "nifty", "nifty_gap_pct",
                            "vwap_crossings", "size_mult", "allow_new_entries", "available")},
        "plan": None if not p else {
            "strategy": p["signal"].name, "side": call["side"], "entry": p["signal"].entry,
            "stop": p["signal"].stop, "target": p["signal"].target, "qty": p["qty"],
            "rr": round(p["rr"], 2), "risk_rs": round(p["risk_rs"], 2),
            "reward_rs": round(p["reward_rs"], 2), "size_mult": p.get("size_mult")},
        "signals": [{"name": s.name, "side": s.side, "strength": s.strength,
                     "weight": round(s.weight, 2), "aligned": s.aligned,
                     "why": s.why, "muted": s.muted} for s in call["signals"]],
        "warnings": warns or [], "alternatives": alts or [],
        "suggested": call.get("suggested"),
    }
    f = path or f"{call['ticker'].split('.')[0]}_{sn['time']:%H%M}_call.json"
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, default=str)
    return f


# ---------------------------------------------------------------------------
# LEVEL 6 - Safety / warning system
# ---------------------------------------------------------------------------
def safety_warnings(sess: Session, call: dict, user_target: float | None = None) -> list[str]:
    w, price = [], sess.snapshot["price"]
    ms, trend, gate, plan = call["market"], call["trend"], call["gate"], call["plan"]

    if ms["phase"] == "PRE_OPEN": w.append("[TIME] Market not open yet - suggestions are based on the last session.")
    if ms["phase"] == "CLOSED":   w.append("[TIME] Market CLOSED - this is a post-close review, NOT an actionable signal.")
    if ms["phase"] == "LATE_SESSION": w.append(f"[TIME] {ms['label']} - after {NO_ENTRY_AFTER.strftime('%H:%M')} IST avoid fresh entries; intraday exits mandatory by 15:15.")
    if plan and 0 < ms["minutes_left"] < 45: w.append(f"[TIME] Only {ms['minutes_left']} min left - trade may not reach target before square-off.")
    if gate["removals"]: w.append("[BLOCK] FUNDAMENTAL/LIQUIDITY: " + " | ".join(gate["removals"]) + "  -> NOT a good stock choice today, pick another.")
    if not gate["passed"] and not gate["removals"]: w.append(f"[WARN] Fundamental quality score {gate['score']}/10 below threshold {CONFIG.min_quality_score}/10.")
    if trend["label"] == "SIDEWAYS" and plan: w.append(f"[WARN] Trend is SIDEWAYS (confidence {trend['confidence']}%) - breakout trades often fail; halve your quantity.")
    if plan and plan["rr"] < CONFIG.risk_reward_min: w.append(f"[WARN] Risk:Reward {plan['rr']:.2f} below minimum {CONFIG.risk_reward_min} - plan rejected as unsafe.")
    if plan and abs(plan["signal"].target - price) > 2.2 * expected_remaining_move(sess):
        w.append(f"[TARGET] Level {plan['signal'].target:.2f} needs >2x the ATR room left ({expected_remaining_move(sess):.2f} Rs) - UNREACHABLE, book at intermediate levels.")

    if user_target is not None:
        room = expected_remaining_move(sess)
        need = abs(user_target - price)
        up = user_target > price
        side_ok = (up and call["side"] == "BUY") or (not up and call["side"] == "SELL")
        if need > 1.1 * room:
            pct = 100 * need / price
            far = 1 if up else -1
            w.append(f"[SAFETY] YOUR TARGET {user_target:.2f} ({pct:.2f}% away, Rs {need:.2f}) is NOT SAFE: it exceeds the "
                     f"statistically expected remaining move for the session (ATR room {room:.2f} Rs). Realistic target zone: "
                     f"{price + far*min(need, 0.8*room):.2f} to {price + far*1.1*room:.2f}. Book profits there.")
        if not side_ok and call["side"] in ("BUY", "SELL"):
            w.append(f"[WARN] Target {user_target:.2f} opposes the detected {call['side']} setup - do not hold a losing direction hoping for target.")
        if call["side"] == "NONE":
            w.append(f"[WARN] You asked about target {user_target:.2f}, but NO strategy fired - there is no trade to take here. Consider another stock.")

    if call.get("veto"): w.append("[VETO] " + call["veto"] + " Better to sit this one out or switch stocks.")
    rg = call.get("regime") or {}
    if rg.get("available"):
        if not rg.get("allow_new_entries", True):
            w.append("[REGIME] " + rg["label"] + ": new intraday positions are blocked today - "
                     + " ".join(rg["notes"][:1]))
        elif rg.get("size_mult", 1.0) < 1.0:
            w.append(f"[REGIME] {rg['label']} ({rg['confidence']}% confidence) - cut size to "
                     f"{int(rg['size_mult'] * 100)}% of normal. " + " ".join(rg["notes"][:1]))
        else:
            w.append(f"[REGIME] {rg['label']} ({rg['confidence']}% confidence) - full size allowed. "
                     + (" ".join(rg["notes"][:1]) if rg["notes"] else ""))
    muted = [s for s in call["signals"] if s.muted]
    if muted:
        w.append("[JOURNAL] down-weighted by your own results: "
                 + ", ".join(f"{s.name} ({s.muted})" for s in muted))
    if call.get("circuit_breaker"):
        w.append("[CIRCUIT BREAKER] " + call["circuit_breaker"].upper() + " - flat and done for today.")
    if plan and call["side"] == "BUY" and trend["votes"] <= -2: w.append("[WARN] BUY signal against a DOWNWARD trend - counter-trend, low odds.")
    if plan and call["side"] == "SELL" and trend["votes"] >= 2: w.append("[WARN] SELL signal against an UPWARD trend - counter-trend, low odds.")
    fee_pct = CONFIG.round_trip_cost_pct
    if plan and plan["rr"] > 0:
        turnover = (price + abs(plan["signal"].target)) * plan["qty"]
        cost_rs = turnover * fee_pct / 100
        net_rr = (plan["reward_rs"] - cost_rs) / max(plan["risk_rs"], 1)
        if net_rr < 1.0: w.append(f"[COST] After ~{fee_pct:.2f}% round-trip costs (Rs {cost_rs:,.0f}), "
                                  f"net R:R drops to {net_rr:.2f} - marginal edge, skip if unsure.")
    atrp = _atr_pct(sess)
    if atrp and atrp > CONFIG.max_atr_pct: w.append(f"[VOL] 5-min ATR {atrp:.1f}% of price - extremely volatile, slippage will hurt.")
    if sess.data_note: w.append("[DATA] " + sess.data_note)
    return w


def suggest_alternatives(sess: Session, max_candidates: int = 6,
                         regime: dict | None = None,
                         expectancy: dict | None = None) -> list[dict]:
    """LEVEL 6.2 - scan the watchlist and rank better stocks (light 1-day scan).

    A replayed session scans at the same clock, so post-close review still works.
    """
    replay = f"{sess.snapshot['time']:%H:%M}" if sess.is_replay else None
    if regime is None and CONFIG.regime_enabled:
        regime = market_regime(fetch_market_context(replay_at=replay))
    if expectancy is None:
        expectancy = expectancy_map()
    ranked = []
    scanned = 0
    for t in CONFIG.watchlist:
        if resolve_ticker(t) == sess.ticker or scanned >= max_candidates:
            continue
        scanned += 1
        try:
            s2 = cached_session(t, replay_at=replay)
            c2 = build_trade_call(s2, regime, expectancy)
        except Exception:
            continue
        score = c2["signal_strength"] * (c2["gate"]["score"] / 10)
        if (c2["side"] != "NONE" and c2["gate"]["passed"]
                and c2["plan"] and c2["plan"]["rr"] >= CONFIG.risk_reward_min
                and c2["market"]["phase"] not in ("CLOSED", "PRE_OPEN", "LATE_SESSION")):
            ranked.append({"ticker": t, "side": c2["side"],
                           "strength": c2["signal_strength"], "quality": c2["gate"]["score"],
                           "trend": c2["trend"]["label"], "score": round(score, 2),
                           "price": c2["snapshot"]["price"],
                           "strategy": c2["plan"]["signal"].name,
                           "entry": round(c2["plan"]["signal"].entry, 2),
                           "stop": round(c2["plan"]["signal"].stop, 2),
                           "target": round(c2["plan"]["signal"].target, 2),
                           "qty": c2["plan"]["qty"],
                           "rr": round(c2["plan"]["rr"], 2)})
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:3]


# ---------------------------------------------------------------------------
# LEVEL 7.1 - Chart
# ---------------------------------------------------------------------------
def plot_session(sess: Session, call: dict, save: str | None = None):
    import matplotlib
    notebook = in_notebook()
    if not notebook:
        matplotlib.use("Agg")     # terminal/headless: write a PNG instead
    # pyplot must be imported AFTER the backend choice, else it warns
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    m1, price = sess.m1, sess.snapshot["price"]
    fig, (ax, axv) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1]})
    m1 = m1.copy()
    # matplotlib formats tz-aware indexes in UTC - plot on the IST wall clock
    m1.index = m1.index.tz_convert(IST_TZ).tz_localize(None)
    x = m1.index
    ax.plot(x, m1["Close"], lw=1.0, color="#1565c0", label="Close")
    ax.plot(x, vwap(m1), lw=1.4, color="#e65100", label="VWAP")
    ax.plot(x, ema(m1["Close"], 9), lw=0.8, color="#2e7d32", alpha=0.8, label="EMA9")
    ax.plot(x, ema(m1["Close"], 20), lw=0.8, color="#7b1fa2", alpha=0.8, label="EMA20")
    ax.axhline(sess.snapshot["open"], color="grey", ls="--", lw=0.7)
    c = m1[np.asarray(_minutes(m1.index)) <= 9 * 60 + 15 + CONFIG.orb_minutes]
    if len(c):
        ax.axhline(c["High"].max(), color="red", ls=":", lw=0.7)
        ax.axhline(c["Low"].min(), color="green", ls=":", lw=0.7)
    plan = call.get("plan")
    if plan:
        s = plan["signal"]
        t_ent = x[-1]
        ax.scatter([t_ent], [s.entry], marker="^" if s.side == "BUY" else "v",
                   s=140, color="green" if s.side == "BUY" else "red", zorder=5,
                   label=f"{s.side} {s.entry:.2f} ({s.name})")
        ax.axhline(s.stop, color="red", ls="--", lw=1, label=f"SL {s.stop:.2f}")
        ax.axhline(s.target, color="darkgreen", ls="--", lw=1, label=f"Target {s.target:.2f}")
    ax.set_title(f"{sess.ticker} - {sess.snapshot['time']:%d %b %H:%M} IST | "
                 f"LTP Rs {price:.2f} ({sess.snapshot['day_change_pct']:+.2f}%) | "
                 f"Trend: {call['trend']['label']} ({call['trend']['confidence']}%) | "
                 f"Market: {(call.get('regime') or {}).get('label', 'UNKNOWN')}")
    ax.legend(loc="upper left", fontsize=8); ax.grid(alpha=0.3)
    axv.bar(x, m1["Volume"], width=0.0007, color="#90a4ae")
    axv.set_ylabel("Vol"); axv.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate(); fig.tight_layout()
    if in_notebook():
        if save:                   # keep a downloadable copy too
            fig.savefig(save, dpi=110)
            print(f"Chart also saved -> {save}")
        plt.show()                 # renders inline in Colab/Jupyter
        plt.close(fig)
    elif save:
        fig.savefig(save, dpi=110); plt.close(fig)
        print(f"Chart saved -> {save}")
    else:
        plt.show(); plt.close(fig)


# ---------------------------------------------------------------------------
# LEVEL 7.2 - Report
# ---------------------------------------------------------------------------
def _row_line(r: dict) -> str:
    """One ranked setup as a single text line (scan table / suggestion box)."""
    return (f"    {str(r['ticker']):16} {str(r['side']):4} "
            f"{str(r.get('strategy', ''))[:22]:22} entry {r['entry']:,.2f} "
            f"SL {r['stop']:,.2f} T {r['target']:,.2f} (R:R {r['rr']}) qty {r['qty']} "
            f"str {r['strength']} quality {r['quality']}/10 trend {r['trend']}")


def _fmt_call(call: dict, warns: list[str], alts: list[dict]) -> str:
    sn, tr, g = call["snapshot"], call["trend"], call["gate"]
    rg = call.get("regime") or {}
    L = ["=" * 74,
         f"  TRADE CALL  |  {call['ticker']}  |  {sn['time']:%H:%M} IST  |  {call['market']['label']}",
         "  " + regime_summary(rg),
         "=" * 74,
         f"  LTP Rs {sn['price']:,.2f}   Open {sn['open']:,.2f}  H {sn['high']:,.2f}  L {sn['low']:,.2f}"
         f"   Chg {sn['day_change_pct']:+.2f}%   Vol {sn['volume']:,}   Session mins {sn['elapsed_min']}",
         f"  TREND: {tr['label']}  confidence {tr['confidence']}%  (slope 30m {tr['slopes']['30m']}%/bar)"]
    for r in tr["reasons"][:5]: L.append(f"    {r}")
    for n in (rg.get("notes") or [])[:3]: L.append(f"    [market] {n}")
    L.append(f"  FUNDAMENTAL GATE: score {g['score']}/10  -> {'PASS' if g['passed'] else 'FAIL'}")
    for f in g["flags"]: L.append(f"    [flag] {f}")
    for r in g["removals"]: L.append(f"    [REMOVE] {r}")
    if call["signals"]:
        L.append(f"  STRATEGY SIGNALS ({len(call['signals'])}):")
        for s in call["signals"]:
            L.append(f"    [{s.side:4}] {s.name:22} str {s.strength:.2f} w {s.weight:.2f} "
                     f"({s.aligned} trend)  entry {s.entry:.2f} "
                     f"SL {s.stop:.2f} T {s.target:.2f}"
                     + (f"  [muted: {s.muted}]" if s.muted else "") + f"\n          why: {s.why}")
    if call["side"] == "NONE":
        L.append("  VERDICT: NO TRADE - " + (call.get("veto") or "no strategy fired with enough conviction."))
    else:
        p = call["plan"]; s = p["signal"]
        L.append(f"  VERDICT: {call['side']}  (best strategy: {s.name}, R:R {p['rr']:.2f})")
        L.append(f"    SUGGESTED TIME: act within next 5 min ({(sn['time'] + timedelta(minutes=5)):%H:%M} IST), "
                 f"after that the setup ages and minute-bar clarity drops.")
        t1 = s.entry + 1.5 * (s.entry - s.stop) if s.side == "BUY" else s.entry - 1.5 * (s.stop - s.entry)
        L.append(f"    Entry ~Rs {s.entry:.2f} | Stop-loss Rs {s.stop:.2f} | Target1 Rs "
                 f"{t1:.2f} | Target2 Rs {s.target:.2f}")
        L.append(f"    Quantity: {p['qty']} shares (risk Rs {p['risk_rs']:,.0f} = "
                 f"{100*p['risk_rs']/CONFIG.capital:.2f}% of Rs {CONFIG.capital:,.0f}) "
                 f"| Expected reward Rs {p['reward_rs']:,.0f}"
                 + (f"  [regime size x{p['size_mult']:.1f}]" if p.get("size_mult", 1) != 1 else ""))
    if warns:
        L.append("-" * 74); L.append("  WARNINGS / SAFETY:")
        for w in warns: L.append(f"    {w}")
    if alts:
        L.append("-" * 74); L.append("  BETTER ALTERNATIVES (watchlist scan):")
        for a in alts:
            L.append(f"    {a['ticker']:16} {a['side']:4} str {a['strength']} quality {a['quality']}/10 "
                     f"trend {a['trend']} | entry {a['entry']:,.2f} SL {a['stop']:,.2f} "
                     f"T {a['target']:,.2f} (R:R {a['rr']}) LTP {a['price']:,.2f}")
    sug = call.get("suggested")
    if sug:
        L.append("-" * 74)
        L.append("  TRADE THIS INSTEAD (full universe scan, best setup right now):")
        L.append(_row_line(sug))
        L.append(f"    why: {sug.get('why', '')}")
    L.append("=" * 74)
    return "\n".join(L)


def trade_recommendation(ticker: str, user_target: float | None = None,
                         chart: bool = True, verbose: bool = True,
                         session: Session | None = None,
                         replay_at: str | None = None,
                         regime: dict | None = None,
                         expectancy: dict | None = None,
                         deep_scan: bool = True, log: bool = True) -> dict:
    """
    MAIN ENGINE ENTRY POINT (one stock, full depth).
      ticker       : 'RELIANCE', 'TATAMOTORS', 'INFY.NS', ...
      user_target  : your own sell/buy target (e.g. 500 in the 490 example)
      replay_at    : 'HH:MM' IST - re-run the analysis as if the clock were then
      regime       : market_regime() output (fetched when omitted)
      deep_scan    : when this stock is unusable, also scan the whole universe
                     and suggest the single best replacement
      Returns dict with snapshot, trend, gate, signals, plan, warnings,
      alternatives, suggested, regime, market.
    """
    sess = session or fetch_session(ticker, replay_at=replay_at)
    cut = replay_at or (f"{sess.snapshot['time']:%H:%M}" if sess.is_replay else None)
    if regime is None:
        regime = (market_regime(fetch_market_context(replay_at=cut),
                              ts=sess.snapshot["time"] if sess.is_replay else None)
                  if CONFIG.regime_enabled else {})
    if expectancy is None:
        expectancy = expectancy_map()
    call = build_trade_call(sess, regime, expectancy)
    call["circuit_breaker"] = "" if not log else journal_gate()
    warns = safety_warnings(sess, call, user_target)
    alts: list[dict] = []
    blocked = bool(call["gate"]["removals"]) or (call["plan"] and call["plan"]["rr"] < CONFIG.risk_reward_min) \
        or call["side"] == "NONE"
    if call["circuit_breaker"]:
        # daily loss cap / trade limit: never tempt the user into "one more"
        blocked, deep_scan = True, False
    if blocked:
        alts = suggest_alternatives(sess, regime=regime, expectancy=expectancy)
        if alts:
            warns.append("[SWITCH] Original stock not suitable - the alternatives above "
                         "score better right now.")
        elif deep_scan:
            best = best_trade_now(regime=regime, expectancy=expectancy, verbose=False)
            if best:
                call["suggested"] = best
                warns.append("[SWITCH] Nothing on the short watchlist either - the best setup "
                             "in the whole scanned universe is shown above.")
    if log and not sess.is_replay:
        # a replay is a review, not a trade you took - never pollute the journal
        row = log_call(call, notes=(f"user_target={user_target}" if user_target else ""))
        if row:
            call["journal_logged"] = row
    if chart:
        try:
            plot_session(sess, call, save=f"{sess.ticker.replace('.','_')}_intraday.png")
        except Exception as e:
            warns.append(f"Chart skipped: {e}")
    if verbose:
        print(_fmt_call(call, warns, alts))
    call["warnings"], call["alternatives"], call["session"] = warns, alts, sess
    return call


# ---------------------------------------------------------------------------
# LEVEL 11 - Universe scan: "if not this one, then which one?"
# ---------------------------------------------------------------------------
_SESSION_CACHE: dict = {}         # {(ticker, replay): (fetched_at, Session)}
SESSION_TTL_S = 180               # 1-min bars land every minute; 3 min is plenty


def cached_session(ticker: str, replay_at: str | None = None,
                   force: bool = False) -> Session:
    """Download each symbol at most once every SESSION_TTL_S - makes a 20-stock
    scan affordable on the free Yahoo quota (and repeated re-runs instant)."""
    key = (resolve_ticker(ticker), replay_at)
    hit = _SESSION_CACHE.get(key)
    if hit and not force and (ist_now() - hit[0]).total_seconds() < SESSION_TTL_S:
        return hit[1]
    s = fetch_session(ticker, require_today=False, replay_at=replay_at)
    _SESSION_CACHE[key] = (ist_now(), s)
    return s


def scan_universe(symbols: tuple | None = None, regime: dict | None = None,
                  expectancy: dict | None = None, replay_at: str | None = None,
                  verbose: bool = True, max_report: int = 10) -> list[dict]:
    """LEVEL 11.1 - run the whole engine over every symbol and rank the setups.

    Returns every scanned row (with a `usable` flag); the printable table shows
    only the tradeable ones, best first.
    """
    symbols = tuple(symbols or CONFIG.universe)
    if regime is None:
        regime = (market_regime(fetch_market_context(replay_at=replay_at))
                  if CONFIG.regime_enabled else {})
    if expectancy is None:
        expectancy = expectancy_map()
    rows, nodata = [], []
    for t in symbols:
        try:
            sess = cached_session(t, replay_at=replay_at)
        except DataError:
            nodata.append(t)
            continue
        except Exception as e:
            nodata.append(f"{t} ({type(e).__name__})")
            continue
        c = build_trade_call(sess, regime, expectancy)
        p, sn = c["plan"], c["snapshot"]
        best_sig = (max([s for s in c["signals"] if s.side == c["side"]],
                        key=lambda s: s.strength * s.weight) if p else None)
        row = {"ticker": t, "side": c["side"], "strength": c["signal_strength"],
               "quality": c["gate"]["score"], "trend": c["trend"]["label"],
               "price": sn["price"], "chg_pct": sn["day_change_pct"],
               "regime": regime.get("label", "UNKNOWN"), "phase": c["market"]["phase"],
               "strategy": best_sig.name if best_sig else "",
               "why": best_sig.why if best_sig else (c.get("veto") or "no signal"),
               "entry": round(best_sig.entry, 2) if best_sig else None,
               "stop": round(best_sig.stop, 2) if best_sig else None,
               "target": round(best_sig.target, 2) if best_sig else None,
               "qty": p["qty"] if p else 0,
               "rr": round(p["rr"], 2) if p else 0.0,
               "risk_rs": round(p["risk_rs"], 0) if p else 0.0,
               "reward_rs": round(p["reward_rs"], 0) if p else 0.0,
               "n_signals": len(c["signals"]), "veto": c.get("veto", ""),
               "flags": c["gate"]["flags"], "removals": c["gate"]["removals"]}
        row["score"] = round(row["strength"] * (row["quality"] / 10) *
                             min(row["rr"], 4) / 2, 2)
        row["usable"] = bool(c["side"] != "NONE" and p and c["gate"]["passed"]
                             and row["rr"] >= CONFIG.risk_reward_min
                             and c["market"]["phase"] == "OPEN"
                             and regime.get("allow_new_entries", True))
        rows.append(row)
    rows.sort(key=lambda r: (r["usable"], r["score"]), reverse=True)
    if verbose:
        print("=" * 74)
        print(f"  UNIVERSE SCAN  |  {len(rows)} stocks analysed, {len(nodata)} without a feed  "
              f"|  {ist_now():%H:%M} IST")
        print("  " + regime_summary(regime))
        print("=" * 74)
        openers = [r for r in rows if r["usable"]]
        if not openers:
            print("  NO TRADEABLE SETUP in this universe right now"
                  + (f" - market is {regime.get('label')}" if regime.get("available") else ""))
        for r in openers[:max_report]:
            print(_row_line(r))
            print(f"          why: {r['why'][:96]}")
        also = [r for r in rows if not r["usable"]][:max_report]
        if also:
            print("-" * 74)
            print("  NOT TRADEABLE NOW:")
            for r in also:
                why = r["veto"] or ("no signal" if r["side"] == "NONE" else
                                    "gate/R:R/session filter")
                print(f"    {r['ticker']:16} {r['side']:4} str {r['strength']:5} "
                      f"quality {r['quality']}/10 trend {r['trend']:10} - {why[:70]}")
        if nodata:
            print(f"  [no feed] {', '.join(str(x) for x in nodata)} - Yahoo has no bars; "
                  f"use load_session_from_csv() for those.")
        print("=" * 74)
    return rows


def best_trade_now(symbols: tuple | None = None, regime: dict | None = None,
                   expectancy: dict | None = None, replay_at: str | None = None,
                   verbose: bool = True) -> dict | None:
    """LEVEL 11.2 - answer the question 'what should I trade RIGHT NOW?'."""
    rows = scan_universe(symbols, regime, expectancy, replay_at, verbose=False)
    openers = [r for r in rows if r["usable"]]
    if verbose:
        print("=" * 74)
        if not openers:
            rg = regime or {}
            print("  BEST TRADE NOW: NONE - no symbol passes every gate at the moment.")
            if rg.get("available"):
                print(f"  Market says {rg['label']} (VIX {rg['vix']}) - "
                      f"{'no new positions' if not rg.get('allow_new_entries', True) else 'smaller size, fewer trades'}.")
            print("  Sitting out is a position. Re-run after the next 15 minutes.")
        else:
            b = openers[0]
            print(f"  BEST TRADE NOW: {b['ticker']}  {b['side']}  "
                  f"({b['strategy']}, R:R {b['rr']}, strength {b['strength']})")
            print(_row_line(b).rstrip())
            if len(openers) > 1:
                print("  RUNNER-UPS:")
                for r in openers[1:4]:
                    print(_row_line(r))
        print("=" * 74)
    return openers[0] if openers else None


# ---------------------------------------------------------------------------
# LEVEL 12 - the one-command user interface: type a stock name, get an answer
# ---------------------------------------------------------------------------
def stock_details(ticker: str, verbose: bool = True,
                  session: Session | None = None) -> dict:
    """LEVEL 12.1 - everything the tool can honestly say about one stock.

    Works even when there is no price feed (NALCO): it then reports exactly
    what was tried, and still returns the fundamentals it could find.
    """
    asked = str(ticker).strip().upper()
    resolved = resolve_ticker(asked)
    alias_note = (f"'{asked}' was redirected to {resolved} (CONFIG.aliases - "
                  f"Yahoo renamed it)" if resolved != asked + ("" if "." in asked else ".NS")
                  else "")
    out: dict = {"asked": asked, "ticker": resolved, "alias": alias_note,
                 "available": False, "reason": "", "details": {}, "how_to_fix": ""}
    L = ["-" * 74, f"  STOCK DETAILS  |  {resolved}" + (f"  ({alias_note})" if alias_note else "")]
    try:
        sess = session or fetch_session(resolved, require_today=False)
    except DataError as e:
        out["reason"] = str(e)
        L.append("  PRICE/BAR DATA: NOT AVAILABLE on the free Yahoo feed")
        for ln in str(e).splitlines():
            L.append("    " + ln)
        if resolved.split(".")[0] in CONFIG.no_feed_expected or asked in CONFIG.no_feed_expected:
            L.append("  THIS IS EXPECTED: Yahoo carries no intraday bars for this symbol "
                     "(verified Oct 2026,\n  also checked .BO, daily intervals, Screener.in "
                     "(404) and NSE India (403).\n  The tool will NOT invent prices for it.")
            out["how_to_fix"] = ("Upload a 1-minute CSV exported from your broker "
                                 "(Kite/StockGraph/Neural) and run:\n"
                                 "    load_session_from_csv('NALCO_1min.csv', 'NALCO')\n"
                                 "  or simply: trade_call('NALCO', csv='NALCO_1min.csv')")
            L.append("  HOW TO STILL ANALYSE IT: " + out["how_to_fix"])
        out["report"] = "\n".join(L + ["-" * 74])
        if verbose:
            print(out["report"])
        return out

    sn, f = sess.snapshot, sess.fundamentals
    tr, g = detect_trend(sess), quality_gate(sess)
    atrp = _atr_pct(sess)
    wk = ""
    if f.get("wk52_high") and f.get("wk52_low"):
        rng = f["wk52_high"] - f["wk52_low"]
        pos = 100 * (sn["price"] - f["wk52_low"]) / rng if rng > 0 else 50.0
        wk = f"{f['wk52_low']:,.2f} - {f['wk52_high']:,.2f} (price at {pos:.0f}% of the range)"
    d = {"time": f"{sn['time']:%Y-%m-%d %H:%M} IST", "ltp": sn["price"],
         "open": sn["open"], "high": sn["high"], "low": sn["low"],
         "chg_pct": sn["day_change_pct"], "volume": sn["volume"],
         "bars": sn["elapsed_min"], "atr_pct": round(atrp, 2) if atrp else None,
         "trend": tr["label"], "trend_confidence": tr["confidence"],
         "quality_score": g["score"], "quality_pass": g["passed"],
         "market_cap": f.get("market_cap"), "pe": f.get("pe"), "pb": f.get("pb"),
         "roe": f.get("roe"), "de": f.get("de"), "beta": f.get("beta"),
         "avg_volume": f.get("avg_vol") or f.get("avg_vol_3m") or f.get("avg_vol_live"),
         "wk52": wk, "name": f.get("name"), "data_note": sess.data_note}
    out.update({"available": True, "details": d, "session": sess})
    rs = lambda v, fmt: (fmt % v) if isinstance(v, (int, float)) else "n/a"
    L.append(f"  {d['time']}   bars: {d['bars']} min" + (f"   [{sess.data_note}]" if sess.data_note else ""))
    L.append(f"  LTP Rs {sn['price']:,.2f}   ({sn['day_change_pct']:+.2f}% today)   "
             f"Open {sn['open']:,.2f}  High {sn['high']:,.2f}  Low {sn['low']:,.2f}")
    L.append(f"  Volume {sn['volume']:,}   5-min ATR {rs(d['atr_pct'], '%.2f')}% of price   "
             f"trend {tr['label']} ({tr['confidence']}%)")
    L.append(f"  Company: {d['name'] or 'name unavailable'}   MCap "
             + (f"Rs {f['market_cap']/1e7:,.0f} Cr" if f.get("market_cap") else "MCap n/a")
             + f"   P/E {rs(f.get('pe'), '%.1f')}   P/B {rs(f.get('pb'), '%.2f')}   "
               f"ROE {rs(None if f.get('roe') is None else f['roe']*100, '%.1f')}%   "
               f"D/E {rs(f.get('de'), '%.0f')}%   Beta {rs(f.get('beta'), '%.2f')}")
    L.append(f"  52-week: {wk or 'range unavailable'}   avg volume "
             + (f"{d['avg_volume']:,.0f}" if d["avg_volume"] else "unavailable"))
    L.append(f"  Quality gate {g['score']}/10 -> {'PASS' if g['passed'] else 'FAIL'}"
             + ("  flags: " + " | ".join(g["flags"]) if g["flags"] else "")
             + ("  REMOVED: " + " | ".join(g["removals"]) if g["removals"] else ""))
    out["report"] = "\n".join(L + ["-" * 74])
    if verbose:
        print(out["report"])
    return out


def trade_call(ticker: str, user_target: float | None = None, chart: bool = True,
               verbose: bool = True, replay_at: str | None = None,
               csv: str | None = None, suggest: bool = True) -> dict:
    """THE ONE-COMMAND ANSWER - this is the function you actually call:

        trade_call("NALCO")        # any stock name, no exchange suffix needed
        trade_call("RELIANCE", user_target=1400)
        trade_call("NALCO", csv="NALCO_1min.csv")     # your broker bars

    It prints, in order:  market regime  ->  stock details  ->  BUY/SELL/NO-TRADE
    verdict with entry/stop/target/qty  ->  safety warnings  ->  and when that
    stock is NOT good to trade right now, the best stock that IS (auto-scanned).
    """
    regime = market_regime(fetch_market_context(replay_at=replay_at)) \
        if CONFIG.regime_enabled else {}
    if verbose:
        print("\n" + "=" * 74)
        print(f"  {str(ticker).strip().upper()}  @  {ist_now():%d %b %Y %H:%M} IST  "
              f"[{market_status()['label']}]")
        print("  " + regime_summary(regime))
        for n in (regime.get("notes") or [])[:3]:
            print(f"    [market] {n}")
        print("=" * 74)

    sess = None
    if csv:
        sess = load_session_from_csv(csv, ticker, replay_at=replay_at)
    try:
        det = stock_details(ticker, verbose=verbose, session=sess)
    except DataError as e:
        det = {"asked": str(ticker).upper(), "ticker": resolve_ticker(ticker),
               "available": False, "reason": str(e),
               "report": "\n".join(["-" * 74]
                                   + ["    " + ln for ln in str(e).splitlines()]
                                   + ["-" * 74])}
        if verbose:
            print(det["report"])

    if not det.get("available"):
        out = {"ticker": det["ticker"], "side": "NO_DATA", "tradeable": False,
               "reason": det.get("reason", ""), "details": det,
               "regime": regime, "warnings": [], "alternatives": [],
               "suggested": None, "market": market_status(), "plan": None,
               "signals": [], "snapshot": {}, "trend": {}, "gate": {}}
        best = best_trade_now(regime=regime, verbose=verbose) if suggest else None
        out["suggested"] = best
        if verbose:
            print("\n" + "=" * 74)
            print(f"  ONE-LINE ANSWER: NO - {det['ticker']} cannot be analysed by this "
                  f"tool (no price feed, nothing was guessed).")
            if best:
                print(f"  TRADE THIS INSTEAD: {best['ticker']} {best['side']} via "
                      f"{best['strategy']}")
                print(f"    entry {best['entry']:.2f}  SL {best['stop']:.2f}  "
                      f"target {best['target']:.2f}  (R:R {best['rr']})  qty {best['qty']}")
            else:
                print("  Nothing else passes the gates either - stay flat and re-check later.")
            print("=" * 74)
        return out

    res = trade_recommendation(det["ticker"], user_target=user_target, chart=chart,
                              verbose=verbose, session=det["session"],
                              replay_at=replay_at, regime=regime,
                              deep_scan=suggest)
    res["details"] = det["details"]
    hard = [w for w in res["warnings"]
            if any(k in w for k in ("[BLOCK]", "[VETO]", "[SAFETY]", "[TIME]",
                                    "[CIRCUIT", "[REGIME]", "[TARGET]"))]
    ok = res["side"] in ("BUY", "SELL") and res["plan"] and \
        not any(w.startswith(("[BLOCK]", "[VETO]", "[SAFETY]", "[TIME]", "[CIRCUIT")) for w in res["warnings"])
    res["tradeable"] = ok
    if verbose:
        print("\n" + "=" * 74)
        if ok:
            p, s = res["plan"], res["plan"]["signal"]
            print(f"  ONE-LINE ANSWER: YES - trade {res['ticker']} {res['side']} now "
                  f"({s.name}).")
            print(f"  Entry {s.entry:.2f} | Stop {s.stop:.2f} | Target {s.target:.2f} "
                  f"| Qty {p['qty']} | Risk Rs {p['risk_rs']:,.0f} | R:R {p['rr']:.2f}")
            print(f"  Exit compulsorily by 15:15 IST. If {s.stop:.2f} is touched, no averaging.")
        else:
            why = res.get("veto") or (res["warnings"][0] if res["warnings"]
                                     else "no setup with enough conviction")
            print(f"  ONE-LINE ANSWER: NO - do not trade {res['ticker']} right now.")
            print(f"  reason: {why[:180]}")
            if res.get("circuit_breaker"):
                print(f"  journal says: {res['circuit_breaker']} - no more trades today.")
            elif res.get("suggested"):
                b = res["suggested"]
                print(f"  TRADE THIS INSTEAD: {b['ticker']} {b['side']} via {b['strategy']}")
                print(f"    entry {b['entry']:.2f}  SL {b['stop']:.2f}  target {b['target']:.2f} "
                      f"(R:R {b['rr']})  qty {b['qty']}")
            elif res.get("alternatives"):
                b = res["alternatives"][0]
                print(f"  TRADE THIS INSTEAD: {b['ticker']} {b['side']} via {b.get('strategy', '')}")
                print(f"    entry {b['entry']:.2f}  SL {b['stop']:.2f}  target {b['target']:.2f} "
                      f"(R:R {b['rr']})")
            else:
                print("  no better stock passed every gate either - sitting out is a position.")
        if hard and ok:
            print("  (still read the warnings above - " + str(len(hard)) + " of them)")
        print("=" * 74)
    return res


# ---------------------------------------------------------------------------
# LEVEL 8 - Self tests (pure synthetic, offline, deterministic)
# ---------------------------------------------------------------------------
_SYNTH_FUND = {"market_cap": 5e11, "pe": 18.0, "pb": 3.0, "de": 40.0, "roe": 0.18,
               "op_margin": 0.12, "net_margin": 0.09, "beta": 0.9, "avg_vol": 2_000_000,
               "avg_vol_3m": 1_900_000, "wk52_high": 560.0, "wk52_low": 400.0,
               "name": "SYNTH", "avg_vol_live": None}


def _synthetic_session(kind: str = "up", gap_pct: float = 0.0,
                       noise: float | None = None) -> Session:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2026-10-14 09:16", periods=180, freq="1min", tz=IST_TZ)
    drift = 0.12 if kind == "up" else -0.12
    base = 490.0 * (1 + gap_pct / 100.0)      # gap_pct = open vs yesterday's close
    sd = noise if noise is not None else (0.6 if kind != "flat" else 0.3)
    steps = rng.normal(0 if kind == "flat" else drift, sd, 180)
    close = base + np.cumsum(steps)
    o = np.concatenate([[base], close[:-1]])
    hi = np.maximum(o, close) + rng.uniform(0, 0.5, 180)
    lo = np.minimum(o, close) - rng.uniform(0, 0.5, 180)
    vol = rng.integers(5_000, 20_000, 180).astype(float)
    m1 = pd.DataFrame({"Open": o, "High": hi, "Low": lo, "Close": close, "Volume": vol}, index=idx)
    m5 = m1.resample("5min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
    snap = {"time": idx[-1], "price": float(close[-1]), "open": float(base),
            "high": float(hi.max()), "low": float(lo.min()), "volume": int(vol.sum()),
            "elapsed_min": 180, "day_change_pct": round(100 * (close[-1] - base) / base, 2)}
    fund = dict(_SYNTH_FUND)
    fund["wk52_high"] = float(close[-1]) * 1.05
    daily = pd.DataFrame()
    if gap_pct:
        daily = pd.DataFrame({"Open": [486.0, 487.0], "High": [492.0, 492.0],
                              "Low": [484.0, 485.0], "Close": [488.0, 490.0],
                              "Volume": [900_000.0, 1_000_000.0]},
                             index=pd.DatetimeIndex(["2026-10-10 15:30",
                                                     "2026-10-13 15:30"], tz=IST_TZ))
    return Session("SYNTH.NS", m1, m5, daily, snap, fund, "")


def _synthetic_market(trend: str = "up", vix: float = 11.0,
                      vix_prev: float | None = None, day: str = "2026-10-14",
                      n_bars: int = 75) -> dict:
    """LEVEL 9 test fixture: fake NIFTY / Bank Nifty / VIX frames, no internet.

    trend = 'up' | 'down' | 'chop' describes how the index is behaving; the
    regime label is then derived by the real market_regime() code path.
    """
    vix_prev = vix if vix_prev is None else vix_prev
    rng = np.random.default_rng(11)
    drift = {"up": 12.0, "down": -12.0, "chop": 0.0}[trend]
    steps = rng.normal(drift, 6.0, 260) if trend != "chop" else rng.normal(0, 25.0, 260)
    # end the daily series exactly where the intraday series starts, so the
    # measured gap is ~0 and only the behaviour under test drives the label
    c = 23000 + np.cumsum(steps)
    c = c - c[-1] + 24000.0
    d_idx = pd.date_range("2025-06-02 15:30", periods=260, freq="B", tz=IST_TZ)
    nifty_daily = pd.DataFrame({"Open": c - 8, "High": c + 40, "Low": c - 40,
                                "Close": c, "Volume": np.full(260, 1e6)}, index=d_idx)
    t_idx = pd.date_range(f"{day} 09:15", periods=n_bars, freq="5min", tz=IST_TZ)
    if trend == "chop":
        tv = 24000 + 55 * np.sin(np.arange(n_bars) / 3.5) + rng.normal(0, 2, n_bars)
    else:
        tv = 24000 + (1.8 if trend == "up" else -1.8) * np.arange(n_bars) \
            + rng.normal(0, 1.0, n_bars)
    nifty_5m = pd.DataFrame({"Open": np.concatenate([[tv[0]], tv[:-1]]),
                             "High": tv + 3, "Low": tv - 3, "Close": tv,
                             "Volume": np.full(n_bars, 2e5)}, index=t_idx)
    b_c = 51000 + np.cumsum(rng.normal(drift * 2, 12.0, 120))
    bank_daily = pd.DataFrame({"Open": b_c, "High": b_c + 80, "Low": b_c - 80,
                               "Close": b_c, "Volume": np.full(120, 5e5)},
                              index=pd.date_range("2026-04-01 15:30", periods=120,
                                                  freq="B", tz=IST_TZ))
    v = np.full(60, vix_prev, dtype=float)
    v[-1] = vix
    vix_daily = pd.DataFrame({"Open": v, "High": v + 0.2, "Low": v - 0.2, "Close": v,
                              "Volume": np.full(60, 1.0)},
                             index=pd.date_range(f"2026-07-01 15:30", periods=60,
                                                 freq="B", tz=IST_TZ))
    vix_daily.iloc[-1] = [vix, vix + 0.2, vix - 0.2, vix, 1.0]
    return {"available": True, "note": "", "replay_at": None,
            "nifty_daily": nifty_daily, "nifty_5m": nifty_5m,
            "bank_daily": bank_daily, "vix_daily": vix_daily}


_SYNTH_TS = pd.Timestamp("2026-10-14 12:15", tz=IST_TZ)


def _fake_journal(rows: list[dict]) -> pd.DataFrame:
    """Journal frame from hand-made settled trades (test fixture)."""
    j = pd.DataFrame(rows, columns=JOURNAL_COLS)
    for c in JOURNAL_COLS:
        if c not in j:
            j[c] = ""
    return j


def run_self_tests() -> bool:
    ok = True
    def check(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"   -> {detail}" if detail and not cond else ""))

    up = _synthetic_session("up"); dn = _synthetic_session("down"); fl = _synthetic_session("flat")
    check("uptime trend detected as UP-family", detect_trend(up)["label"] in ("UP", "STRONG_UP"))
    check("downtrend detected as DOWN-family", detect_trend(dn)["label"] in ("DOWN", "STRONG_DOWN"))
    check("flat market not STRONG", detect_trend(fl)["label"] != "STRONG_UP")
    st = market_status(pd.Timestamp("2026-10-14 12:15", tz=IST_TZ))
    check("12:15 IST -> OPEN phase", st["phase"] == "OPEN")
    check("15:00 IST -> LATE_SESSION", market_status(pd.Timestamp("2026-10-14 15:00", tz=IST_TZ))["phase"] == "LATE_SESSION")
    check("position sizing caps risk <=1% capital",
          (lambda q, p, s: abs(p - s) * q <= CONFIG.capital * CONFIG.risk_pct + abs(p - s))
          (position_size(490, 485, "BUY"), 490, 485))
    check("quality gate passes for blue-chip synthetic", quality_gate(up)["passed"])
    bad = _synthetic_session("up"); bad.fundamentals = {"market_cap": 1e8, "avg_vol": 100}
    check("illiquid stock gets REMOVED", not quality_gate(bad)["passed"] and quality_gate(bad)["removals"])
    call = build_trade_call(up)
    crazy = safety_warnings(up, call, user_target=up.snapshot["price"] * 1.5)
    check("unreachable user target triggers SAFETY warning", any("NOT SAFE" in w for w in crazy))
    sane = safety_warnings(up, call, user_target=up.snapshot["price"] * 1.004)
    check("realistic user target raises no SAFETY warning",
          not any("NOT SAFE" in w for w in sane))
    # the exact scenario from the brief: ~12:15, price 490, wanting to sell at 500
    sc = _synthetic_session("flat")
    sc_call = build_trade_call(sc)
    brief = safety_warnings(sc, sc_call, user_target=sc.snapshot["open"] + 10)
    check("490 -> 500 intraday target flagged NOT SAFE", any("NOT SAFE" in w for w in brief))
    check("490 -> 500 case also suggests a realistic zone", any("Realistic target zone" in w for w in brief))
    check("closed-market minutes_left is 0", market_status(pd.Timestamp("2026-10-14 18:30", tz=IST_TZ))["minutes_left"] == 0)
    check("stale ORB (>2h after open) is not tradable", s1_orb(up) is None)
    check("no crash when strategies silent", isinstance(build_trade_call(fl), dict))
    # trend alignment: an overbought RSI must not flip a strong uptrend into SELL
    up_call = build_trade_call(_synthetic_session("up"))
    check("strong uptrend never yields a SELL verdict", up_call["side"] in ("BUY", "NONE"))
    dn_call = build_trade_call(_synthetic_session("down"))
    check("strong downtrend never yields a BUY verdict", dn_call["side"] in ("SELL", "NONE"))
    # every emitted plan must respect the configured minimum reward:risk ratio
    for kind in ("up", "down", "flat"):
        cc = build_trade_call(_synthetic_session(kind))
        check(f"{kind}: all signals honour min R:R",
              all(abs(s.target - s.entry) >= CONFIG.risk_reward_min * abs(s.entry - s.stop) - 0.02
                  for s in cc["signals"]))

    # ---- LEVEL 9: market regime gate (synthetic index data, offline) --------
    strong_up = _synthetic_session("up", noise=0.05)
    r_up = market_regime(_synthetic_market("up"), ts=_SYNTH_TS)
    r_dn = market_regime(_synthetic_market("down"), ts=_SYNTH_TS)
    r_ch = market_regime(_synthetic_market("chop"), ts=_SYNTH_TS)
    r_ro = market_regime(_synthetic_market("up", vix=17.0), ts=_SYNTH_TS)
    check("regime: NIFTY rising, above VWAP -> TREND_UP", r_up["label"] == "TREND_UP", r_up["label"])
    check("regime: NIFTY falling, below VWAP -> TREND_DOWN", r_dn["label"] == "TREND_DOWN", r_dn["label"])
    check("regime: repeated VWAP crossings -> CHOP", r_ch["label"] == "CHOP",
          f"{r_ch['label']} crossings={r_ch['vwap_crossings']}")
    check("regime: CHOP really counts the crossings",
          (r_ch["vwap_crossings"] or 0) >= CONFIG.chop_vwap_crossings)
    check("regime: biases match the labels",
          (r_up["bias"], r_dn["bias"], r_ch["bias"]) == (1, -1, 0))
    check("regime: VIX at/above the risk-off level blocks new entries",
          r_ro["label"] == "RISK_OFF" and r_ro["allow_new_entries"] is False
          and r_ro["size_mult"] == 0.0)
    check("regime: a one-day VIX spike is risk-off too",
          market_regime(_synthetic_market("up", vix=12.0, vix_prev=10.0),
                        ts=_SYNTH_TS)["label"] == "RISK_OFF")
    check("regime: elevated (not risk-off) VIX halves size",
          market_regime(_synthetic_market("up", vix=14.0), ts=_SYNTH_TS)["size_mult"] <= 0.6)
    check("regime: NIFTY numbers are carried into the report",
          r_up["nifty"] and r_up["nifty_slope20"] is not None and "TREND_UP" in regime_summary(r_up))
    no_ctx = market_regime({"available": False, "note": "feed down"}, ts=_SYNTH_TS)
    check("regime: no market data -> UNKNOWN and the gate is skipped",
          no_ctx["label"] == "UNKNOWN" and no_ctx["available"] is False
          and no_ctx["allow_new_entries"] is True and no_ctx["size_mult"] == 1.0)
    check("regime: UNKNOWN is explained, not hidden",
          any("MARKET DATA UNAVAILABLE" in n for n in no_ctx["notes"]))
    # weights actually move the ensemble
    plain_w = {s.name: s.weight for s in build_trade_call(strong_up)["signals"]}
    chop_w = {s.name: s.weight for s in
              build_trade_call(strong_up, regime=r_ch)["signals"]}
    check("regime: a choppy tape cuts a trend-follower's weight",
          plain_w and all(chop_w.get(k, plain_w[k]) < plain_w[k] for k in plain_w))
    check("regime: CHOP prefers mean reversion over breakouts",
          r_ch["strategy_mult"]["VWAP Fade"] > r_ch["strategy_mult"]["EMA 9/20 Crossover"])
    check("regime: TREND_UP prefers trend followers",
          r_up["strategy_mult"]["Supertrend Follow"] > 1.0
          and r_up["strategy_mult"]["VWAP Fade"] < 1.0)
    flat_call = build_trade_call(_synthetic_session("flat"))
    check("regime: fixture stock has a signal before the gate", flat_call["side"] != "NONE",
          flat_call["side"])
    ro_call = build_trade_call(_synthetic_session("flat"), regime=r_ro)
    check("regime: RISK_OFF vetoes that same trade",
          ro_call["side"] == "NONE" and "regime gate" in ro_call["veto"], ro_call["veto"][:80])
    real_trend = globals()["detect_trend"]
    globals()["detect_trend"] = lambda s: {"label": "SIDEWAYS", "votes": 0, "confidence": 55,
                                           "slopes": {"30m": 0.0, "60m": 0.0, "session": 0.0},
                                           "reasons": ["stubbed for the veto test"]}
    against = build_trade_call(_synthetic_session("flat"), regime=r_dn)
    check("regime: a BUY against a bearish tape is vetoed when the stock has no trend",
          against["side"] == "NONE" and "vetoed" in against["veto"], against["veto"][:80])
    globals()["detect_trend"] = real_trend
    check("regime: size multiplier flows into the position size",
          position_size(500, 495, "BUY", mult=0.5) <= position_size(500, 495, "BUY") // 2 + 1
          and position_size(500, 495, "BUY", mult=0.0) == 0)
    sized = build_trade_call(strong_up, regime=market_regime(
        _synthetic_market("up", vix=14.0), ts=_SYNTH_TS))
    check("regime: nervous tape shrinks the emitted plan too",
          (sized["plan"] is None or sized["plan"]["size_mult"] <= 0.6) and
          build_trade_call(strong_up)["plan"] is not None)

    # ---- LEVEL 4.7 / 4.8: the two new strategies ---------------------------
    s7 = s7_relative_strength(strong_up, r_up)
    check("RS strategy: a leader vs NIFTY fires BUY on a bull tape",
          s7 is not None and s7.side == "BUY" and "vs NIFTY" in s7.why)
    check("RS strategy: needs the index data to exist",
          s7_relative_strength(strong_up, no_ctx) is None
          and s7_relative_strength(strong_up, None) is None)
    s7_dn = s7_relative_strength(_synthetic_session("down", noise=0.05), r_dn)
    check("RS strategy: a laggard fires SELL on a bear tape",
          s7_dn is not None and s7_dn.side == "SELL")
    g_up = _synthetic_session("up", gap_pct=1.5)
    s8 = s8_gap_fill(g_up)
    check("gap strategy: unfilled gap-up is a SELL back to yesterday",
          s8 is not None and s8.side == "SELL" and abs(s8.target - 490.0) < 0.01)
    check("gap strategy: gap-down is a BUY back to yesterday",
          s8_gap_fill(_synthetic_session("down", gap_pct=-1.5)).side == "BUY")
    check("gap strategy: a small gap is noise, not a signal",
          s8_gap_fill(_synthetic_session("up", gap_pct=0.2)) is None)
    check("gap strategy: a gap that already filled has nothing to give back",
          s8_gap_fill(_synthetic_session("down", gap_pct=1.5)) is None)
    check("strategies: the ensemble registers all 8 methods",
          len(STRATEGIES) + len(CTX_STRATEGIES) == 8 and len(STRATEGY_NAMES) == 8)

    # ---- LEVEL 10 / 11 / 12: journal, CSV import, scan, one-command UX ------
    # Everything below stays offline: the clock, the downloads and the index
    # feed are replaced by the synthetic fixtures above.
    G = globals()
    tmp = tempfile.mkdtemp(prefix="itc_selftest_")
    keep_fn = {k: G[k] for k in ("_dl", "_download_1m", "fetch_fundamentals",
                                 "fetch_market_context", "ist_now")}
    keep_cfg = (CONFIG.journal_file, CONFIG.universe, CONFIG.watchlist)
    LIVE = _synthetic_session("up", noise=0.05).m1
    G["_dl"] = lambda ticker, **kw: pd.DataFrame()
    G["_download_1m"] = lambda ticker, now: (LIVE.copy(), ticker)
    G["fetch_fundamentals"] = lambda ticker: dict(_SYNTH_FUND, wk52_high=float(LIVE["Close"].iloc[-1]) * 1.05)
    G["fetch_market_context"] = lambda force=False, replay_at=None: _synthetic_market("up")
    try:
        CONFIG.journal_file = os.path.join(tmp, "journal.csv")
        CONFIG.universe = ("AAA.NS", "BBB.NS", "CCC.NS")
        CONFIG.watchlist = ("AAA.NS", "BBB.NS")
        G["ist_now"] = lambda: pd.Timestamp("2026-10-14 12:15", tz=IST_TZ)
        # regression (found live): Yahoo delivers DAILY bars on a tz-NAIVE index
        # while the intraday snapshot is IST - gap-fill must not compare the two
        # directly (that raised "Cannot compare tz-naive and tz-aware").
        gf = _synthetic_session("up", gap_pct=2.0)
        gf.daily = gf.daily.tz_localize(None)
        try:
            gsig = s8_gap_fill(gf)
            _gf_ok = gsig is not None and gsig.name == "Gap Fill Fade"
        except Exception as e:                      # noqa: BLE001 - the bug raised here
            gsig, _gf_ok = repr(e), False
        check("gap-fill: survives a tz-NAIVE daily index (exactly how Yahoo delivers)",
              _gf_ok, str(gsig)[:120])
        plan_call = build_trade_call(strong_up, regime=r_up)
        row = log_call(plan_call)
        check("journal: a real plan is written to disk",
              bool(row) and os.path.exists(CONFIG.journal_file) and len(read_journal()) == 1)
        check("journal: the logged row carries every level",
              all(str(row.get(k, "")) != "" for k in
                  ("date", "time", "ticker", "side", "strategy", "entry", "stop",
                   "target", "qty", "status")), str(row)[:120])
        check("journal: NO-TRADE calls are never logged",
              log_call(build_trade_call(_synthetic_session("flat"), regime=r_ro)) == {})
        # settle the one logged plan against bars that break its stop first
        sig = plan_call["plan"]["signal"]

        def stop_out_bars(ticker, **kw):
            idx = pd.date_range("2026-10-14 09:15", periods=40, freq="5min", tz=IST_TZ)
            n = np.arange(len(idx))
            low = np.where(n < 2, sig.entry + 0.5, sig.stop - 1.0)
            high = np.where(n < 2, sig.entry + 1.0, sig.entry + 0.4)
            close = np.full(len(idx), sig.entry + 0.2)
            return pd.DataFrame({"Open": close, "High": high, "Low": low,
                                 "Close": close, "Volume": np.full(len(idx), 1e5)},
                                index=idx)
        G["_dl"] = stop_out_bars
        still_open = settle_journal(verbose=False)          # clock says 12:15, market OPEN
        check("journal: a live plan is not scored before the close",
              str(still_open.iloc[0]["status"]) == "OPEN", str(still_open.iloc[0]["status"]))
        G["ist_now"] = lambda: pd.Timestamp("2026-10-14 16:00", tz=IST_TZ)   # after square-off
        settled = settle_journal(verbose=False)
        G["ist_now"] = lambda: pd.Timestamp("2026-10-14 12:15", tz=IST_TZ)
        G["_dl"] = lambda ticker, **kw: pd.DataFrame()
        check("journal: after the close the plan is settled on the real bars",
              str(settled.iloc[0]["status"]) == "STOPPED", str(settled.iloc[0]["status"]))
        check("journal: settlement scores the outcome in R",
              abs(float(settled.iloc[0]["result_r"]) + 1.0) < 1e-9,
              str(settled.iloc[0]["result_r"]))
        check("journal: settlement names the data it used",
              "5-min" in str(settled.iloc[0]["settle_data"]))
        check("journal: today's realised exposure is -1R", abs(day_exposure_r() + 1.0) < 1e-9,
              str(day_exposure_r()))
        check("journal: one trade counted today", trades_today() == 1, str(trades_today()))
        check("journal: -1R stays inside the daily cap", journal_gate() == "", journal_gate())

        win = [{"strategy": "VWAP Pullback", "result_r": x, "status": "TARGET",
                "date": "2026-10-14", "ticker": "A.NS", "side": "BUY",
                "entry": 100.0, "stop": 99.0, "target": 102.0} for x in (1, 1, -1, 1, -1)]
        board = strategy_scoreboard(_fake_journal(win))
        vp = board["VWAP Pullback"]
        check("journal: win rate is measured, not assumed", vp["win_rate"] == 60.0, str(vp))
        check("journal: average R per trade", abs(vp["avg_r"] - 0.2) < 1e-9, str(vp))
        check("journal: profit factor", abs(vp["profit_factor"] - 1.5) < 1e-9, str(vp))
        check("journal: a never-used strategy reports no stats yet",
              board["Gap Fill Fade"]["trades"] == 0)
        check("journal: expectancy waits for min_trades_to_judge",
              expectancy_map(_fake_journal(win)) == {} and
              CONFIG.min_trades_to_judge > len(win))
        lose = [{"strategy": "RSI Reversal", "result_r": -0.8, "status": "STOPPED",
                 "date": "2026-10-14", "ticker": "A.NS", "side": "BUY",
                 "entry": 100.0, "stop": 99.0, "target": 102.0}
                for _ in range(CONFIG.min_trades_to_judge)]
        em = expectancy_map(_fake_journal(lose))
        check("journal: enough evidence publishes an expectancy",
              em.get("RSI Reversal") == -0.8 and len(em) == 1, str(em))
        judged = build_trade_call(fl, expectancy=em)
        plain_fl = build_trade_call(fl)
        check("journal: a strategy you lose money on gets muted",
              any(s.name == "RSI Reversal" and s.muted for s in judged["signals"]),
              [(s.name, s.muted) for s in judged["signals"]])
        wm = {s.name: s.weight for s in judged["signals"]}
        pm = {s.name: s.weight for s in plain_fl["signals"]}
        check("journal: muting really cuts that strategy's vote",
              wm.get("RSI Reversal", 1) < pm.get("RSI Reversal", 1)
              and all(wm[k] <= pm[k] for k in pm), f"{wm} vs {pm}")
        three = _fake_journal([dict(d, result_r=-1.0, status="STOPPED") for d in
                               [{"strategy": "ORB-15 Breakout", "date": "2026-10-14",
                                 "time": "10:00", "ticker": "A.NS", "side": "BUY",
                                 "entry": 100.0, "stop": 99.0, "target": 102.0}] * 3])
        check("journal: three stop-outs (-3R) trip the daily loss cap",
              "loss cap" in journal_gate("2026-10-14", three), journal_gate("2026-10-14", three))
        too_many = _fake_journal([dict(d, result_r=0.0)
                                  for d in [{"strategy": "VWAP Pullback",
                                             "date": "2026-10-14", "time": "10:00",
                                             "ticker": "A.NS", "side": "BUY",
                                             "entry": 100.0, "stop": 99.0,
                                             "target": 102.0}] * CONFIG.max_trades_per_day])
        check("journal: the trades-per-day limit trips too",
              "already logged today" in journal_gate("2026-10-14", too_many),
              journal_gate("2026-10-14", too_many))
        check("journal: a single loss is not a reason to quit",
              journal_gate("2026-10-14", _fake_journal([dict(
                  three.iloc[0].to_dict(), result_r=-1.0)])) == "")
        rep = journal_report(verbose=False)
        check("journal: scoreboard report names the strategies",
              "TRADE JOURNAL" in rep and "VWAP Pullback" in rep and "CIRCUIT" not in rep,
              rep[:200])

        # broker CSV import (the NALCO path)
        src = LIVE
        broker = pd.DataFrame({"Date": [f"{t:%d/%m/%Y}" for t in src.index],
                               "Time": [f"{t:%H:%M:%S}" for t in src.index],
                               "Open": src["Open"].values, "High": src["High"].values,
                               "Low": src["Low"].values, "Close": src["Close"].values,
                               "Volume": src["Volume"].values, "Trades": 1})
        csvp = os.path.join(tmp, "NALCO_1min.csv")
        broker.to_csv(csvp, index=False)
        cs = load_session_from_csv(csvp, "NALCO")
        check("csv import: broker Date/Time/OHLCV columns understood",
              cs.ticker == "NALCO.NS" and len(cs.m1) > 150, str(len(cs.m1)))
        check("csv import: bars sit on the IST clock inside the session",
              str(cs.m1.index.tz) == "Asia/Kolkata" and f"{cs.m1.index.min():%H:%M}" == "09:16",
              str(cs.m1.index.min()))
        check("csv import: provenance is stated honestly", "broker CSV" in cs.data_note, cs.data_note)
        check("csv import: the whole engine runs on imported bars",
              build_trade_call(cs, regime=r_up)["snapshot"]["price"] > 0)
        bad_csv = os.path.join(tmp, "readme.csv")
        with open(bad_csv, "w", encoding="utf-8") as fh:
            fh.write("a,b\n1,2\n")
        try:
            load_session_from_csv(bad_csv, "X")
            check("csv import: a file without OHLCV fails loudly instead of guessing", False)
        except DataError:
            check("csv import: a file without OHLCV fails loudly instead of guessing", True)

        # LEVEL 11 scan + LEVEL 12 one-command entry
        rows = scan_universe(verbose=False)
        check("scan: every universe symbol is analysed",
              len(rows) == 3 and all(r["side"] in ("BUY", "SELL", "NONE") for r in rows))
        check("scan: setups are ranked best first",
              [r["score"] for r in rows] == sorted([r["score"] for r in rows], reverse=True),
              str([r["score"] for r in rows]))
        check("scan: the regime gate is applied to every row",
              all(r["regime"] == "TREND_UP" for r in rows))
        best = best_trade_now(verbose=False)
        check("best_trade_now returns one complete plan",
              best and best["usable"] and best["entry"] and best["stop"] and
              best["target"] and best["qty"] and best["rr"] >= CONFIG.risk_reward_min,
              str(best)[:160])
        res = trade_call("AAA", verbose=False, chart=False)
        check("one-command: a good stock gets a YES with levels",
              res["side"] in ("BUY", "SELL") and res["tradeable"] is True and res["plan"],
              f"{res['side']} {res['warnings'][:1]}")
        check("one-command: the report opens with the market regime",
              "REGIME:" in _fmt_call(res, res["warnings"], res["alternatives"]))
        details = res["details"]
        check("one-command: stock details are attached",
              details.get("ltp", 0) > 0 and "trend" in details and "quality_score" in details,
              str(details)[:120])
        p = export_call(res, warns=res["warnings"], path=os.path.join(tmp, "call.json"))
        loaded = json.load(open(p, encoding="utf-8"))
        check("export: JSON round-trip keeps verdict, plan and regime",
              loaded["ticker"] == "AAA.NS" and loaded["verdict"] == res["side"] and
              loaded["plan"]["entry"] > 0 and loaded["regime"]["label"] == "TREND_UP")

        # symbol with no feed at all (the NALCO case) -> honest + automatic swap
        G["_download_1m"] = lambda ticker, now: ((pd.DataFrame(), ticker)
                                                 if str(ticker).upper().startswith("NALCO")
                                                 else (LIVE.copy(), ticker))
        res_nd = trade_call("NALCO", verbose=False, chart=False)
        check("one-command: no-feed stock returns NO_DATA, never invented prices",
              res_nd["side"] == "NO_DATA" and res_nd["tradeable"] is False and
              "1-minute data" in res_nd["reason"], str(res_nd["reason"])[:120])
        check("one-command: no-feed stock still names a better stock to trade",
              res_nd["suggested"] and res_nd["suggested"]["side"] in ("BUY", "SELL"),
              str(res_nd["suggested"])[:120])
        det_nd = stock_details("NALCO", verbose=False)
        check("details: says what is missing and how to fix it (broker CSV)",
              det_nd["available"] is False and "load_session_from_csv" in det_nd["report"])
        # a stock that fails the quality gate -> replacement suggested
        G["_download_1m"] = lambda ticker, now: (LIVE.copy(), ticker)
        G["fetch_fundamentals"] = lambda ticker: (
            {"market_cap": 1e8, "avg_vol": 10, "avg_vol_3m": 10, "pe": None, "pb": None,
             "de": None, "roe": None, "op_margin": None, "net_margin": None, "beta": None,
             "wk52_high": None, "wk52_low": None, "name": "PennyCo", "avg_vol_live": None}
            if str(ticker).startswith("AAA") else dict(_SYNTH_FUND))
        res_bad = trade_call("AAA", verbose=False, chart=False)
        pick = res_bad.get("suggested") or (res_bad["alternatives"][0]
                                           if res_bad.get("alternatives") else None)
        check("one-command: an unsuitable stock is refused",
              res_bad["tradeable"] is False and
              any("[BLOCK]" in x for x in res_bad["warnings"]), str(res_bad["warnings"])[:160])
        check("one-command: a better stock is suggested automatically",
              pick is not None and pick["ticker"] != "AAA.NS" and pick["entry"] > 0,
              str(pick)[:160])
        check("one-command: the suggestion is explained in the report text",
              "TRADE THIS INSTEAD" in _fmt_call(res_bad, res_bad["warnings"],
                                                 res_bad["alternatives"]) or
              "BETTER ALTERNATIVES" in _fmt_call(res_bad, res_bad["warnings"],
                                                  res_bad["alternatives"]))
    finally:
        for k, v in keep_fn.items():
            G[k] = v
        (CONFIG.journal_file, CONFIG.universe, CONFIG.watchlist) = keep_cfg
        _SESSION_CACHE.clear()
        _MARKET_CACHE.clear()
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass
    print("SELF-TESTS:", "ALL PASS" if ok else "FAILURES PRESENT")
    return ok


# ---------------------------------------------------------------------------
# EXAMPLE USAGE  (run after market open, e.g. at 12:15 IST)
# ---------------------------------------------------------------------------
EXAMPLE = '''
# --- STEP 1: set your own money parameters (run once per session) ----------
CONFIG.capital   = 200_000        # Rs you can deploy intraday
CONFIG.risk_pct  = 0.005          # risk 0.5% per trade
CONFIG.watchlist = ("RELIANCE.NS", "TCS.NS", "INFY.NS",
                    "SBIN.NS", "ITC.NS", "HDFCBANK.NS")   # for alternatives

# --- STEP 2: sanity-check the engine (offline, no internet) ----------------
run_self_tests()                  # want: SELF-TESTS: ALL PASS

# --- STEP 3: analyse a stock right now (report + inline chart) -------------
res = trade_recommendation("RELIANCE")

# --- STEP 4: ask your "can I sell at 500?" question -----------------------
try:
    res = trade_recommendation("SBIN", user_target=500)
except DataError as e:
    print(e)          # renamed/delisted/no-data symbol - nothing is ever invented
#   -> if 500 needs more move than the session has left you get a
#      "[SAFETY] ... NOT SAFE" warning + a realistic target zone,
#      and if the stock itself is unsuitable, a BETTER ALTERNATIVES list.

# --- STEP 5: review a past moment of today's session ----------------------
res = trade_recommendation("INFY", user_target=1100, replay_at="12:15")

# --- STEP 6: fast re-runs + manual watchlist scan -------------------------
sess = fetch_session("RELIANCE")                      # download once...
res  = trade_recommendation("RELIANCE", session=sess) # ...reuse many times
alts = suggest_alternatives(sess)                     # best other stocks now

# --- STEP 7: read the result programmatically ----------------------------
print(res["side"])                       # BUY / SELL / NONE
print(res["warnings"])                   # list of safety strings
if res["plan"]:
    s = res["plan"]["signal"]
    print(res["plan"]["qty"], s.entry, s.stop, s.target, res["plan"]["rr"])

# NOTE: some NSE symbols are renamed/delisted on Yahoo (e.g. TATAMOTORS after
# the demerger). If you see "No 1-minute data on Yahoo for ...", use one of the
# symbols it suggests - the tool never invents prices.
'''


def trade_prompt(first: str | None = None) -> None:
    """INTERACTIVE: run this and it ASKS you for a stock name, prints the full
    trade_call() answer (details -> BUY/SELL/NO-TRADE -> a better stock if this
    one can't be traded now), then asks for the next name. Type a blank line to
    stop.

        trade_prompt()               # keeps asking until you press Enter on empty
        trade_prompt("NALCO")        # start with one stock, then keep going

    Works in a Colab/Jupyter cell (it uses input()). In a non-interactive run it
    does not hang - it falls back to telling you to call trade_call() directly.
    """
    print("Type a stock name to analyse it (just NALCO, SBIN, RELIANCE... "
          "no .NS needed). Press Enter on an empty line to finish.")
    name = first
    while True:
        if name is None:
            try:
                name = input("\nstock> ")
            except (EOFError, KeyboardInterrupt):
                print("\n(this cell is not interactive - run  trade_call(\"RELIANCE\")  "
                      "directly instead)")
                return
        name = (name or "").strip()
        if not name:
            print("done.")
            return
        csv = None
        low = name.lower()
        if low.endswith(".csv") or "," in name:      # 'NALCO,myfile.csv' or a bare path
            parts = [p.strip() for p in name.split(",") if p.strip()]
            name = next((p for p in parts if not p.lower().endswith(".csv")), parts[0])
            csv = next((p for p in parts if p.lower().endswith(".csv")), None)
        try:
            trade_call(name, csv=csv)
        except Exception as e:                       # noqa: BLE001 - keep the loop alive
            print(f"  could not analyse {name}: {e}")
        name = None


def _cli_mods(argv: list) -> tuple:
    """Pull the optional switch set + a --csv path out of argv. Kept separate
    from _parse_cli_args so the (ticker, target, replay) contract stays a clean
    3-tuple. Recognised: --scan, --best, --details, --no-chart, --csv <file>."""
    argv = list(argv)
    csv_path = None
    for i, a in enumerate(argv):
        if a in ("--csv", "-csv") and i + 1 < len(argv):
            csv_path = argv[i + 1]
    flags = {f for f in argv if f in ("--scan", "--best", "--details", "--no-chart",
                                      "--ask")}
    return flags, csv_path


def _demo_main(argv: list) -> int:
    """Safe entry point for BOTH a terminal and a notebook cell.

    Running this file inside Colab/Jupyter used to crash, because there
    `__name__` is '__main__' and argv holds kernel launch args such as
    ['-f', '/root/.../kernel-xxxx.json'] - a config path is not a price.
    """
    if "--selftest" in argv:
        return 0 if run_self_tests() else 1
    ticker, target, replay = _parse_cli_args(argv)
    flags, csv_path = _cli_mods(argv)
    chart = "--no-chart" not in flags

    if in_notebook() or not (ticker or flags):
        # 'auto_analyze' lets you get an answer just by re-running the file.
        want = str(CONFIG.auto_analyze).strip()
        if want:
            print(f"INTRADAY TRADING ANALYZER - auto_analyze={want!r}, running it now "
                  f"(live data, needs internet)...\n")
            return _run_auto(want)
        # Otherwise: library mode. Lead with the ONE thing to do next, then the
        # rest as reference.
        where = ("You ran this file as a notebook cell - library mode, it only "
                 "loaded the functions" if in_notebook() else "Nothing to do yet")
        print("=" * 74)
        print("INTRADAY TRADING ANALYZER (NSE/BSE) - "
              "library mode, nothing executed yet.")
        print(f"{where}. That is normal: a big analysis engine should not start "
              "downloading by itself.")
        print("=" * 74)
        print()
        print("  >>> DO THIS NEXT <<<")
        print('      Add a NEW cell, paste this ONE line, and run it:')
        print()
        print('          trade_call("RELIANCE")        # any stock: NALCO, SBIN, TCS...')
        print()
        print('      Or let it ASK you, again and again, in one cell:')
        print()
        print('          trade_prompt()                # type a name, get the verdict')
        print()
        print('      It prints: market regime -> stock details -> BUY/SELL/NO-TRADE')
        print('      with entry/stop/target/qty -> and, if that stock is not a good')
        print('      trade right now, the best stock that IS (suggested automatically).')
        print()
        print("  Or make it run by itself: set CONFIG.auto_analyze = 'BEST' (or a")
        print("  stock name like 'RELIANCE') above, then re-run this cell.")
        print()
        print("  If you imported the file as a module instead of pasting it:")
        print("       from Intraday_Trader_Colab import *")
        print("       trade_call(\"NALCO\")")
        print()
        print("-" * 74)
        print("More things to try (full reference):\n")
        print(EXAMPLE)
        print("-'user_target' tip: ask 'can I reach price X today?' with e.g. "
              'trade_call("SBIN", user_target=500).')
        print()
        print("Terminal examples:")
        print("  python Intraday_Trader_Colab.py --selftest")
        print("  python Intraday_Trader_Colab.py NALCO                 # one-command answer")
        print("  python Intraday_Trader_Colab.py NALCO --csv NALCO_1min.csv   # broker bars")
        print("  python Intraday_Trader_Colab.py RELIANCE 1200 [12:15] # old-style target")
        print("  python Intraday_Trader_Colab.py --best               # scan the whole universe")
        print("  python Intraday_Trader_Colab.py --scan               # rank the watchlist")
        print("  python Intraday_Trader_Colab.py --ask                # type stock names, get verdicts")
        return 0

    try:
        return _run_cli(ticker, target, replay, flags, csv_path, chart)
    except DataError as e:
        print(f"ERROR: {e}")
        return 2


def _run_auto(want: str) -> int:
    """CONFIG.auto_analyze helper - runs one live command from a notebook cell."""
    try:
        w = want.strip().upper()
        if w == "BEST":
            best_trade_now()
        elif w == "SCAN":
            scan_universe()
        elif w == "ASK":
            trade_prompt()
        else:
            trade_call(want)
        return 0
    except DataError as e:
        print(f"ERROR: {e}")
        return 2


def _run_cli(ticker, target, replay, flags, csv_path, chart) -> int:
    """Real-terminal dispatch (kept separate so the notebook path stays simple)."""
    if "--best" in flags:
        best_trade_now()
    elif "--scan" in flags:
        scan_universe()
    elif "--ask" in flags:
        trade_prompt(ticker)          # interactive: type stock names in the terminal
    elif "--details" in flags and ticker:
        stock_details(ticker)
    else:
        # the headline one-command path: regime + details + verdict + suggest
        res = trade_call(ticker, user_target=target, chart=chart,
                         replay_at=replay, csv=csv_path)
        # a symbol with no price feed is still answered politely (details +
        # suggestions), but a script can detect the failure via exit code 2.
        return 0 if res.get("side") != "NO_DATA" else 2
    return 0


if __name__ == "__main__":
    _RC = _demo_main(sys.argv)
    # IPython turns a raised SystemExit into "An exception has occurred,
    # use %tb to see the full traceback" - so only exit in a real terminal.
    if not in_notebook():
        sys.exit(_RC)

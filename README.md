# 📈 Stock Analyzer — Intraday Trading Analyzer (NSE/BSE)

A single-file Python tool that answers one question, honestly:

> **"Can I trade this stock right now — and if not, what SHOULD I trade?"**

Type any stock name (`SBIN`, `RELIANCE`, `NALCO`...) and it gives you the market
regime, stock details, a **BUY / SELL / NO-TRADE** verdict with exact
entry / stop-loss / target / quantity — and when your stock isn't a good trade,
it automatically suggests the best stock that *is*.

**It never invents prices.** No feed → it says so and offers alternatives.

---

## Contents

1. [What you need](#1-what-you-need)
2. [How to install & run (A to Z)](#2-how-to-install--run-a-to-z)
3. [The common errors and fixes](#3-common-errors-and-fixes)
4. [How to use it — every command](#4-how-to-use-it--every-command)
5. [How it works (the engine, step by step)](#5-how-it-works-the-engine-step-by-step)
6. [Reading the output](#6-reading-the-output)
7. [Special case: NALCO and stocks with no free feed](#7-special-case-nalco-and-stocks-with-no-free-feed)
8. [Configuration — tune it to your money](#8-configuration--tune-it-to-your-money)
9. [The trade journal (auto feedback loop)](#9-the-trade-journal-auto-feedback-loop)
10. [Running the tests](#10-running-the-tests)
11. [Using it in Google Colab](#11-using-it-in-google-colab)
12. [FAQ](#12-faq)

---

## 1. What you need

| Requirement | Details |
|---|---|
| **Python** | 3.10 or newer (3.12 recommended) — [python.org/downloads](https://www.python.org/downloads/) |
| **Operating system** | Windows / macOS / Linux — anything Python runs on |
| **Internet** | Yes — live price bars are downloaded from Yahoo Finance (free). `--selftest` works offline. |
| **Libraries** | `pandas`, `numpy`, `yfinance`, `matplotlib` (install command below) |
| **Market hours** | Run between **9:15 – 15:30 IST, Mon–Fri** for actionable signals. Outside those hours you get an honest post-close review instead. |
| **A broker account** | Optional. Needed only to export 1-minute CSVs for stocks Yahoo doesn't cover (like NALCO). |

Install the libraries (one time):

```powershell
python -m pip install pandas numpy yfinance matplotlib
```

---

## 2. How to install & run (A to Z)

Follow these 4 steps exactly. Windows / PowerShell assumed (macOS/Linux: same commands, `python3` if `python` isn't found).

### Step 1 — Download the file from GitHub

Grab **`Intraday_Trader_Colab.py`** (and `test_intraday_acceptance.py` if you want the deep test suite):

- On the GitHub page → green **Code** button → **Download ZIP**, or
- Open each file on GitHub → **Raw** view → Ctrl+S to save, or
- If you have git installed:
  ```powershell
  git clone <your-repo-url>
  ```

### Step 2 — Save it in a folder

Create a folder and put the file inside, e.g.:

```
D:\Stock Analyzer\Intraday_Trader_Colab.py
```

### Step 3 — Open PowerShell in that folder

```powershell
cd "D:\Stock Analyzer"
dir Intraday_Trader_Colab.py        # must list the file - if not, wrong folder
```

> PowerShell needs the quotes because of the space in the folder name.
> Jumping from `C:` to `D:` drive: use `cd /d "D:\Stock Analyzer"` in cmd, or just
> `cd "D:\Stock Analyzer"` in PowerShell.

### Step 4 — Run it

```powershell
python Intraday_Trader_Colab.py SBIN            # analyse one stock
python Intraday_Trader_Colab.py --ask           # interactive: type stock names one by one
python Intraday_Trader_Colab.py --best          # what should I trade RIGHT NOW?
python Intraday_Trader_Colab.py --selftest      # 90 offline checks, no internet needed
```

That's it. You'll see a regime banner, stock details, and a ONE-LINE YES/NO answer
with entry/stop/target/qty — or a better suggested stock.

---

## 3. Common errors and fixes

### ❌ "Python was not found; run without arguments to install from the Microsoft Store..."

Windows' Store stub is shadowing your real Python. Fix permanently (pick one):

**Option A — PowerShell alias (recommended, works even when the Settings page shows nothing):**

```powershell
New-Item -ItemType File -Force $PROFILE | Out-Null
Add-Content $PROFILE 'Set-Alias python "C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe"'
. $PROFILE
```
(Use your actual python.exe path — find it with:
`Get-ChildItem "$env:LOCALAPPDATA\Programs\Python" -Recurse -Filter python.exe`.)

**Option B — disable the stub:** Settings → Apps → Advanced app settings →
App execution aliases → toggle **off** `python.exe` / `python3.exe` (App Installer).

**Option C — always use the full path:**

```powershell
& "C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe" Intraday_Trader_Colab.py SBIN
```

### ❌ "can't open file 'C:\\WINDOWS\\system32\\Intraday_Trader_Colab.py': No such file or directory"

You're in the wrong folder. The file is on `D:`:

```powershell
cd "D:\Stock Analyzer"
python Intraday_Trader_Colab.py SBIN
```

Or run it from anywhere with the full script path:

```powershell
python "D:\Stock Analyzer\Intraday_Trader_Colab.py" SBIN
```

### ❌ "ModuleNotFoundError: No module named 'yfinance'" (or pandas/numpy/matplotlib)

```powershell
python -m pip install pandas numpy yfinance matplotlib
```

### ❌ "No 1-minute data on Yahoo for XYZ.NS"

Not an error — Yahoo genuinely has no intraday feed for that symbol (NALCO,
TATAMOTORS post-demerger, etc.). The tool tells you working alternatives and never
guesses. Use a broker CSV for those stocks → [section 7](#7-special-case-nalco-and-stocks-with-no-free-feed).

### ❌ Verdict is always "Market CLOSED / not actionable"

You ran outside 9:15–15:30 IST Mon–Fri. Wait for market hours. (The analysis still
runs — it's a post-close review, not a live signal.)

---

## 4. How to use it — every command

### Terminal (PowerShell)

| Command | What it does |
|---|---|
| `python Intraday_Trader_Colab.py --ask` | **Interactive mode.** Prompts `stock>` — type any name (empty Enter quits). For no-feed stocks type `NALCO,NALCO_1min.csv` to attach a broker file. |
| `python Intraday_Trader_Colab.py SBIN` | Full one-command analysis of one stock. |
| `python Intraday_Trader_Colab.py SBIN --no-chart` | Same, without drawing the chart. |
| `python Intraday_Trader_Colab.py RELIANCE 1400` | "Can RELIANCE reach 1400 today?" → SAFE / NOT SAFE + realistic target zone. |
| `python Intraday_Trader_Colab.py INFY 1100 12:15` | Same question, reviewed *as if* it were 12:15 IST (replay). |
| `python Intraday_Trader_Colab.py --best` | Scans a 20-stock universe, prints **the single best trade right now** + runner-ups. |
| `python Intraday_Trader_Colab.py --scan` | Ranked table of every setup in the universe. |
| `python Intraday_Trader_Colab.py SBIN --details` | Just the details (price, trend, fundamentals, quality gate), no verdict. |
| `python Intraday_Trader_Colab.py NALCO --csv NALCO_1min.csv` | Analyse a broker-exported 1-min CSV (the no-feed escape hatch). |
| `python Intraday_Trader_Colab.py --selftest` | 90 built-in offline checks. Must end **SELF-TESTS: ALL PASS**. |

### Python / Colab / any REPL

```python
from Intraday_Trader_Colab import *

trade_call("SBIN")                      # THE one command: everything + YES/NO + suggestion
trade_call("RELIANCE", user_target=1400)# "can it reach 1400 today?"
trade_call("NALCO", csv="NALCO_1min.csv")
trade_prompt()                          # interactive loop, asks for stock names
best_trade_now()                        # "what should I trade right now?" over 20 stocks
scan_universe()                         # ranked table of all setups
stock_details("TATAMOTORS")             # honest details, no verdict
trade_recommendation("INFY", replay_at="12:15")  # time-machine review of today
load_session_from_csv("NALCO_1min.csv", "NALCO")  # broker bars -> Session object
export_call(res)                        # JSON snapshot of any trade_call result
```

---

## 5. How it works (the engine, step by step)

```
your stock name
      │
      ▼
┌─ 1. DATA LAYER ───────────────────────────────────────────────┐
│ Yahoo Finance 1-minute bars (never guesses - missing = said  │
│ out loud) → resampled to 5-min, sliced to 9:15-15:30 IST,    │
│ 3-min session cache, fundamentals + previous dailies.         │
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌─ 2. MARKET REGIME GATE (L9) ──────────────────────────────────┐
│ NIFTY 20-day trend + intraday VWAP chop + gap + Bank Nifty +  │
│ India VIX → labels: TREND_UP / TREND_DOWN / CHOP / MIXED /    │
│ RISK_OFF.  RISK_OFF blocks ALL new entries; each label        │
│ re-weights strategies and multiplies position size (x0.6 etc).│
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌─ 3. QUALITY GATE (L5/L6) ─────────────────────────────────────┐
│ market cap, liquidity (avg volume), P/E, P/B, ROE, margins,   │
│ beta, 52-wk range, ATR wildness → 0-10 score, junk filtered.  │
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌─ 4. 8 STRATEGIES vote (ensemble, L4) ─────────────────────────┐
│ S1 ORB-15 Breakout      S2 VWAP Pullback    S3 EMA 9/20 Cross  │
│ S4 RSI Reversal         S5 Supertrend       S6 VWAP Fade       │
│ S7 Relative Strength vs NIFTY (leader/laggard)                 │
│ S8 Gap Fill Fade (unfinished gap = magnet)                     │
│ Votes are weighted: trend-alignment × regime × YOUR journal's  │
│ expectancy (losing strategies get muted).                      │
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌─ 5. RISK & PLAN (L5) ─────────────────────────────────────────┐
│ Entry, stop (structure/ATR), target (min R:R), quantity =     │
│ capital × risk% ÷ stop-distance, ×regime multiplier.          │
│ Invariants: R:R ≥ minimum, risk per trade ≤ cap, square-off   │
│ 15:15, daily loss cap -2R, max 5 trades/day (circuit breaker).│
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌─ 6. SAFETY WARNINGS (L7) ─────────────────────────────────────┐
│ [TIME] market closed/late entry, [BLOCK] illiquid, [VETO]     │
│ counter-regime trade, [SAFETY] your target needs more move    │
│ than the session has left, [CIRCUIT] over-trading, [DATA]     │
│ stale/broker-CSV provenance notes.                            │
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌─ 7. VERDICT + ALTERNATIVES (L11/L12) ─────────────────────────┐
│ ONE-LINE ANSWER: YES → full trade card.                       │
│ ONE-LINE ANSWER: NO  → scans watchlist + 20-stock universe     │
│ and prints "TRADE THIS INSTEAD" with its own entry/SL/target. │
└──────────────────────────────┬────────────────────────────────┘
                               ▼
┌─ 8. JOURNAL LOOP (L10) ───────────────────────────────────────┐
│ Every live plan → trade_journal.csv. After the close it is    │
│ settled on the REAL bars into R multiples → scoreboard        │
│ (win%, expectancy, profit factor) feeds back into step 4's    │
│ weights and enforces the daily loss cap / trade limit.        │
└───────────────────────────────────────────────────────────────┘
```

**Honesty rules the engine never breaks:**
- Missing data is announced, never fabricated (no invented candles/prices).
- A verdict of NO is a valid output — "sitting out is a position".
- Every number on screen traces to a real bar or a stated assumption.

---

## 6. Reading the output

```
==========  SBIN  @  15 Oct 2026 12:15 IST  [OPEN] ==========
  REGIME: MIXED (neutral, confidence 90%) | NIFTY 22,991 slope -0.21%/day
          | India VIX 14.88 (+1.7%) | size x0.6        ← market gate
  STOCK DETAILS | SBIN.NS                               ← price/trend/fundamentals
  FUNDAMENTAL GATE: score 8.5/10 -> PASS                ← quality filter
  STRATEGY SIGNALS (2):                                 ← the ensemble votes
    [BUY] Relative Strength Momentum  str 0.90  entry 959.60 SL 956.72 T 965.36
  VERDICT: BUY                                          ← decision
  Entry ~Rs 959.60 | SL Rs 956.72 | Target1 Rs 963.92 | Qty 208
  Risk Rs 599 = 0.6% of capital | R:R 2.00 | [regime size x0.6]
  WARNINGS: [REGIME] MIXED - cut size to 60% ...         ← read these first!
  ONE-LINE ANSWER: YES - trade SBIN.NS BUY now.
  Exit compulsorily by 15:15 IST. If 956.72 is touched, no averaging.
==========================================================
```

- **str** = signal strength 0–1; **R:R** = reward per rupee of risk;
  **Qty** is already sized to your capital & risk settings.
- If instead you see `NO ... TRADE THIS INSTEAD: <stock>` — that stock passed
  *every* gate; the suggestion card has its own entry/SL/target/qty.

---

## 7. Special case: NALCO and stocks with no free feed

Yahoo carries **no intraday bars** for NALCO (verified Oct 2026 — `.NS`, `.BO`,
daily, all 404/empty; Screener and NSE also block free scrapers). The tool says
this honestly rather than inventing data.

**Still want to analyse NALCO? Export bars from your broker:**

1. In your broker terminal (Zerodha Kite / StockGraph / Dhan / Neural), open
   NALCO charts on **1-minute** interval and **export CSV** (any column names —
   it auto-recognises `Date/Time`, `datetime`, `Open/High/Low/Close`, `Volume/Vol/LTP`...).
2. Save it next to the script, then:

```powershell
python Intraday_Trader_Colab.py NALCO --csv NALCO_1min.csv
```

or interactive: at the `stock>` prompt type `NALCO,NALCO_1min.csv`.

Indicators are then computed on *your* exact bars; the report notes the
fundamentals may be stale. The full engine (regime, ensemble, sizing, journal)
runs identically on imported bars.

---

## 8. Configuration — tune it to your money

Edit these once per session (before running calls):

```python
CONFIG.capital       = 200_000      # Rs you can deploy intraday
CONFIG.risk_pct      = 0.005        # risk 0.5% per trade
CONFIG.watchlist     = ("RELIANCE.NS", "TCS.NS", ...)   # alternative pool
CONFIG.universe      = (...)        # 20 stocks --best/--scan searches
CONFIG.daily_loss_cap_r = 2.0       # stop trading at -2R for the day
CONFIG.max_trades_per_day = 5       # over-trading circuit breaker
CONFIG.regime_enabled = True        # market gate on/off
CONFIG.min_quality_score = 4.0      # fundamental gate (0-10)
CONFIG.vix_risk_off    = 16.0       # VIX >= this: no new entries
```

**`CONFIG.auto_analyze`** — make it run by itself when the file/cell executes:

```python
CONFIG.auto_analyze = "BEST"       # scan universe immediately -> best trade now
CONFIG.auto_analyze = "ASK"        # interactive prompt loop
CONFIG.auto_analyze = "RELIANCE"   # analyse that stock immediately
CONFIG.auto_analyze = ""           # just load (default)
```

---

## 9. The trade journal (auto feedback loop)

Every BUY/SELL plan (with a live market) is appended to **`trade_journal.csv`**:
date, ticker, side, strategy, entry/stop/target/qty, regime, quality, status.

```python
journal_report()               # scoreboard: per-strategy win%, avg R, expectancy
settle_journal()               # re-check OPEN plans against real bars after close
```

Why it matters: the engine **mutes strategies your own journal proved
unprofitable** (≥8 trades, negative expectancy), enforces the **-2R daily stop**
and the **5-trades/day circuit breaker**, and prints the scoreboard with every call.

---

## 10. Running the tests

| Test | Command | Expect |
|---|---|---|
| Built-in self-tests (offline) | `python Intraday_Trader_Colab.py --selftest` | `SELF-TESTS: ALL PASS` (90 checks) |
| Deep acceptance suite (offline) | `python test_intraday_acceptance.py --offline` | `TOTAL 143 checks \| PASS 143 \| FAIL 0` |
| Full suite incl. live Yahoo | `python test_intraday_acceptance.py` | `TOTAL 177 checks \| PASS 177 \| FAIL 0` |

Run these after any edit — they cover the clock, indicator maths, data layer,
risk invariants, quality gate, ensemble, safety text, chart, regime gate,
journal, scan, CSV import, and Colab-cell compatibility.

---

## 11. Using it in Google Colab

1. **File** → **Upload** → `Intraday_Trader_Colab.py`
2. Cell 1:
   ```python
   from Intraday_Trader_Colab import *
   ```
   (or paste the whole file into one cell and run it — everything is then defined)
3. Cell 2:
   ```python
   trade_call("SBIN")          # details + verdict + auto-suggestion
   ```
   or `trade_prompt()` for the interactive loop, or `best_trade_now()`.

Running the file as a cell prints guidance instead of downloading — set
`CONFIG.auto_analyze = "BEST"` (or `"ASK"`) and re-run to get an immediate answer.

---

## 12. FAQ

**Do I pay for any data?** No — Yahoo Finance free feed. Broker CSVs for the
no-feed symbols. **Does it place orders?** No — it's an analyzer; execution stays
with you.

**Why did it say NO for my stock?** Too choppy/illiquid/counter-regime/late/day's
loss cap hit — and it always shows *why*, plus the best alternative.

**When do I get the best results?** During 9:30–14:30 IST on active trading days,
with `CONFIG.capital/risk_pct` set to your real numbers.

**Can I add my own strategy or stocks?** Yes — append to `CONFIG.universe` /
`CONFIG.watchlist`; strategies are plain functions (`s1_orb`... `s8_gap_fill`)
in `STRATEGIES`.

**Is this financial advice?** No. It's a decision-support tool; intraday trading
carries real risk of loss. Use the stop-losses it prints.

---

*Built as a single paste-able file: `Intraday_Trader_Colab.py` (~2,900 lines) +
optional `test_intraday_acceptance.py` (177 checks). Verified live Oct 2026:
90/90 self-tests, 143/143 offline, 177/177 vs real Yahoo data.*

import os
import hmac
import hashlib
import sqlite3
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_NAME = "ZOHAIR PO3 AI AGENT"
DB_PATH = os.getenv("DB_PATH", "zohair_agent.db")
AGENT_SECRET = os.getenv("AGENT_SECRET", "")

app = FastAPI(title=APP_NAME, version="1.0.0")


class Signal(BaseModel):
    agent: str = APP_NAME
    signal: str
    symbol: str
    timeframe: str = "5"
    entry: float = Field(gt=0)
    manipulation_high: float = Field(gt=0)
    manipulation_low: float = Field(gt=0)
    sl: float = Field(gt=0)
    tp: float = Field(gt=0)
    entry_model: str = ""
    timestamp: int


def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def initialize():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT UNIQUE NOT NULL,
                signal TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                entry REAL NOT NULL,
                manipulation_high REAL NOT NULL,
                manipulation_low REAL NOT NULL,
                sl REAL NOT NULL,
                tp REAL NOT NULL,
                rr REAL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                entry_model TEXT,
                timestamp INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


@app.on_event("startup")
def startup():
    initialize()


def analyze(s: Signal):
    direction = s.signal.upper()
    symbol = s.symbol.upper()

    if direction not in ("BUY", "SELL"):
        return "REJECTED", "Signal must be BUY or SELL", None
    if "XAU" not in symbol and "GOLD" not in symbol:
        return "REJECTED", "Only XAU symbols are accepted", None
    if s.timeframe not in ("5", "5m", "M5"):
        return "REJECTED", "Only M5 signals are accepted", None
    if s.manipulation_high <= s.manipulation_low:
        return "REJECTED", "Manipulation high must exceed manipulation low", None

    risk = abs(s.entry - s.sl)
    reward = abs(s.tp - s.entry)
    if risk <= 0:
        return "REJECTED", "Entry and stop loss cannot be equal", None

    if direction == "BUY":
        if not s.sl < s.entry < s.tp:
            return "REJECTED", "BUY levels must satisfy SL < Entry < TP", None
        if s.sl >= s.manipulation_low:
            return "REJECTED", "BUY stop must be below manipulation low", None
    else:
        if not s.tp < s.entry < s.sl:
            return "REJECTED", "SELL levels must satisfy TP < Entry < SL", None
        if s.sl <= s.manipulation_high:
            return "REJECTED", "SELL stop must be above manipulation high", None

    rr = reward / risk
    if not 1.8 <= rr <= 2.2:
        return "REJECTED", f"Expected approximately 2R; received {rr:.2f}R", round(rr, 2)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if abs(now_ms - s.timestamp) > 15 * 60 * 1000:
        return "REJECTED", "Signal timestamp is outside the 15-minute acceptance window", round(rr, 2)

    return "RECEIVED", "Structure and risk checks passed; this is not a prediction or trade confirmation", round(rr, 2)


@app.get("/")
def home():
    return {
        "agent": APP_NAME,
        "status": "ONLINE",
        "mode": "ALERTS_ONLY",
        "market": "XAUUSD",
        "timeframe": "M5"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/webhook/tradingview/{token}")
def tradingview_webhook(token: str, signal: Signal):
    if not AGENT_SECRET or not hmac.compare_digest(token, AGENT_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")

    status, reason, rr = analyze(signal)
    raw = (
        f"{signal.symbol}|{signal.signal.upper()}|{signal.timestamp}|"
        f"{signal.entry}|{signal.sl}|{signal.tp}"
    )
    fingerprint = hashlib.sha256(raw.encode()).hexdigest()

    try:
        with connect() as db:
            db.execute("""
                INSERT INTO signals (
                    fingerprint, signal, symbol, timeframe, entry,
                    manipulation_high, manipulation_low, sl, tp, rr,
                    status, reason, entry_model, timestamp, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fingerprint, signal.signal.upper(), signal.symbol,
                signal.timeframe, signal.entry, signal.manipulation_high,
                signal.manipulation_low, signal.sl, signal.tp, rr,
                status, reason, signal.entry_model, signal.timestamp,
                datetime.now(timezone.utc).isoformat()
            ))
    except sqlite3.IntegrityError:
        return {"received": True, "decision": "DUPLICATE"}

    return {
        "received": True,
        "agent": APP_NAME,
        "decision": status,
        "reason": reason,
        "rr": rr
    }


@app.get("/api/signals")
def get_signals(limit: int = 30):
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"signals": [dict(row) for row in rows]}


@app.get("/api/latest")
def latest():
    with connect() as db:
        row = db.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {"signal": dict(row) if row else None}

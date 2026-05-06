import os
import psycopg2
import psycopg2.extras
from datetime import datetime
from flask import Flask, jsonify, request
import pytz

app = Flask(__name__)

TIMEZONE      = pytz.timezone("Asia/Dubai")
CLAUDE_SECRET = os.environ.get("UAE_CLAUDE_SECRET", "uae_claude_2026")
DATABASE_URL  = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def today_uae():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

def init_db():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS uae_signals (
            id         BIGSERIAL PRIMARY KEY,
            symbol     TEXT,
            signal     TEXT,
            entry      NUMERIC,
            stop       NUMERIC,
            target     NUMERIC,
            rsi        NUMERIC,
            volume     BIGINT,
            market     TEXT DEFAULT 'UAE',
            date       DATE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route("/setup")
def setup():
    try:
        init_db()
        return jsonify({"status": "table created"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({
        "service":  "UAE ADX Signals API",
        "status":   "running",
        "time":     datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M"),
        "timezone": "Asia/Dubai (UTC+4)"
    })

@app.route("/watchdog")
def watchdog():
    return jsonify({"ok": True, "time": datetime.now(TIMEZONE).isoformat()})

@app.route("/bot/run")
def bot_run():
    if request.args.get("secret") != CLAUDE_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    try:
        from uae_bot_v1 import run_bot
        result = run_bot()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals/add", methods=["POST"])
def add_signal():
    data = request.get_json()
    if not data or data.get("secret") != CLAUDE_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO uae_signals
                (symbol, signal, entry, stop, target, rsi, volume, market, date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get("symbol"),
            data.get("signal"),
            data.get("entry"),
            data.get("stop"),
            data.get("target"),
            data.get("rsi"),
            data.get("volume"),
            "UAE",
            today_uae(),
            datetime.now(TIMEZONE).isoformat()
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals/check")
def check_signal():
    symbol = request.args.get("symbol")
    date   = request.args.get("date", today_uae())
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute(
            "SELECT id FROM uae_signals WHERE symbol = %s AND date = %s",
            (symbol, date)
        )
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return jsonify({"exists": exists})
    except Exception as e:
        return jsonify({"error": str(e), "exists": False}), 500

@app.route("/signals")
def get_signals():
    date = request.args.get("date", today_uae())
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM uae_signals WHERE date = %s ORDER BY created_at DESC",
            (date,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"date": date, "signals": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

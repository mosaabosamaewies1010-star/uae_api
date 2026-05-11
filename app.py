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
            tp1        NUMERIC,
            tp2        NUMERIC,
            grade      TEXT,
            score      INTEGER,
            rr         NUMERIC,
            rsi        NUMERIC,
            adx        NUMERIC,
            support    NUMERIC,
            resistance NUMERIC,
            volume     BIGINT,
            market     TEXT DEFAULT 'UAE',
            date       DATE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route("/migrate")
def migrate():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            ALTER TABLE uae_signals
            ADD COLUMN IF NOT EXISTS status      TEXT DEFAULT 'open',
            ADD COLUMN IF NOT EXISTS result_date DATE,
            ADD COLUMN IF NOT EXISTS pnl_pct     NUMERIC,
            ADD COLUMN IF NOT EXISTS hit_tp1     BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS hit_tp2     BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS hit_sl      BOOLEAN DEFAULT FALSE
        """)
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "migration done"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/setup")
def setup():
    try:
        init_db()
        return jsonify({"status": "table ready"})
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
        import threading
        from uae_bot_v1 import run_bot
        t = threading.Thread(target=run_bot, daemon=True)
        t.start()
        return jsonify({"status": "started"})
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
                (symbol, signal, entry, stop, target,
                 tp1, tp2, grade, score, rr,
                 rsi, adx, support, resistance,
                 market, date, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get("symbol"),
            data.get("signal"),
            data.get("entry"),
            data.get("stop"),
            data.get("tp1"),
            data.get("tp1"),
            data.get("tp2"),
            data.get("grade"),
            data.get("score"),
            data.get("rr"),
            data.get("rsi"),
            data.get("adx"),
            data.get("support"),
            data.get("resistance"),
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
            "SELECT * FROM uae_signals WHERE date = %s ORDER BY score DESC, created_at DESC",
            (date,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"date": date, "signals": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals/all")
def get_all_signals():
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM uae_signals ORDER BY created_at DESC LIMIT 500"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"signals": [dict(r) for r in rows], "count": len(rows)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals/open")
def get_open_signals():
    try:
        conn = get_conn()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM uae_signals WHERE status = 'open' OR status IS NULL ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"signals": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals/update", methods=["POST"])
def update_signal():
    data = request.get_json()
    if not data or data.get("secret") != CLAUDE_SECRET:
        return jsonify({"error": "unauthorized"}), 401
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            UPDATE uae_signals
            SET status      = %s,
                pnl_pct     = %s,
                hit_tp1     = %s,
                hit_tp2     = %s,
                hit_sl      = %s,
                result_date = %s
            WHERE id = %s
        """, (
            data.get("status"),
            data.get("pnl_pct"),
            data.get("hit_tp1"),
            data.get("hit_tp2"),
            data.get("hit_sl"),
            data.get("result_date"),
            data.get("id"),
        ))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

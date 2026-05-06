import os
import json
from datetime import datetime

import pytz
from flask import Flask, jsonify, request
from supabase import create_client, Client

app = Flask(__name__)

# ─── الإعدادات ───────────────────────────────────────────────
TIMEZONE      = pytz.timezone("Asia/Dubai")  # UTC+4
CLAUDE_SECRET = os.environ.get("UAE_CLAUDE_SECRET", "uae_claude_2026")
SUPABASE_URL  = os.environ.get("SUPABASE_URL")
SUPABASE_KEY  = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Helpers ─────────────────────────────────────────────────
def today_uae():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")

def auth(req):
    secret = req.args.get("secret") or req.json.get("secret", "") if req.is_json else req.args.get("secret", "")
    return secret == CLAUDE_SECRET

# ─── Health Check ─────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({
        "service": "UAE ADX Signals API",
        "status":  "running",
        "time":    datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M"),
        "timezone": "Asia/Dubai (UTC+4)"
    })

# ─── Watchdog ────────────────────────────────────────────────
@app.route("/watchdog")
def watchdog():
    return jsonify({"ok": True, "time": datetime.now(TIMEZONE).isoformat()})

# ─── تشغيل البوت ─────────────────────────────────────────────
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

# ─── إضافة إشارة ─────────────────────────────────────────────
@app.route("/signals/add", methods=["POST"])
def add_signal():
    data = request.get_json()
    if not data or data.get("secret") != CLAUDE_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    payload = {
        "symbol":  data.get("symbol"),
        "signal":  data.get("signal"),
        "entry":   data.get("entry"),
        "stop":    data.get("stop"),
        "target":  data.get("target"),
        "rsi":     data.get("rsi"),
        "volume":  data.get("volume"),
        "market":  "UAE",
        "date":    today_uae(),
        "created_at": datetime.now(TIMEZONE).isoformat(),
    }

    try:
        supabase.table("uae_signals").insert(payload).execute()
        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── التحقق من تكرار الإشارة ─────────────────────────────────
@app.route("/signals/check")
def check_signal():
    symbol = request.args.get("symbol")
    date   = request.args.get("date", today_uae())
    try:
        res = (
            supabase.table("uae_signals")
            .select("id")
            .eq("symbol", symbol)
            .eq("date", date)
            .execute()
        )
        exists = len(res.data) > 0
        return jsonify({"exists": exists})
    except Exception as e:
        return jsonify({"error": str(e), "exists": False}), 500

# ─── جلب الإشارات ────────────────────────────────────────────
@app.route("/signals")
def get_signals():
    date = request.args.get("date", today_uae())
    try:
        res = (
            supabase.table("uae_signals")
            .select("*")
            .eq("date", date)
            .order("created_at", desc=True)
            .execute()
        )
        return jsonify({"date": date, "signals": res.data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─── Run ──────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

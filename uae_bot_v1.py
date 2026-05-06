import os
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz

# ─── الإعدادات ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("UAE_TELEGRAM_TOKEN", "8206640637:AAE8rBc5H1iepG_tFWsb7epL_JGB2nbqRmI")
CHAT_ID        = os.environ.get("UAE_CHAT_ID", "1758789551")
API_URL        = os.environ.get("UAE_API_URL", "https://uae-api-xxxx.onrender.com")
CLAUDE_SECRET  = os.environ.get("UAE_CLAUDE_SECRET", "uae_claude_2026")
TIMEZONE       = pytz.timezone("Asia/Dubai")   # UTC+4

# ─── أسهم الشريعة ADX ────────────────────────────────────────
SYMBOLS = [
    "ADIB.AD",        # Abu Dhabi Islamic Bank
    "DIB.AD",         # Dubai Islamic Bank
    "SIB.AD",         # Sharjah Islamic Bank
    "AJIB.AD",        # Ajman Bank
    "ALDAR.AD",       # Aldar Properties
    "ESHRAQ.AD",      # Eshraq Investments
    "TAQA.AD",        # Abu Dhabi National Energy
    "ETISALAT.AD",    # e& (اتصالات)
    "METHAQ.AD",      # Methaq Takaful
    "AGTHIA.AD",      # Agthia Group
    "FERTIGLOBE.AD",  # Fertiglobe
    "IHC.AD",         # International Holding Company
    "MULTIPLY.AD",    # Multiply Group
    "GFH.AD",         # Gulf Finance House
    "GPBM.AD",        # Gulf Pharmaceutical
    "PIHC.AD",        # Primus International Holding
    "FOODCO.AD",      # Foodco Holding
    "TKFL.AD",        # Al Wathba Insurance
    "SALAMA.AD",      # Islamic Arab Insurance
]

# ─── وقت السوق ADX (الأحد - الخميس 10:00 - 14:00 UTC+4) ──────
def is_market_open():
    now = datetime.now(TIMEZONE)
    # الأحد=6, الاثنين=0, الثلاثاء=1, الأربعاء=2, الخميس=3
    if now.weekday() not in [6, 0, 1, 2, 3]:
        return False
    market_open  = now.replace(hour=10, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=14, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close

# ─── جلب البيانات ─────────────────────────────────────────────
def get_data(symbol):
    try:
        df = yf.download(symbol, period="60d", interval="1d",
                         auto_adjust=True, progress=False)
        if df is None or df.empty or len(df) < 20:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return df
    except Exception as e:
        print(f"[get_data] {symbol}: {e}")
        return None

# ─── المؤشرات الفنية ──────────────────────────────────────────
def calc_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))

def calc_indicators(df):
    df = df.copy()
    df["EMA20"]  = df["Close"].ewm(span=20).mean()
    df["EMA50"]  = df["Close"].ewm(span=50).mean()
    df["RSI"]    = calc_rsi(df["Close"])
    df["VOL_MA"] = df["Volume"].rolling(20).mean()
    return df

# ─── منطق الإشارة ────────────────────────────────────────────
def generate_signal(symbol):
    df = get_data(symbol)
    if df is None:
        return None

    df = calc_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    close   = float(last["Close"])
    ema20   = float(last["EMA20"])
    ema50   = float(last["EMA50"])
    rsi     = float(last["RSI"])
    volume  = float(last["Volume"])
    vol_ma  = float(last["VOL_MA"])

    # شروط الشراء
    buy = (
        close > ema20 > ema50 and
        30 < rsi < 70 and
        volume > vol_ma * 1.2 and
        float(prev["Close"]) < float(prev["EMA20"])  # كروس حديث
    )

    if not buy:
        return None

    entry  = round(close, 4)
    stop   = round(close * 0.97, 4)   # وقف خسارة 3%
    target = round(close * 1.05, 4)   # هدف 5%

    return {
        "symbol": symbol,
        "signal": "BUY",
        "entry":  entry,
        "stop":   stop,
        "target": target,
        "rsi":    round(rsi, 1),
        "volume": int(volume),
    }

# ─── التحقق من تكرار الإشارة ──────────────────────────────────
def already_sent_today(symbol):
    try:
        today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
        res = requests.get(
            f"{API_URL}/signals/check",
            params={"symbol": symbol, "date": today, "market": "UAE"},
            timeout=10
        )
        if res.status_code == 200:
            return res.json().get("exists", False)
    except Exception as e:
        print(f"[already_sent_today] {e}")
    return False

# ─── حفظ الإشارة عبر API ─────────────────────────────────────
def save_signal(signal_data):
    try:
        payload = {**signal_data, "market": "UAE", "secret": CLAUDE_SECRET}
        res = requests.post(
            f"{API_URL}/signals/add",
            json=payload,
            timeout=10
        )
        return res.status_code == 200
    except Exception as e:
        print(f"[save_signal] {e}")
        return False

# ─── إرسال التليجرام ─────────────────────────────────────────
def send_telegram(signal_data):
    symbol  = signal_data["symbol"].replace(".AD", "")
    message = (
        f"🇦🇪 إشارة ADX — {symbol}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📈 نوع الإشارة: شراء\n"
        f"💰 سعر الدخول:  {signal_data['entry']} AED\n"
        f"🎯 الهدف:        {signal_data['target']} AED\n"
        f"🛑 وقف الخسارة: {signal_data['stop']} AED\n"
        f"📊 RSI:          {signal_data['rsi']}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M')} (UAE)"
    )
    try:
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message},
            timeout=10
        )
        return res.status_code == 200
    except Exception as e:
        print(f"[send_telegram] {e}")
        return False

# ─── الدالة الرئيسية ──────────────────────────────────────────
def run_bot():
    now = datetime.now(TIMEZONE)
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] UAE Bot started")

    if not is_market_open():
        print("السوق مغلق")
        return {"status": "market_closed"}

    results = []
    for symbol in SYMBOLS:
        try:
            if already_sent_today(symbol):
                print(f"{symbol}: تم الإرسال مسبقاً اليوم")
                continue

            signal = generate_signal(symbol)
            if signal is None:
                print(f"{symbol}: لا توجد إشارة")
                continue

            saved = save_signal(signal)
            sent  = send_telegram(signal)
            print(f"{symbol}: saved={saved} sent={sent}")
            results.append(signal)

        except Exception as e:
            print(f"[run_bot] {symbol}: {e}")

    print(f"انتهى — {len(results)} إشارة")
    return {"status": "done", "signals": len(results)}

# ─── تشغيل مباشر ─────────────────────────────────────────────
if __name__ == "__main__":
    run_bot()

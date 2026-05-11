"""
========================================================
  UAE ADX SMART BOT v1.0 — نسخة كاملة
========================================================
مبني على نفس هيكل EGX Bot v4.0 بالظبط:
  ✅ نظام Score 0-100 — 3 درجات
  ✅ RSI Divergence
  ✅ Volume Surge 3x
  ✅ Bollinger Squeeze
  ✅ دعم ومقاومة ديناميكية
  ✅ Ichimoku Cloud
  ✅ OBV — تراكم مؤسسي
  ✅ ADX — قوة الترند
  ✅ MACD + Stochastic + VWAP
  ✅ أنماط الشموع الـ 6
  ✅ Multi-Timeframe
  ✅ تحليل القطاعات
  ✅ أخبار UAE
  ✅ تقارير أسبوعية وشهرية
  ✅ Position Sizing
  ✅ ATR للـ SL و TP1 و TP2
========================================================
"""

import pandas as pd
import numpy as np
import ta
import requests
import os
import feedparser
from datetime import datetime, timedelta, timezone

DUBAI_TZ = timezone(timedelta(hours=4))

def now_dubai():
    return datetime.now(DUBAI_TZ).replace(tzinfo=None)

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.environ.get("UAE_TELEGRAM_TOKEN", "8206640637:AAE8rBc5H1iepG_tFWsb7epL_JGB2nbqRmI")
CHAT_ID        = os.environ.get("UAE_CHAT_ID",        "1758789551")
RENDER_API_URL = os.environ.get("UAE_API_URL",        "https://uae-api.onrender.com")

ACCOUNT_SIZE   = 100_000
RISK_PER_TRADE = 0.02

MARKET_OPEN_HOUR  = 10
MARKET_CLOSE_HOUR = 14
MARKET_CLOSE_MIN  = 0
START_DELAY_MIN   = 30
STOP_BEFORE_CLOSE = 60

SCORE_STRONG  = 75
SCORE_GOOD    = 55
SCORE_MINIMUM = 40

LOG_FILE = "uae_signals_log.xlsx"

SYMBOLS = [
    # بنوك إسلامية
    "ADIB.AD",        # Abu Dhabi Islamic Bank
    "DIB.AD",         # Dubai Islamic Bank
    "SIB.AD",         # Sharjah Islamic Bank
    "AJIB.AD",        # Ajman Bank

    # عقارات
    "ALDAR.AD",       # Aldar Properties
    "ESHRAQ.AD",      # Eshraq Investments

    # طاقة وبتروكيماويات
    "TAQA.AD",        # Abu Dhabi National Energy
    "FERTIGLOBE.AD",  # Fertiglobe
    "ADNOCGAS.AD",    # ADNOC Gas
    "ADNOCDRILL.AD",  # ADNOC Drilling
    "BOROUGE.AD",     # Borouge

    # اتصالات
    "ETISALAT.AD",    # e& (اتصالات)

    # تأمين إسلامي
    "METHAQ.AD",      # Methaq Takaful
    "TKFL.AD",        # Al Wathba Insurance
    "SALAMA.AD",      # Islamic Arab Insurance

    # غذاء ومطاعم
    "AGTHIA.AD",      # Agthia Group
    "FOODCO.AD",      # Foodco Holding
    "AMERICANA.AD",   # Americana Restaurants

    # نقل وخدمات
    "SALIK.AD",       # Salik (رسوم المرور)

    # استثمار ومتنوع
    "IHC.AD",         # International Holding Company
    "MULTIPLY.AD",    # Multiply Group
    "GFH.AD",         # Gulf Finance House

    # صناعة
    "GPBM.AD",        # Gulf Pharmaceutical
    "PIHC.AD",        # Primus International Holding
    "NPCC.AD",        # National Petroleum Construction
]

SECTORS = {
    "بنوك إسلامية": ["ADIB.AD", "DIB.AD", "SIB.AD", "AJIB.AD"],
    "عقارات":       ["ALDAR.AD", "ESHRAQ.AD"],
    "طاقة":         ["TAQA.AD", "FERTIGLOBE.AD", "ADNOCGAS.AD", "ADNOCDRILL.AD", "BOROUGE.AD"],
    "اتصالات":      ["ETISALAT.AD"],
    "تأمين":        ["METHAQ.AD", "TKFL.AD", "SALAMA.AD"],
    "غذاء":         ["AGTHIA.AD", "FOODCO.AD", "AMERICANA.AD"],
    "نقل":          ["SALIK.AD"],
    "استثمار":      ["IHC.AD", "MULTIPLY.AD", "GFH.AD"],
    "صناعة":        ["GPBM.AD", "PIHC.AD", "NPCC.AD"],
}

NEWS_CACHE    = {}
SECTOR_CACHE  = {}

# =========================
# TELEGRAM
# =========================

def send(msg, parse_mode="HTML"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": parse_mode}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

# =========================
# DATA
# =========================

TWELVEDATA_KEY = os.environ.get("TWELVEDATA_API_KEY", "77d24f06c4c54fb583047bed85ef59c8")

def get_data(symbol, interval="1day", bars=300):
    ticker = symbol.replace(".AD", "")
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol":     ticker,
        "exchange":   "XADS",
        "interval":   interval,
        "outputsize": bars,
        "apikey":     TWELVEDATA_KEY,
        "format":     "JSON",
    }
    try:
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        if data.get("status") == "error" or "values" not in data:
            print(f"TwelveData error {ticker}: {data.get('message','')}")
            return None
        values = data["values"]
        df = pd.DataFrame(values)
        df = df.rename(columns={
            "datetime": "date",
            "open":     "open",
            "high":     "high",
            "low":      "low",
            "close":    "close",
            "volume":   "volume"
        })
        for col in ["open","high","low","close","volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        if len(df) < 20:
            print(f"TwelveData: بيانات قليلة {ticker}: {len(df)}")
            return None
        print(f"TwelveData OK: {ticker} — {len(df)} يوم")
        return df
    except Exception as e:
        print(f"get_data {ticker}: {e}")
        return None

# =========================
# VWAP
# =========================

def calc_vwap(df):
    if "volume" not in df.columns:
        return df
    df = df.copy()
    try:
        date_col   = pd.to_datetime(df.get("date", pd.Series(df.index))).dt.date
        df["_date"] = date_col
        df["_tp"]   = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"]  = (df.groupby("_date")
                         .apply(lambda g: (g["_tp"] * g["volume"]).cumsum() / g["volume"].cumsum())
                         .reset_index(level=0, drop=True))
    except Exception:
        df["vwap"] = df["close"].rolling(20).mean()
    return df

# =========================
# ATR
# =========================

def calc_atr_levels(df, price):
    atr = float(ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=14)
                  .average_true_range().iloc[-1])
    return price - 1.5*atr, price + 2.0*atr, price + 3.5*atr, atr

# =========================
# RSI Divergence
# =========================

def rsi_divergence(df):
    close = df["close"]
    rsi   = ta.momentum.rsi(close, window=14)
    score, reasons = 0, []
    if len(df) < 20:
        return 0, []
    recent_close = close.iloc[-20:]
    recent_rsi   = rsi.iloc[-20:]
    price_low_1  = recent_close.iloc[:10].min()
    price_low_2  = recent_close.iloc[10:].min()
    rsi_low_1    = recent_rsi.iloc[:10].min()
    rsi_low_2    = recent_rsi.iloc[10:].min()
    if price_low_2 < price_low_1 and rsi_low_2 > rsi_low_1:
        score += 30
        reasons.append("🔀 RSI Divergence صعودي — انعكاس قوي جداً")
    return score, reasons

# =========================
# Volume Surge
# =========================

def volume_surge(df):
    if "volume" not in df.columns:
        return 0, []
    vol      = df["volume"]
    avg_vol  = vol.rolling(20).mean()
    last_vol = vol.iloc[-1]
    last_avg = avg_vol.iloc[-1]
    if last_avg == 0 or pd.isna(last_avg):
        return 0, []
    ratio = last_vol / last_avg
    score, reasons = 0, []
    if ratio >= 5:
        score += 35
        reasons.append(f"🚨 حجم ضخم جداً {ratio:.1f}x — مؤسسات تشتري")
    elif ratio >= 3:
        score += 25
        reasons.append(f"📈 Volume Surge {ratio:.1f}x — اهتمام مؤسسي")
    elif ratio >= 2:
        score += 12
        reasons.append(f"📊 حجم مرتفع {ratio:.1f}x فوق المتوسط")
    return score, reasons

# =========================
# Bollinger Squeeze
# =========================

def bollinger_squeeze(df):
    close = df["close"]
    bb    = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    width = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg() * 100
    current_width = width.iloc[-1]
    avg_width     = width.rolling(50).mean().iloc[-1]
    score, reasons = 0, []
    if pd.isna(avg_width):
        return 0, []
    if current_width < avg_width * 0.5:
        score += 20
        reasons.append("💥 Bollinger Squeeze شديد — انفجار وشيك")
    elif current_width < avg_width * 0.7:
        score += 10
        reasons.append("⚡ Bollinger ضيق — ترقّب حركة قوية")
    if close.iloc[-1] > bb.bollinger_mavg().iloc[-1]:
        score += 5
    return score, reasons

# =========================
# Support & Resistance
# =========================

def support_resistance(df, price):
    recent_highs = df["high"].iloc[-50:].nlargest(5).values
    recent_lows  = df["low"].iloc[-50:].nsmallest(5).values
    resistance   = min([h for h in recent_highs if h > price], default=price * 1.05)
    support      = max([l for l in recent_lows  if l < price], default=price * 0.95)
    dist_to_resistance = (resistance - price) / price * 100
    dist_to_support    = (price - support)    / price * 100
    score, reasons = 0, []
    if dist_to_support < 3 and dist_to_resistance > 5:
        score += 15
        reasons.append(f"📌 السعر فوق دعم قريب — مقاومة بعيدة {dist_to_resistance:.1f}%")
    elif dist_to_resistance < 2:
        score -= 15
        reasons.append(f"🚧 السعر قريب من المقاومة ({dist_to_resistance:.1f}%) — خطر")
    return score, reasons, support, resistance

# =========================
# Ichimoku
# =========================

def calc_ichimoku(df):
    h, l   = df["high"], df["low"]
    tenkan = (h.rolling(9).max()  + l.rolling(9).min())  / 2
    kijun  = (h.rolling(26).max() + l.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    df = df.copy()
    df["ichi_tenkan"] = tenkan
    df["ichi_kijun"]  = kijun
    df["ichi_span_a"] = span_a
    df["ichi_span_b"] = span_b
    return df

def ichimoku_signal(df):
    last   = df.iloc[-1]
    score, reasons = 0, []
    close  = last["close"]
    span_a = last.get("ichi_span_a", np.nan)
    span_b = last.get("ichi_span_b", np.nan)
    tenkan = last.get("ichi_tenkan", np.nan)
    kijun  = last.get("ichi_kijun",  np.nan)
    if pd.isna(span_a) or pd.isna(span_b):
        return 0, []
    cloud_top = max(span_a, span_b)
    cloud_bot = min(span_a, span_b)
    if close > cloud_top:
        score += 20; reasons.append("☁️ السعر فوق سحابة Ichimoku")
    elif close > cloud_bot:
        score += 8;  reasons.append("☁️ السعر داخل السحابة")
    if not pd.isna(tenkan) and not pd.isna(kijun) and tenkan > kijun:
        score += 10; reasons.append("☁️ Tenkan > Kijun إيجابي")
    return score, reasons

# =========================
# OBV
# =========================

def obv_signal(df):
    obv     = ta.volume.OnBalanceVolumeIndicator(df["close"], df["volume"]).on_balance_volume()
    obv_ema = obv.ewm(span=20).mean()
    score, reasons = 0, []
    if obv.iloc[-1] > obv_ema.iloc[-1] and obv.iloc[-1] > obv.iloc[-5]:
        score += 15; reasons.append("📊 OBV صاعد — تراكم مؤسسي")
    elif obv.iloc[-1] > obv.iloc[-5]:
        score += 7;  reasons.append("📊 OBV في ارتفاع")
    return score, reasons

# =========================
# ADX
# =========================

def adx_signal(df):
    ind  = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
    adx  = ind.adx().iloc[-1]
    dip  = ind.adx_neg().iloc[-1]
    dim  = ind.adx_pos().iloc[-1]
    score, reasons = 0, []
    if adx < 15:
        score -= 20; reasons.append(f"⚠️ ADX={adx:.0f} — سوق جانبي")
    elif adx >= 25 and dim > dip:
        score += 20; reasons.append(f"✅ ADX={adx:.0f} — ترند صاعد قوي")
    elif adx >= 18:
        score += 10; reasons.append(f"✅ ADX={adx:.0f} — ترند يتشكّل")
    return score, reasons, adx

# =========================
# أنماط الشموع
# =========================

def candle_patterns(df):
    score, reasons = 0, []
    if "open" not in df.columns:
        return 0, []
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    i = len(c) - 1
    body       = abs(c[i] - o[i])
    full_range = h[i] - l[i]
    if full_range == 0:
        return 0, []
    lower_wick = min(o[i], c[i]) - l[i]
    upper_wick = h[i] - max(o[i], c[i])
    if lower_wick >= 2*body and upper_wick <= 0.2*full_range and c[i] > o[i]:
        score += 20; reasons.append("🔨 Hammer — انعكاس صعودي")
    if i > 0 and c[i-1] < o[i-1] and c[i] > o[i] and o[i] < c[i-1] and c[i] > o[i-1]:
        score += 25; reasons.append("🕯️ Bullish Engulfing — تحوّل قوي")
    if (i > 1 and c[i-2] < o[i-2] and
            abs(c[i-1]-o[i-1]) < 0.3*abs(c[i-2]-o[i-2]) and
            c[i] > o[i] and c[i] > (o[i-2]+c[i-2])/2):
        score += 25; reasons.append("⭐ Morning Star — انعكاس قوي جداً")
    if (i > 0 and c[i-1] < o[i-1] and c[i] > o[i] and
            o[i] < l[i-1] and c[i] > (o[i-1]+c[i-1])/2):
        score += 18; reasons.append("📍 Piercing Line — اختراق صعودي")
    if (i > 1 and c[i] > o[i] and c[i-1] > o[i-1] and c[i-2] > o[i-2] and
            c[i] > c[i-1] > c[i-2] and o[i] > o[i-1] and o[i-1] > o[i-2]):
        score += 20; reasons.append("💪 Three White Soldiers — زخم صاعد قوي")
    if upper_wick >= 2*body and lower_wick <= 0.2*full_range and c[i] > o[i]:
        score += 12; reasons.append("🔁 Inverted Hammer — انعكاس محتمل")
    if body / full_range < 0.1:
        reasons.append("〰️ Doji — تردد، انتبه")
    return score, reasons

# =========================
# Multi-Timeframe
# =========================

def multi_timeframe_confirm(symbol):
    ticker = symbol.replace(".AD", "")
    try:
        res = requests.get("https://api.twelvedata.com/time_series", params={
            "symbol": ticker, "exchange": "XADS",
            "interval": "1h", "outputsize": 60,
            "apikey": TWELVEDATA_KEY, "format": "JSON"
        }, timeout=15)
        data = res.json()
        if data.get("status") == "error" or "values" not in data:
            return True, ["⚪ 1H: بيانات غير متاحة — تم التجاوز"]
        df_h = pd.DataFrame(data["values"])
        df_h["close"] = pd.to_numeric(df_h["close"], errors="coerce")
        df_h = df_h.sort_values("datetime").reset_index(drop=True)
        if len(df_h) < 20:
            return True, ["⚪ 1H: بيانات قليلة — تم التجاوز"]
        ema20 = ta.trend.ema_indicator(df_h["close"], window=20).iloc[-1]
        ema50 = ta.trend.ema_indicator(df_h["close"], window=50).iloc[-1]
        rsi1h = ta.momentum.rsi(df_h["close"], window=14).iloc[-1]
        if ema20 < ema50 * 0.98 and rsi1h < 40:
            return False, ["❌ 1H هابط بقوة — تجنّب"]
        if ema20 > ema50:
            return True, ["✅ 1H مؤكد — ترند صاعد"]
        return True, ["⚪ 1H محايد — مقبول"]
    except Exception:
        return True, ["⚪ 1H: تعذّر التحقق — تم التجاوز"]

# =========================
# أخبار UAE
# =========================

def fetch_uae_news():
    feeds = [
        # Reuters عربي
        "https://feeds.reuters.com/reuters/businessNews",
        "https://ar.reuters.com/rssFeed/businessNews",
        # Bloomberg الشرق
        "https://feeds.bloomberg.com/markets/news.rss",
        # Zawya
        "https://www.zawya.com/rss/ae/",
        # Mubasher
        "https://mubasher.info/rss/ae",
    ]
    items = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:15]:
                items.append({
                    "title":   e.get("title", ""),
                    "summary": e.get("summary", ""),
                    "source":  url.split("/")[2]
                })
        except Exception:
            pass

    # ADX الموقع الرسمي
    try:
        res = requests.get(
            "https://www.adx.ae/ar/news",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if res.status_code == 200:
            from html.parser import HTMLParser
            class NewsParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.titles = []
                    self.in_title = False
                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    if "news-title" in attrs_dict.get("class", ""):
                        self.in_title = True
                def handle_data(self, data):
                    if self.in_title and data.strip():
                        self.titles.append(data.strip())
                        self.in_title = False
            parser = NewsParser()
            parser.feed(res.text)
            for t in parser.titles[:10]:
                items.append({"title": t, "summary": "", "source": "adx.ae"})
    except Exception:
        pass

    NEWS_CACHE["items"] = items
    NEWS_CACHE["time"]  = now_dubai()
    print(f"أخبار: {len(items)} خبر من {len(feeds)+1} مصدر")

def news_sentiment(symbol):
    ticker = symbol.replace(".AD", "").upper()
    items  = NEWS_CACHE.get("items", [])
    neg_kw = ["توقف", "خسارة", "غرامة", "تحقيق", "انخفاض", "هبوط"]
    pos_kw = ["أرباح", "توزيعات", "نمو", "عقد", "شراكة", "ارتفاع", "توسع"]
    score, reasons = 0, []
    for item in items:
        text = (item["title"] + item["summary"]).upper()
        if ticker in text:
            for kw in neg_kw:
                if kw in text:
                    score -= 25; reasons.append(f"📰 خبر سلبي: {item['title'][:40]}")
            for kw in pos_kw:
                if kw in text:
                    score += 15; reasons.append(f"📰 خبر إيجابي: {item['title'][:40]}")
    return score, reasons

# =========================
# النفط والماكرو
# =========================

def oil_macro_signal():
    import yfinance as yf
    score, reasons = 0, []

    # سعر النفط
    try:
        oil = yf.download("CL=F", period="5d", interval="1d", progress=False, auto_adjust=True)
        if oil is not None and len(oil) >= 2:
            oil_price = float(oil["Close"].iloc[-1])
            oil_prev  = float(oil["Close"].iloc[-2])
            oil_change = (oil_price - oil_prev) / oil_prev * 100

            if oil_price >= 85:
                score += 15
                reasons.append(f"🛢️ النفط قوي {oil_price:.1f}$ (+{oil_change:.1f}%)")
            elif oil_price >= 70:
                score += 0
                reasons.append(f"🛢️ النفط محايد {oil_price:.1f}$")
            elif oil_price >= 60:
                score -= 20
                reasons.append(f"🛢️ النفط ضعيف {oil_price:.1f}$ — ضغط على السوق")
            else:
                score -= 35
                reasons.append(f"🛢️ النفط منهار {oil_price:.1f}$ — خطر كبير")
    except Exception as e:
        print(f"oil_macro_signal oil: {e}")

    # الفائدة الأمريكية — 10Y Treasury كمؤشر
    try:
        tnx = yf.download("^TNX", period="10d", interval="1d", progress=False, auto_adjust=True)
        if tnx is not None and len(tnx) >= 5:
            rate_now  = float(tnx["Close"].iloc[-1])
            rate_prev = float(tnx["Close"].iloc[-5])
            if rate_now < rate_prev - 0.1:
                score += 10
                reasons.append(f"🏦 الفائدة تنخفض {rate_now:.2f}% — إيجابي للأسهم")
            elif rate_now > rate_prev + 0.1:
                score -= 10
                reasons.append(f"🏦 الفائدة ترتفع {rate_now:.2f}% — ضغط على الأسهم")
    except Exception as e:
        print(f"oil_macro_signal rate: {e}")

    return score, reasons

# =========================
# قوة القطاع
# =========================

def calc_sector_strength():
    for sector, syms in SECTORS.items():
        perfs = []
        for s in syms:
            try:
                ticker = s.replace(".AD", "")
                res = requests.get("https://api.twelvedata.com/time_series", params={
                    "symbol": ticker, "exchange": "XADS",
                    "interval": "1day", "outputsize": 3,
                    "apikey": TWELVEDATA_KEY, "format": "JSON"
                }, timeout=10)
                data = res.json()
                if "values" in data and len(data["values"]) >= 2:
                    c1 = float(data["values"][0]["close"])
                    c2 = float(data["values"][1]["close"])
                    perfs.append((c1 - c2) / c2 * 100)
            except Exception:
                pass
        SECTOR_CACHE[sector] = np.mean(perfs) if perfs else 0

def get_sector(symbol):
    for sector, syms in SECTORS.items():
        if symbol in syms:
            return sector
    return "متنوع"

def sector_signal(symbol):
    perf = SECTOR_CACHE.get(get_sector(symbol), 0)
    score, reasons = 0, []
    if perf > 1:
        score += 15; reasons.append(f"🏭 القطاع قوي (+{perf:.1f}%)")
    elif perf < -1.5:
        score -= 15; reasons.append(f"🏭 القطاع ضعيف ({perf:.1f}%)")
    return score, reasons

# =========================
# حجم المركز
# =========================

def calc_position_size(price, sl):
    risk_amt       = ACCOUNT_SIZE * RISK_PER_TRADE
    risk_per_share = price - sl
    if risk_per_share <= 0:
        return 0, 0
    shares = int(risk_amt / risk_per_share)
    return shares, shares * price

# =========================
# محرك التحليل
# =========================

def analyze(symbol):
    df = get_data(symbol)
    if df is None or len(df) < 80:
        return None

    if "volume" not in df.columns:
        df["volume"] = 0

    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    df["ema20"]  = ta.trend.ema_indicator(close, window=20)
    df["ema50"]  = ta.trend.ema_indicator(close, window=50)
    df["ema200"] = ta.trend.ema_indicator(close, window=200)
    df["rsi"]    = ta.momentum.rsi(close, window=14)

    macd_obj          = ta.trend.MACD(close)
    df["macd_hist"]   = macd_obj.macd_diff()

    bb             = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["bb_mid"]   = bb.bollinger_mavg()

    stoch         = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    df = calc_vwap(df)
    df = calc_ichimoku(df)
    df.dropna(subset=["ema20", "ema50", "rsi"], inplace=True)

    if len(df) < 10:
        return None

    last  = df.iloc[-1]
    prev  = df.iloc[-2]
    score   = 0
    reasons = []

    # 1. EMA Trend
    if last["ema20"] > last["ema50"] > last["ema200"]:
        score += 25; reasons.append("✅ EMA20>50>200 ترند قوي")
    elif last["ema20"] > last["ema50"]:
        score += 12; reasons.append("⚠️ EMA20>50 جزئي")

    # 2. RSI
    rsi = last["rsi"]
    if 45 < rsi < 68:
        score += 15; reasons.append(f"✅ RSI={rsi:.0f} مثالي")
    elif 68 <= rsi < 75:
        score += 5
    elif rsi >= 75:
        score -= 15; reasons.append(f"❌ RSI={rsi:.0f} تشبع")

    # 3. MACD
    if last["macd_hist"] > 0 and prev["macd_hist"] <= 0:
        score += 15; reasons.append("✅ MACD تقاطع صاعد الآن")
    elif last["macd_hist"] > 0:
        score += 7

    # 4. Bollinger
    if last["close"] > last["bb_mid"] and prev["close"] <= prev["bb_mid"]:
        score += 10; reasons.append("✅ اخترق Bollinger للأعلى")
    elif last["close"] > last["bb_mid"]:
        score += 4

    # 5. Stochastic
    if last["stoch_k"] > last["stoch_d"] and prev["stoch_k"] <= prev["stoch_d"] and last["stoch_k"] < 80:
        score += 10; reasons.append("✅ Stochastic تقاطع صاعد")

    # 6. VWAP
    if "vwap" in df.columns and not pd.isna(last.get("vwap", np.nan)):
        if last["close"] > last["vwap"]:
            score += 10; reasons.append("✅ السعر فوق VWAP")
        else:
            score -= 8; reasons.append("❌ السعر تحت VWAP")

    # 7. Ichimoku
    ich_s, ich_r = ichimoku_signal(df)
    score += ich_s; reasons += ich_r

    # 8. OBV
    if df["volume"].sum() > 0:
        obv_s, obv_r = obv_signal(df)
        score += obv_s; reasons += obv_r

    # 9. ADX
    adx_s, adx_r, adx_val = adx_signal(df)
    score += adx_s; reasons += adx_r

    # 10. أنماط الشموع
    cdl_s, cdl_r = candle_patterns(df)
    score += cdl_s; reasons += cdl_r

    # 11. RSI Divergence
    div_s, div_r = rsi_divergence(df)
    score += div_s; reasons += div_r

    # 12. Volume Surge
    vs_s, vs_r = volume_surge(df)
    score += vs_s; reasons += vs_r

    # 13. Bollinger Squeeze
    bsq_s, bsq_r = bollinger_squeeze(df)
    score += bsq_s; reasons += bsq_r

    # 14. أخبار
    news_s, news_r = news_sentiment(symbol)
    score += news_s; reasons += news_r

    # 15. قطاع
    sec_s, sec_r = sector_signal(symbol)
    score += sec_s; reasons += sec_r

    # 16. النفط والماكرو
    oil_s, oil_r = oil_macro_signal()
    score += oil_s; reasons += oil_r

    # 17. سيولة الأجانب
    fi_s, fi_r = foreign_investor_signal()
    score += fi_s; reasons += fi_r

    # فلاتر رفض
    dist = (last["close"] - last["ema50"]) / last["ema50"] * 100
    if dist > 10:
        score -= 20; reasons.append(f"❌ ممتد {dist:.1f}% عن EMA50")
    if "open" in df.columns:
        body_pct = (last["close"] - last["open"]) / last["open"] * 100
        if body_pct < -3:
            score -= 15; reasons.append(f"❌ شمعة هبوطية ({body_pct:.1f}%)")

    if score < SCORE_MINIMUM:
        return None

    # Multi-Timeframe
    tf_ok, tf_r = multi_timeframe_confirm(symbol)
    reasons += tf_r
    if not tf_ok:
        return None

    price = float(last["close"])
    sl, tp1, tp2, atr_val = calc_atr_levels(df, price)
    sl = max(sl, price * 0.93)

    risk   = price - sl
    reward = tp1 - price
    rr     = reward / risk if risk > 0 else 0

    if rr < 1.2:
        return None

    sr_s, sr_r, support, resistance = support_resistance(df, price)
    score += sr_s; reasons += sr_r

    shares, total_inv = calc_position_size(price, sl)

    if score >= SCORE_STRONG:
        grade = "🔥 قوية جداً"
    elif score >= SCORE_GOOD:
        grade = "✅ قوية"
    else:
        grade = "⚠️ متوسطة"

    return {
        "symbol":     symbol,
        "score":      score,
        "grade":      grade,
        "price":      price,
        "entry":      price,
        "sl":         sl,
        "tp1":        tp1,
        "tp2":        tp2,
        "rr":         rr,
        "rsi":        rsi,
        "atr":        atr_val,
        "adx":        adx_val,
        "support":    support,
        "resistance": resistance,
        "shares":     shares,
        "total_inv":  total_inv,
        "reasons":    reasons,
    }

# =========================
# رسالة التليجرام
# =========================

def format_signal(s):
    top     = "\n".join(s["reasons"][:5])
    pct_tp1 = (s["tp1"] - s["entry"]) / s["entry"] * 100
    pct_tp2 = (s["tp2"] - s["entry"]) / s["entry"] * 100
    pct_sl  = (s["entry"] - s["sl"])  / s["entry"] * 100
    ticker  = s["symbol"].replace(".AD", "")
    pos     = f"📦 {s['shares']} سهم | {s['total_inv']:,.0f} د.إ" if s["shares"] > 0 else ""
    return f"""
{s['grade']} <b>إشارة شراء — {ticker}</b>
━━━━━━━━━━━━━━━━━━━━━
💰 سعر الدخول:   <b>{s['entry']:.4f} د.إ</b>
🎯 الهدف الأول:  {s['tp1']:.4f} د.إ  <b>(+{pct_tp1:.1f}%)</b>
🎯 الهدف الثاني: {s['tp2']:.4f} د.إ  <b>(+{pct_tp2:.1f}%)</b>
🛑 وقف الخسارة:  {s['sl']:.4f} د.إ  (-{pct_sl:.1f}%)
⚖️ R/R: {s['rr']:.1f}x  |  🧠 Score: {s['score']}
━━━━━━━━━━━━━━━━━━━━━
📌 <b>أسباب الدخول:</b>
{top}
━━━━━━━━━━━━━━━━━━━━━
📉 RSI: {s['rsi']:.0f}  |  ADX: {s['adx']:.0f}
📌 دعم: {s['support']:.4f}  |  مقاومة: {s['resistance']:.4f}
{pos}
━━━━━━━━━━━━━━━━━━━━━
🇦🇪 ADX  |  ⏰ {now_dubai().strftime('%H:%M')} (UAE)
⚠️ <i>للمعلومات فقط — ليس توصية</i>
"""

# =========================
# حفظ الإشارة في API
# =========================

def send_to_api(s):
    try:
        import psycopg2
        conn = get_db_conn()
        if not conn:
            print("send_to_api: no DB connection")
            return
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO uae_signals
                (symbol, signal, entry, stop, target,
                 tp1, tp2, grade, score, rr,
                 rsi, adx, support, resistance,
                 market, date, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            s["symbol"], "BUY",
            s["entry"], s["sl"], s["tp1"],
            s["tp1"], s["tp2"],
            s["grade"], s["score"], round(s["rr"], 2),
            round(s["rsi"], 1), round(s["adx"], 1),
            s["support"], s["resistance"],
            "UAE",
            now_dubai().strftime("%Y-%m-%d"),
            now_dubai().isoformat()
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"DB saved: {s['symbol']}")
    except Exception as e:
        print(f"send_to_api: {e}")

def log_signal(s):
    row = {
        "التاريخ":  now_dubai().strftime("%Y-%m-%d %H:%M"),
        "السهم":    s["symbol"],
        "الدرجة":   s["grade"],
        "Score":    s["score"],
        "السعر":    s["price"],
        "TP1":      s["tp1"],
        "TP2":      s["tp2"],
        "SL":       s["sl"],
        "R/R":      s["rr"],
        "دعم":      s.get("support", 0),
        "مقاومة":   s.get("resistance", 0),
        "النتيجة":  "",
    }
    try:
        if os.path.exists(LOG_FILE):
            df_log = pd.concat([pd.read_excel(LOG_FILE), pd.DataFrame([row])], ignore_index=True)
        else:
            df_log = pd.DataFrame([row])
        df_log.to_excel(LOG_FILE, index=False)
    except Exception as e:
        print(f"log_signal: {e}")

# =========================
# التقارير
# =========================

def fetch_signals_period(period="week"):
    import psycopg2.extras
    try:
        conn = get_db_conn()
        if not conn:
            return []
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        now  = now_dubai()
        if period == "week":
            from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            cur.execute("SELECT * FROM uae_signals WHERE date >= %s ORDER BY created_at DESC", (from_date,))
        else:
            month_start = now.strftime("%Y-%m-01")
            cur.execute("SELECT * FROM uae_signals WHERE date >= %s ORDER BY created_at DESC", (month_start,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"fetch_signals_period: {e}")
        return []

def send_weekly_report():
    signals = fetch_signals_period("week")
    total   = len(signals)
    now     = now_dubai()
    if total == 0:
        send("📊 <b>تقرير الأسبوع — UAE ADX</b>\n━━━━━━━━━━━━━━━━━━━━━\nلا توجد إشارات هذا الأسبوع.")
        return
    strong   = len([s for s in signals if "قوية جداً" in str(s.get("grade", ""))])
    good     = len([s for s in signals if str(s.get("grade", "")) == "✅ قوية"])
    moderate = total - strong - good
    lines    = [f"• {str(s.get('symbol','')).replace('.AD','')} | Score: {s.get('score',0)} | {s.get('grade','')}"
                for s in signals]
    details  = "\n".join(lines)
    msg = f"""
📊 <b>تقرير الأسبوع — UAE ADX</b>
━━━━━━━━━━━━━━━━━━━━━
{details}
━━━━━━━━━━━━━━━━━━━━━
📈 إجمالي الإشارات: {total}
🔥 قوية جداً: {strong}  |  ✅ قوية: {good}  |  ⚠️ متوسطة: {moderate}
━━━━━━━━━━━━━━━━━━━━━
"""
    send(msg)

def send_monthly_report():
    signals = fetch_signals_period("month")
    now     = now_dubai()
    total   = len(signals)
    if total == 0:
        send(f"📅 <b>تقرير {now.strftime('%B %Y')} — UAE ADX</b>\n━━━━━━━━━━━━━━━━━━━━━\nلا توجد إشارات هذا الشهر.")
        return
    strong   = len([s for s in signals if "قوية جداً" in str(s.get("grade", ""))])
    good     = len([s for s in signals if str(s.get("grade", "")) == "✅ قوية"])
    moderate = total - strong - good
    msg = f"""
📅 <b>تقرير {now.strftime('%B %Y')} — UAE ADX</b>
━━━━━━━━━━━━━━━━━━━━━
📈 إجمالي الإشارات: {total}
🔥 قوية جداً: {strong}
✅ قوية: {good}
⚠️ متوسطة: {moderate}
━━━━━━━━━━━━━━━━━━━━━
"""
    send(msg)

# =========================
# التوقيت
# =========================

def is_trading_time():
    now = now_dubai()
    if now.weekday() in [4, 5]:
        return False
    cur   = now.hour * 60 + now.minute
    start = MARKET_OPEN_HOUR  * 60 + START_DELAY_MIN
    end   = MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MIN - STOP_BEFORE_CLOSE
    return start <= cur <= end

# =========================
# منع التكرار
# =========================

def get_db_conn():
    import psycopg2
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return None
    return psycopg2.connect(db_url, sslmode="require")

def already_sent_today(symbol):
    try:
        today = now_dubai().strftime("%Y-%m-%d")
        conn  = get_db_conn()
        if not conn:
            return False
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM uae_signals WHERE symbol = %s AND date = %s",
            (symbol, today)
        )
        exists = cur.fetchone() is not None
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        print(f"already_sent_today: {e}")
        return False

# =========================
# سيولة الأجانب — ADX
# =========================

def foreign_investor_signal():
    score, reasons = 0, []
    try:
        res = requests.get(
            "https://www.adx.ae/ar/market-data/foreign-investors",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        if res.status_code != 200:
            return 0, []

        text = res.text

        # ابحث عن صافي الأجانب في الصفحة
        import re
        patterns = [
            r'صافي[^0-9\-]*([+\-]?\d[\d,\.]+)',
            r'net[^0-9\-]*([+\-]?\d[\d,\.]+)',
            r'foreign[^0-9\-]*([+\-]?\d[\d,\.]+)',
        ]

        net_value = None
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(",", "")
                try:
                    net_value = float(raw)
                    break
                except Exception:
                    pass

        if net_value is not None:
            if net_value >= 50_000_000:
                score += 20
                reasons.append(f"🌍 أجانب يشترون بقوة: +{net_value/1e6:.0f}M AED")
            elif net_value >= 10_000_000:
                score += 10
                reasons.append(f"🌍 أجانب مشترون: +{net_value/1e6:.0f}M AED")
            elif net_value <= -50_000_000:
                score -= 25
                reasons.append(f"🌍 أجانب يبيعون بقوة: {net_value/1e6:.0f}M AED")
            elif net_value <= -10_000_000:
                score -= 15
                reasons.append(f"🌍 أجانب بائعون: {net_value/1e6:.0f}M AED")
        else:
            print("foreign_investor_signal: لم يتم العثور على البيانات")

    except Exception as e:
        print(f"foreign_investor_signal: {e}")

    return score, reasons

# =========================
# تتبع الإشارات المفتوحة
# =========================

def track_open_signals():
    import psycopg2.extras
    try:
        conn = get_db_conn()
        if not conn:
            return
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM uae_signals WHERE status = 'open' OR status IS NULL")
        signals = cur.fetchall()
        cur.close()
        if not signals:
            conn.close()
            return
        print(f"تتبع {len(signals)} إشارة مفتوحة...")
        for s in signals:
            symbol = s.get("symbol")
            sig_id = s.get("id")
            tp1    = float(s.get("tp1") or 0)
            tp2    = float(s.get("tp2") or 0)
            sl     = float(s.get("stop") or 0)
            entry  = float(s.get("entry") or 0)
            if not symbol or not entry:
                continue
            try:
                ticker = symbol.replace(".AD", "")
                res = requests.get("https://api.twelvedata.com/time_series", params={
                    "symbol": ticker, "exchange": "XADS",
                    "interval": "1day", "outputsize": 3,
                    "apikey": TWELVEDATA_KEY, "format": "JSON"
                }, timeout=10)
                data = res.json()
                if "values" not in data:
                    continue
                high = float(data["values"][0]["high"])
                low  = float(data["values"][0]["low"])
                hit_tp2 = tp2 > 0 and high >= tp2
                hit_tp1 = tp1 > 0 and high >= tp1
                hit_sl  = sl  > 0 and low  <= sl
                if not hit_tp1 and not hit_sl:
                    continue
                if hit_tp2:
                    status  = "tp2_hit"
                    pnl_pct = (tp2 - entry) / entry * 100
                elif hit_tp1:
                    status  = "tp1_hit"
                    pnl_pct = (tp1 - entry) / entry * 100
                else:
                    status  = "stopped"
                    pnl_pct = (sl - entry) / entry * 100
                upd = conn.cursor()
                upd.execute("""
                    UPDATE uae_signals
                    SET status=%s, pnl_pct=%s, hit_tp1=%s, hit_tp2=%s,
                        hit_sl=%s, result_date=%s
                    WHERE id=%s
                """, (status, round(pnl_pct,2), hit_tp1, hit_tp2, hit_sl,
                      now_dubai().strftime("%Y-%m-%d"), sig_id))
                conn.commit()
                upd.close()
                emoji = "✅" if pnl_pct > 0 else "❌"
                send(f"{emoji} <b>نتيجة — {ticker}</b>\nالحالة: {status}\nP&L: {pnl_pct:+.1f}%")
                print(f"{symbol}: {status} {pnl_pct:+.1f}%")
            except Exception as e:
                print(f"track {symbol}: {e}")
        conn.close()
    except Exception as e:
        print(f"track_open_signals: {e}")

# =========================
# RUN
# =========================

def run_bot():
    print("=" * 55)
    print("  UAE ADX SMART BOT v1.0")
    print("=" * 55)

    now = now_dubai()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] started")

    tomorrow = now + timedelta(days=1)
    if tomorrow.day == 1 and now.weekday() not in [4, 5]:
        send_monthly_report()

    if now.weekday() == 3 and now.hour >= 15:
        send_weekly_report()
        return {"status": "weekly_report_sent"}

    if not is_trading_time():
        print("السوق مغلق")
        return {"status": "market_closed"}

    print("جلب الأخبار...")
    fetch_uae_news()
    print("حساب القطاعات...")
    calc_sector_strength()
    print("تتبع الإشارات المفتوحة...")
    track_open_signals()

    print("بدأ الفحص...")
    send("🔍 <b>UAE ADX Bot — بدأ الفحص...</b>")

    results = []
    for symbol in SYMBOLS:
        if already_sent_today(symbol):
            print(f"{symbol}: تم الإرسال مسبقاً")
            continue
        print(f"  ← {symbol}", end="\r")
        r = analyze(symbol)
        if r:
            results.append(r)

    results.sort(key=lambda x: x["score"], reverse=True)

    strong   = [r for r in results if r["score"] >= SCORE_STRONG]
    good     = [r for r in results if SCORE_GOOD <= r["score"] < SCORE_STRONG]
    moderate = [r for r in results if SCORE_MINIMUM <= r["score"] < SCORE_GOOD]

    print(f"قوية جداً: {len(strong)} | قوية: {len(good)} | متوسطة: {len(moderate)}")

    if results:
        send(f"📊 <b>نتائج الفحص — UAE ADX</b>\n🔥 قوية جداً: {len(strong)}\n✅ قوية: {len(good)}\n⚠️ متوسطة: {len(moderate)}")
        for r in results:
            send(format_signal(r))
            log_signal(r)
            send_to_api(r)
            print(f"✅ {r['symbol']} | {r['grade']} | Score: {r['score']}")
    else:
        send("📭 <b>UAE ADX</b> — لا توجد فرص قوية الآن.")

    print("اكتمل الفحص.")
    return {"status": "done", "signals": len(results)}


if __name__ == "__main__":
    run_bot()

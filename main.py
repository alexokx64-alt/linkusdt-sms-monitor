import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

OKX = "https://www.okx.com"
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
STATE_FILE = "state.json"

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "LINKUSDT-SMC-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def candles(inst_id, bar, limit=100):
    url = f"{OKX}/api/v5/market/candles?instId={urllib.parse.quote(inst_id)}&bar={bar}&limit={limit}"
    data = get_json(url)
    if data.get("code") != "0":
        raise RuntimeError(f"OKX API error for {inst_id} {bar}: {data.get('msg')}")
    # OKX returns newest first. Convert to oldest first.
    rows = list(reversed(data["data"]))
    result = []
    for r in rows:
        result.append({
            "ts": int(r[0]), "o": float(r[1]), "h": float(r[2]),
            "l": float(r[3]), "c": float(r[4]), "confirm": r[8]
        })
    # Exclude any candle that OKX still marks as unconfirmed.
    return [x for x in result if x["confirm"] == "1"]

def pivots(cs, left=2, right=2):
    highs, lows = [], []
    for i in range(left, len(cs) - right):
        if all(cs[i]["h"] > cs[j]["h"] for j in range(i-left, i)) and all(cs[i]["h"] >= cs[j]["h"] for j in range(i+1, i+right+1)):
            highs.append((i, cs[i]["h"]))
        if all(cs[i]["l"] < cs[j]["l"] for j in range(i-left, i)) and all(cs[i]["l"] <= cs[j]["l"] for j in range(i+1, i+right+1)):
            lows.append((i, cs[i]["l"]))
    return highs, lows

def structure_bias(cs):
    highs, lows = pivots(cs)
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    higher_high = highs[-1][1] > highs[-2][1]
    higher_low = lows[-1][1] > lows[-2][1]
    lower_high = highs[-1][1] < highs[-2][1]
    lower_low = lows[-1][1] < lows[-2][1]
    if higher_high and higher_low:
        return "LONG"
    if lower_high and lower_low:
        return "SHORT"
    return "NEUTRAL"

def detect_setup(link5, link15, btc15):
    # Only use closed candles. Require enough candles for pivots.
    if len(link5) < 25 or len(link15) < 25 or len(btc15) < 25:
        return None
    link_bias = structure_bias(link15[-60:])
    btc_bias = structure_bias(btc15[-60:])
    if link_bias not in ("LONG", "SHORT") or btc_bias != link_bias:
        return None

    # Sweep + MSS proxy on the most recent closed 5m candle:
    # sweep prior local liquidity, then close back through the local structure.
    cur = link5[-1]
    prior = link5[-7:-1]
    if len(prior) < 6:
        return None
    prior_high = max(x["h"] for x in prior)
    prior_low = min(x["l"] for x in prior)
    recent = link5[-13:-1]
    local_low = min(x["l"] for x in recent)
    local_high = max(x["h"] for x in recent)

    if link_bias == "LONG":
        swept = cur["l"] < prior_low and cur["c"] > prior_low
        displacement = cur["c"] > max(x["h"] for x in link5[-4:-1])
        if swept and displacement:
            return ("LONG", link_bias, btc_bias, cur)
    else:
        swept = cur["h"] > prior_high and cur["c"] < prior_high
        displacement = cur["c"] < min(x["l"] for x in link5[-4:-1])
        if swept and displacement:
            return ("SHORT", link_bias, btc_bias, cur)
    return None

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": message}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError("Telegram sendMessage failed")

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def main():
    link5 = candles("LINK-USDT-SWAP", "5m")
    link15 = candles("LINK-USDT-SWAP", "15m")
    btc15 = candles("BTC-USDT-SWAP", "15m")
    setup = detect_setup(link5, link15, btc15)
    if not setup:
        print("No confirmed SMC setup.")
        return

    side, link_bias, btc_bias, candle = setup
    key = f"{side}:{candle['ts']}"
    state = load_state()
    if state.get("last_signal") == key:
        print("This candle's signal was already sent.")
        return

    ts = datetime.fromtimestamp(candle["ts"] / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    emoji = "🟢" if side == "LONG" else "🔴"
    message = (
        f"{emoji} LINKUSDT-SWAP — SMC-кандидат: {side}\n"
        f"Подтверждение: закрытая свеча 5М ({ts})\n"
        f"Структура LINK 15М: {link_bias}\n"
        f"Фильтр BTC 15М: {btc_bias} — совпадает\n"
        f"Условие: локальный сбор ликвидности + импульсное закрытие.\n\n"
        "Это алгоритмический сигнал-кандидат, не гарантия сделки. "
        "Стоп и расчёт позиции не включены. Проверь график перед входом."
    )
    send_telegram(message)
    state["last_signal"] = key
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)
    print("Signal sent:", key)

if __name__ == "__main__":
    main()

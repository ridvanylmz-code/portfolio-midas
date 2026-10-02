import requests
import json
import os
from datetime import datetime
import pytz

# API Keys
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
FINNHUB_KEY = os.getenv('FINNHUB_API_KEY')

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
IST = pytz.timezone('Europe/Istanbul')

def load_portfolio():
    """portfolio.json'dan portföy yükle"""
    try:
        with open('portfolio.json', 'r') as f:
            data = json.load(f)
        return data.get('portfolio', {}), data.get('watchlist', []), data.get('cash_reserve', 0)
    except Exception as e:
        print(f"❌ portfolio.json hatası: {e}")
        return {}, [], 0

def get_finnhub_realtime(ticker):
    """Finnhub'dan real-time veri çek"""
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if 'c' in data and data['c'] > 0:
            return {
                'current_price': round(data.get('c', 0), 2),
                'high': round(data.get('h', 0), 2),
                'low': round(data.get('l', 0), 2),
                'open': round(data.get('o', 0), 2),
                'prev_close': round(data.get('pc', 0), 2),
                'change': round(data.get('d', 0), 2),
                'change_pct': round(data.get('dp', 0), 2),
                'volume': int(data.get('v', 0))
            }
        return None
    except Exception as e:
        print(f"⚠️ {ticker} hatası: {e}")
        return None

def create_realtime_report(portfolio, watchlist, cash_reserve):
    """Real-time portföy raporu oluştur - HTML & Emoji ile renkli"""
    
    report = "<b>📊 PORTFÖY MIDAS - REAL-TIME RAPOR</b>\n"
    report += f"⏰ {datetime.now(IST).strftime('%d.%m.%Y %H:%M')} Istanbul\n"
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    alerts = []
    portfolio_changes = []
    total_value = 0
    total_cost = 0
    
    report += "<b>🎯 AKTİF POZİSYONLAR</b>\n"
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for ticker, ticker_data in portfolio.items():
        # JSON'dan shares ve cost_basis oku
        if isinstance(ticker_data, dict):
            shares = ticker_data.get('shares', 0)
            cost_price = ticker_data.get('cost_basis', 0)
        else:
            shares = ticker_data
            cost_price = 0
        
        data = get_finnhub_realtime(ticker)
        if data:
            current_price = data['current_price']
            change_pct = data['change_pct']
            position_value = current_price * shares
            total_value += position_value
            
            cost_value = cost_price * shares
            total_cost += cost_value
            pl = position_value - cost_value
            pl_pct = (pl / cost_value * 100) if cost_value > 0 else 0
            
            # Renkli Emoji Belirleme
            if change_pct >= 3:
                change_emoji = "🟢📈"
            elif change_pct > 0:
                change_emoji = "📈"
            elif change_pct >= -3:
                change_emoji = "📉"
            else:
                change_emoji = "🔴📉"
            
            if pl > 0:
                pl_emoji = "✅"
            elif pl == 0:
                pl_emoji = "➖"
            else:
                pl_emoji = "❌"
            
            # %5+ Alert
            if abs(change_pct) >= 5.0:
                alerts.append(f"🚨 <b>${ticker}</b>: <b>{change_pct:+.2f}%</b> | Fiyat: <b>${current_price}</b>")
            
            # Rapor Format
            report += f"\n<b>${ticker}</b> {change_emoji} <b>{change_pct:+.2f}%</b>\n"
            report += f"  💰 Fiyat: ${current_price} | Hisse: {shares}\n"
            report += f"  {pl_emoji} P&L: <b>${pl:,.0f}</b> (<b>{pl_pct:+.2f}%</b>)\n"
            report += f"  📊 Gün: ${data['low']} - ${data['high']}\n"
            
            portfolio_changes.append((ticker, change_pct, pl_pct))
    
    # ÖZET BÖLÜMÜ
    report += "\n<b>💰 ÖZET</b>\n"
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    total_portfolio = total_value + cash_reserve
    total_pl = total_value - total_cost
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0
    
    # P&L Rengi
    if total_pl > 0:
        pl_emoji = "✅"
    elif total_pl == 0:
        pl_emoji = "➖"
    else:
        pl_emoji = "❌"
    
    report += f"\n💎 Portföy Değeri: <b>${total_value:,.0f}</b>\n"
    report += f"💵 Nakit Yedek: <b>${cash_reserve:,.0f}</b>\n"
    report += f"📊 <b>Toplam: ${total_portfolio:,.0f}</b>\n\n"
    
    report += f"📈 Maliyet Bazı: <b>${total_cost:,.0f}</b>\n"
    report += f"{pl_emoji} <b>Kar/Zarar: ${total_pl:,.0f}</b> (<b>{total_pl_pct:+.2f}%</b>)\n"
    
    # En İyi / En Kötü
    if portfolio_changes:
        best = max(portfolio_changes, key=lambda x: x[1])
        worst = min(portfolio_changes, key=lambda x: x[1])
        report += f"\n✅ <b>En Güçlü:</b> ${best[0]} ({best[1]:+.2f}%)\n"
        report += f"⚠️ <b>En Zayıf:</b> ${worst[0]} ({worst[1]:+.2f}%)\n"
    
    # WATCHLIST
    report += "\n<b>👀 WATCHLIST - EN UYGUN</b>\n"
    report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for ticker in watchlist[:5]:
        data = get_finnhub_realtime(ticker)
        if data:
            change_pct = data['change_pct']
            
            if change_pct >= 2:
                change_emoji = "🟢📈"
            elif change_pct > 0:
                change_emoji = "📈"
            elif change_pct >= -2:
                change_emoji = "📉"
            else:
                change_emoji = "🔴📉"
            
            report += f"\n<b>${ticker}</b> {change_emoji} <b>{change_pct:+.2f}%</b>\n"
            report += f"  💰 ${data['current_price']} | Aralık: ${data['low']} - ${data['high']}\n"
    
    report += "\n" + "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    report += "⏰ <b>Sonraki Rapor: +4 saat</b>\n"
    report += "🔗 Dashboard: https://claude.ai\n"
    
    return report, alerts

def send_telegram(message):
    """Telegram'a mesaj gönder - HTML formatında"""
    try:
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(TELEGRAM_URL, json=payload)
        if response.status_code == 200:
            print("✅ Telegram'a gönderildi!")
            return True
        else:
            print(f"❌ Hata: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Gönderme hatası: {e}")
        return False

if __name__ == "__main__":
    print("📊 Real-time Portföy Raporu Oluşturuluyor...")
    
    portfolio, watchlist, cash_reserve = load_portfolio()
    
    if portfolio:
        report, alerts = create_realtime_report(portfolio, watchlist, cash_reserve)
        print(report)
        
        # HER ZAMAN RAPOR GÖNDER
        print("\n📤 Telegram'a Gönderiliyor...")
        send_telegram(report)
        
        # %5+ ALERT VARSA EK MESAJ GÖNDER
        if alerts:
            alert_message = "<b>🚨 ÖNEMLİ DEĞİŞİKLİKLER (%5+)</b>\n"
            alert_message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            alert_message += "\n".join(alerts)
            alert_message += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            print("\n⚠️ Alert Telegram'a Gönderiliyor...")
            send_telegram(alert_message)
    else:
        print("❌ Portföy yüklenemedi!")

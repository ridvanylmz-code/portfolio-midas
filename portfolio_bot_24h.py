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

# Istanbul timezone
IST = pytz.timezone('Europe/Istanbul')

def load_portfolio():
    """portfolio.json'dan portföy yükle"""
    try:
        with open('portfolio.json', 'r') as f:
            data = json.load(f)
        return data.get('portfolio', {}), data.get('watchlist', []), data.get('cash_reserve', 0)
    except:
        print("❌ portfolio.json bulunamadı!")
        return {}, [], 0

def get_finnhub_realtime(ticker):
    """Finnhub'dan real-time veri çek (pre/after-hours dahil)"""
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
                'volume': int(data.get('v', 0)),
                'timestamp': data.get('t', 0)
            }
        return None
    except Exception as e:
        print(f"⚠️ {ticker} veri çekme hatası: {e}")
        return None

def create_realtime_report(portfolio, watchlist, cash_reserve):
    """Real-time portföy raporu oluştur"""
    
    report = "📊 PORTFÖY MIDAS - REAL-TIME RAPOR\n"
    report += f"⏰ {datetime.now(IST).strftime('%d.%m.%Y %H:%M')} Istanbul\n"
    report += "=" * 50 + "\n\n"
    
    # Önemli değişiklikler (%5+)
    alerts = []
    portfolio_changes = []
    total_value = 0
    total_cost = 0
    daily_pl_total = 0
    
    # Maliyet bazı (portfolio.json'dan okumak için güncelle)
    cost_basis_data = {
        'WYFI': 12.00,
        'RKLB': 9.50,
        'CRWV': 27.50,
        'UAMY': 4.40,
        'SGML': 5.65,
        'CBRS': 3.45,
        'CGNX': 15.60
    }
    
    report += "🎯 AKTİF POZİSYONLAR\n"
    report += "-" * 50 + "\n"
    
    for ticker, shares in portfolio.items():
        data = get_finnhub_realtime(ticker)
        if data:
            current_price = data['current_price']
            change_pct = data['change_pct']
            position_value = current_price * shares
            total_value += position_value
            
            # Maliyet hesabı
            cost_price = cost_basis_data.get(ticker, current_price)
            cost_value = cost_price * shares
            total_cost += cost_value
            pl = position_value - cost_value
            daily_pl_total += pl
            
            pl_pct = (pl / cost_value * 100) if cost_value > 0 else 0
            
            change_emoji = "📈" if change_pct >= 0 else "📉"
            pl_emoji = "📈" if pl >= 0 else "📉"
            
            # %5+ ALERT
            if abs(change_pct) >= 5.0:
                alerts.append(f"🚨 ${ticker}: {change_pct:+.2f}% | Fiyat: ${current_price}")
            
            report += f"${ticker}: ${current_price} {change_emoji} {change_pct:+.2f}%\n"
            report += f"  Pozisyon: {shares} hisse | Değer: ${position_value:,.0f}\n"
            report += f"  Maliyet: ${cost_value:,.0f} | P&L: ${pl:,.0f} ({pl_pct:+.2f}%) {pl_emoji}\n"
            report += f"  Gün Aralığı: ${data['low']} - ${data['high']}\n"
            report += f"  Hacim: {data['volume']:,}\n\n"
            
            portfolio_changes.append((ticker, change_pct, pl_pct))
    
    # ÖZET
    report += "\n💰 ÖZET\n"
    report += "-" * 50 + "\n"
    total_portfolio = total_value + cash_reserve
    total_pl = total_value - total_cost
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0
    
    report += f"Portföy Değeri: ${total_value:,.0f}\n"
    report += f"Nakit Yedek: ${cash_reserve:,.0f}\n"
    report += f"Toplam: ${total_portfolio:,.0f}\n\n"
    
    report += f"Maliyet Bazı: ${total_cost:,.0f}\n"
    report += f"Toplam Kar/Zarar: ${total_pl:,.0f} ({total_pl_pct:+.2f}%)\n"
    report += f"Günlük Kar/Zarar: ${daily_pl_total:,.0f}\n\n"
    
    if portfolio_changes:
        best = max(portfolio_changes, key=lambda x: x[1])
        worst = min(portfolio_changes, key=lambda x: x[1])
        report += f"✅ En Güçlü: ${best[0]} ({best[1]:+.2f}%)\n"
        report += f"⚠️ En Zayıf: ${worst[0]} ({worst[1]:+.2f}%)\n"
    
    # Watchlist
    report += "\n👀 WATCHLIST\n"
    report += "-" * 50 + "\n"
    for ticker in watchlist[:3]:
        data = get_finnhub_realtime(ticker)
        if data:
            change_emoji = "📈" if data['change_pct'] >= 0 else "📉"
            report += f"${ticker}: ${data['current_price']} {change_emoji} {data['change_pct']:+.2f}%\n"
    
    report += "\n" + "=" * 50
    report += "\n⏰ Sonraki Rapor: +4 saat\n"
    report += "🔗 Dashboard: https://claude.ai\n"
    
    return report, alerts

def send_telegram(message):
    """Telegram'a mesaj gönder"""
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
        
        # HER ZAMAN rapor gönder
print("\n📤 Telegram'a Gönderiliyor...")
send_telegram(report)

# Eğer %5+ alert varsa ek mesaj gönder
if alerts:
    alert_message = "🚨 ÖNEMLİ DEĞİŞİKLİKLER (%5+):\n\n" + "\n".join(alerts)
    print("⚠️ Alert de gönderiliyor...")
    send_telegram(alert_message)
    else:
        print("❌ Portföy yüklenemedi!")

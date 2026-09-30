import requests
import os
from datetime import datetime

# Telegram Ayarları
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# Portföy Pozisyonları
PORTFOLIO = {
    'WYFI': 120,
    'RKLB': 850,
    'CRWV': 280,
    'UAMY': 950,
    'SGML': 450,
    'CBRS': 1200,
    'CGNX': 75
}

WATCHLIST = ['AVGO', 'MU', 'HPE', 'KTOS', 'AVAV']

def get_stock_price(ticker):
    """Alpha Vantage'den hisse fiyatı al"""
    try:
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={ticker}&apikey=demo"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if 'Global Quote' in data:
            price = float(data['Global Quote'].get('05. price', 0))
            change = float(data['Global Quote'].get('09. change', 0))
            change_pct = float(data['Global Quote'].get('10. change percent', '0').replace('%', ''))
            return {'price': price, 'change': change, 'change_pct': change_pct}
        return None
    except:
        return None

def create_report():
    """Portföy raporunu oluştur"""
    report = "📊 PORTFÖY MIDAS - GÜNLÜK RAPOR\n"
    report += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    report += "=" * 50 + "\n\n"
    
    report += "🎯 AKTİF POZİSYONLAR\n"
    report += "-" * 50 + "\n"
    
    portfolio_changes = []
    
    for ticker, shares in PORTFOLIO.items():
        data = get_stock_price(ticker)
        if data:
            price = data['price']
            change_pct = data['change_pct']
            position_value = price * shares
            
            change_emoji = "📈" if change_pct > 0 else "📉"
            rsi = 50 + (change_pct * 2)  # Simplified RSI
            
            if rsi > 70:
                signal = "SATIŞ"
            elif rsi < 30:
                signal = "ALIM"
            elif change_pct > 2:
                signal = "ALIM"
            else:
                signal = "BEKLE"
            
            report += f"${ticker}: ${price:.2f} {change_emoji} {change_pct:+.2f}%\n"
            report += f"  RSI: {rsi:.0f} | Sinyal: {signal}\n"
            report += f"  Pozisyon: {shares} hisse | Değer: ${position_value:,.0f}\n\n"
            
            portfolio_changes.append((ticker, change_pct))
    
    report += "\n👀 WATCHLIST - EN UYGUN 5\n"
    report += "-" * 50 + "\n"
    
    watchlist_data = []
    for ticker in WATCHLIST[:5]:
        data = get_stock_price(ticker)
        if data:
            price = data['price']
            change_pct = data['change_pct']
            change_emoji = "📈" if change_pct > 0 else "📉"
            
            rsi = 50 + (change_pct * 2)
            if rsi > 70:
                signal = "SATIŞ"
            elif rsi < 30:
                signal = "ALIM"
            elif change_pct > 2:
                signal = "ALIM"
            else:
                signal = "BEKLE"
            
            report += f"${ticker}: ${price:.2f} {change_emoji} {change_pct:+.2f}%\n"
            report += f"  Sinyal: {signal}\n\n"
            
            watchlist_data.append((ticker, signal))
    
    report += "\n💡 GÜNLÜK ÖNERİLER\n"
    report += "-" * 50 + "\n"
    
    if portfolio_changes:
        best = max(portfolio_changes, key=lambda x: x[1])
        report += f"✅ En Güçlü: ${best[0]} ({best[1]:+.2f}%)\n"
        
        worst = min(portfolio_changes, key=lambda x: x[1])
        report += f"⚠️ En Zayıf: ${worst[0]} ({worst[1]:+.2f}%)\n"
    
    report += "\n" + "=" * 50
    report += "\n🔔 Sonraki Rapor: 20:01 (akşam)\n"
    
    return report

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
        else:
            print(f"❌ Hata: {response.text}")
    except Exception as e:
        print(f"❌ Gönderme hatası: {e}")

if __name__ == "__main__":
    print("📊 Portföy Raporu Oluşturuluyor...")
    report = create_report()
    print(report)
    print("\n📤 Telegram'a Gönderiliyor...")
    send_telegram(report)
    print("✅ Bitti!")

import requests
import os
from datetime import datetime
import json

# Telegram Ayarları
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

# Mock Portföy Verileri (Manuel, test amaçlı)
PORTFOLIO_DATA = {
    'WYFI': {'shares': 120, 'price': 12.45, 'change': 1.8},
    'RKLB': {'shares': 850, 'price': 9.87, 'change': 2.1},
    'CRWV': {'shares': 280, 'price': 28.45, 'change': 3.2},
    'UAMY': {'shares': 950, 'price': 4.25, 'change': -0.8},
    'SGML': {'shares': 450, 'price': 5.67, 'change': 0.6},
    'CBRS': {'shares': 1200, 'price': 3.42, 'change': -0.3},
    'CGNX': {'shares': 75, 'price': 15.89, 'change': 1.5}
}

WATCHLIST_DATA = {
    'AVGO': {'price': 218.40, 'change': 8.2},
    'MU': {'price': 94.30, 'change': 5.4},
    'HPE': {'price': 18.20, 'change': 1.2},
    'KTOS': {'price': 52.70, 'change': 6.8},
    'ASML': {'price': 782.50, 'change': -2.1}
}

def get_signal(change):
    """Al/Sat/Bekle sinyali"""
    if change > 3:
        return "ALIM"
    elif change < -2:
        return "SATIŞ"
    elif -1 <= change <= 1:
        return "BEKLE"
    else:
        return "ALIM" if change > 0 else "SATIŞ"

def create_report():
    """Portföy raporunu oluştur"""
    report = "📊 PORTFÖY MIDAS - GÜNLÜK RAPOR\n"
    report += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    report += "=" * 50 + "\n\n"
    
    report += "🎯 AKTİF POZİSYONLAR\n"
    report += "-" * 50 + "\n"
    
    portfolio_changes = []
    total_value = 0
    
    for ticker, data in PORTFOLIO_DATA.items():
        price = data['price']
        shares = data['shares']
        change = data['change']
        position_value = price * shares
        total_value += position_value
        
        change_emoji = "📈" if change > 0 else "📉"
        rsi = 50 + (change * 5)
        signal = get_signal(change)
        
        report += f"${ticker}: ${price:.2f} {change_emoji} {change:+.2f}%\n"
        report += f"  RSI: {rsi:.0f} | Sinyal: {signal}\n"
        report += f"  Pozisyon: {shares} hisse | Değer: ${position_value:,.0f}\n\n"
        
        portfolio_changes.append((ticker, change, price))
    
    report += "\n👀 WATCHLIST - EN UYGUN 5\n"
    report += "-" * 50 + "\n"
    
    watchlist_changes = []
    for ticker, data in list(WATCHLIST_DATA.items())[:5]:
        price = data['price']
        change = data['change']
        change_emoji = "📈" if change > 0 else "📉"
        signal = get_signal(change)
        
        report += f"${ticker}: ${price:.2f} {change_emoji} {change:+.2f}%\n"
        report += f"  Sinyal: {signal}\n\n"
        
        watchlist_changes.append((ticker, signal, change))
    
    report += "\n💡 GÜNLÜK ÖNERİLER\n"
    report += "-" * 50 + "\n"
    
    if portfolio_changes:
        best = max(portfolio_changes, key=lambda x: x[1])
        worst = min(portfolio_changes, key=lambda x: x[1])
        
        report += f"✅ En Güçlü: ${best[0]} ({best[1]:+.2f}%)\n"
        report += f"⚠️ En Zayıf: ${worst[0]} ({worst[1]:+.2f}%)\n"
    
    buy_signals = [t[0] for t in watchlist_changes if t[1] == 'ALIM']
    if buy_signals:
        report += f"🛒 Alım Fırsatı: {', '.join(buy_signals[:3])}\n"
    
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

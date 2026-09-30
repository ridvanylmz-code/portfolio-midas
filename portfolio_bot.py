import yfinance as yf
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

WATCHLIST = ['AVGO', 'MU', 'HPE', 'KTOS', 'AVAV', 'ONDS', 'IONQ']

def get_stock_data(ticker):
    """Yahoo Finance'ten gerçek veri al"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='2d')
        
        if len(hist) < 2:
            return None
        
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_price) / prev_price) * 100
        
        return {
            'price': round(float(current_price), 2),
            'change': round(float(change_pct), 2)
        }
    except:
        return None

def calculate_rsi(ticker, period=14):
    """RSI hesapla"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='100d')
        
        if len(hist) < period:
            return 50
        
        close = hist['Close']
        delta = close.diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(float(rsi.iloc[-1]), 2)
    except:
        return 50

def get_signal(rsi, change):
    """Al/Sat/Bekle sinyali"""
    if rsi > 70:
        return "SATIŞ"
    elif rsi < 30:
        return "ALIM"
    elif change > 3:
        return "GÜÇLÜ ALIM"
    elif change > 1:
        return "ALIM"
    else:
        return "BEKLE"

def create_report():
    """Portföy raporunu oluştur"""
    report = "📊 PORTFÖY MIDAS - GÜNLÜK RAPOR\n"
    report += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    report += "=" * 50 + "\n\n"
    
    report += "🎯 AKTİF POZİSYONLAR\n"
    report += "-" * 50 + "\n"
    
    portfolio_changes = []
    total_value = 0
    
    for ticker, shares in PORTFOLIO.items():
        data = get_stock_data(ticker)
        if data:
            price = data['price']
            change = data['change']
            rsi = calculate_rsi(ticker)
            position_value = price * shares
            total_value += position_value
            
            signal = get_signal(rsi, change)
            change_emoji = "📈" if change > 0 else "📉"
            
            report += f"${ticker}: ${price} {change_emoji} {change:+.2f}%\n"
            report += f"  RSI: {rsi:.0f} | Sinyal: {signal}\n"
            report += f"  Pozisyon: {shares} hisse | Değer: ${position_value:,.0f}\n\n"
            
            portfolio_changes.append((ticker, change, signal))
    
    report += "\n👀 WATCHLIST - EN UYGUN 5\n"
    report += "-" * 50 + "\n"
    
    watchlist_data = []
    for ticker in WATCHLIST[:5]:
        data = get_stock_data(ticker)
        if data:
            price = data['price']
            change = data['change']
            rsi = calculate_rsi(ticker)
            signal = get_signal(rsi, change)
            change_emoji = "📈" if change > 0 else "📉"
            
            report += f"${ticker}: ${price} {change_emoji} {change:+.2f}%\n"
            report += f"  RSI: {rsi:.0f} | Sinyal: {signal}\n\n"
            
            watchlist_data.append((ticker, signal, change))
    
    report += "\n💡 GÜNLÜK ÖNERİLER\n"
    report += "-" * 50 + "\n"
    
    if portfolio_changes:
        best = max(portfolio_changes, key=lambda x: x[1])
        worst = min(portfolio_changes, key=lambda x: x[1])
        
        report += f"✅ En Güçlü: ${best[0]} ({best[1]:+.2f}%)\n"
        report += f"⚠️ En Zayıf: ${worst[0]} ({worst[1]:+.2f}%)\n"
    
    buy_signals = [t[0] for t in watchlist_data if 'ALIM' in t[1]]
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

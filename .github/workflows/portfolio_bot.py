import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime
import ta

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

# Watchlist
WATCHLIST = ['AVGO', 'MU', 'HPE', 'KTOS', 'AVAV', 'IONQ', 'ASML']

def get_technical_indicators(ticker, period=20):
    """Teknik göstergeleri hesapla"""
    try:
        data = yf.download(ticker, period='3mo', progress=False)
        if len(data) < 2:
            return None
        
        # RSI
        rsi = ta.momentum.rsi(data['Close'], window=14).iloc[-1]
        
        # MACD
        macd = ta.trend.macd(data['Close'])
        macd_signal = macd.iloc[-1] if len(macd) > 0 else 0
        
        # Moving Averages
        ma20 = data['Close'].rolling(window=20).mean().iloc[-1]
        ma50 = data['Close'].rolling(window=50).mean().iloc[-1]
        
        # Günlük değişim
        current_price = data['Close'].iloc[-1]
        prev_price = data['Close'].iloc[-2]
        daily_change = ((current_price - prev_price) / prev_price) * 100
        
        return {
            'price': round(current_price, 2),
            'daily_change': round(daily_change, 2),
            'rsi': round(rsi, 2),
            'ma20': round(ma20, 2),
            'ma50': round(ma50, 2)
        }
    except:
        return None

def get_signal(rsi, daily_change, ma20, ma50):
    """Al/Sat/Bekle sinyali"""
    if rsi > 70:
        return "SATIŞ"
    elif rsi < 30:
        return "ALIM"
    elif daily_change > 3:
        return "GÜÇLÜ ALIM"
    elif ma20 > ma50:
        return "ALIM"
    else:
        return "BEKLE"

def create_report():
    """Portföy raporunu oluştur"""
    report = "📊 PORTFÖY MIDAS - GÜNLÜK RAPOR\n"
    report += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    report += "=" * 50 + "\n\n"
    
    # Portföy Analizi
    report += "🎯 AKTİF POZİSYONLAR\n"
    report += "-" * 50 + "\n"
    
    total_value = 0
    portfolio_changes = []
    
    for ticker, shares in PORTFOLIO.items():
        indicators = get_technical_indicators(ticker)
        if indicators:
            price = indicators['price']
            daily_change = indicators['daily_change']
            rsi = indicators['rsi']
            position_value = price * shares
            total_value += position_value
            
            signal = get_signal(rsi, daily_change, indicators['ma20'], indicators['ma50'])
            
            # Renk sinyalleri (Telegram Unicode)
            change_emoji = "📈" if daily_change > 0 else "📉"
            
            report += f"${ticker}: ${price} {change_emoji} {daily_change:+.2f}%\n"
            report += f"  RSI: {rsi:.0f} | Sinyal: {signal}\n"
            report += f"  Pozisyon: {shares} hisse | Değer: ${position_value:,.0f}\n\n"
            
            portfolio_changes.append((ticker, daily_change))
    
    # Watchlist Analizi
    report += "\n👀 WATCHLIST - EN UYGUN 5\n"
    report += "-" * 50 + "\n"
    
    watchlist_data = []
    for ticker in WATCHLIST[:5]:
        indicators = get_technical_indicators(ticker)
        if indicators:
            price = indicators['price']
            daily_change = indicators['daily_change']
            rsi = indicators['rsi']
            
            signal = get_signal(rsi, daily_change, indicators['ma20'], indicators['ma50'])
            change_emoji = "📈" if daily_change > 0 else "📉"
            
            report += f"${ticker}: ${price} {change_emoji} {daily_change:+.2f}%\n"
            report += f"  RSI: {rsi:.0f} | Sinyal: {signal}\n\n"
            
            watchlist_data.append((ticker, signal, daily_change))
    
    # Öneriler
    report += "\n💡 GÜNLÜK ÖNERİLER\n"
    report += "-" * 50 + "\n"
    
    # En güçlü momentum
    best = max(portfolio_changes, key=lambda x: x[1])
    report += f"✅ En Güçlü: ${best[0]} ({best[1]:+.2f}%)\n"
    
    # En zayıf
    worst = min(portfolio_changes, key=lambda x: x[1])
    report += f"⚠️ En Zayıf: ${worst[0]} ({worst[1]:+.2f}%)\n"
    
    # AL sinyali veren watchlist
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

import yfinance as yf
import requests
import os
import json
from datetime import datetime

# Telegram Ayarları
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def load_portfolio():
    """GitHub'dan portfolio.json yükle"""
    try:
        with open('portfolio.json', 'r') as f:
            data = json.load(f)
        return data.get('portfolio', {}), data.get('watchlist', []), data.get('cash_reserve', 0)
    except:
        print("❌ portfolio.json bulunamadı!")
        return {}, [], 0

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

def create_report(portfolio, watchlist, cash_reserve):
    """Portföy raporunu oluştur"""
    report = "📊 PORTFÖY MIDAS - GÜNLÜK RAPOR\n"
    report += f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    report += "=" * 50 + "\n\n"
    
    report += "🎯 AKTİF POZİSYONLAR\n"
    report += "-" * 50 + "\n"
    
    portfolio_changes = []
    total_value = 0
    
    for ticker, shares in portfolio.items():
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
    
    # Nakit bilgisi
    total_portfolio = total_value + cash_reserve
    report += f"\n💰 NAKIT YEDEK: ${cash_reserve:,.0f}\n"
    report += f"📊 TOPLAM PORTFÖY: ${total_portfolio:,.0f}\n\n"
    
    report += "👀 WATCHLIST - EN UYGUN\n"
    report += "-" * 50 + "\n"
    
    watchlist_data = []
    for ticker in watchlist[:5]:
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
    report += f"📁 Portföy Güncelleme: portfolio.json'dan okunuyor\n"
    
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
    
    # portfolio.json'dan oku
    portfolio, watchlist, cash_reserve = load_portfolio()
    
    if portfolio:
        report = create_report(portfolio, watchlist, cash_reserve)
        print(report)
        print("\n📤 Telegram'a Gönderiliyor...")
        send_telegram(report)
        print("✅ Bitti!")
    else:
        print("❌ Portföy yüklenemedi!")

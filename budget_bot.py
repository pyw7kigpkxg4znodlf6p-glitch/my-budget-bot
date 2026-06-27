import telebot
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Font, Alignment

TOKEN = "8881978694:AAEQA7iJby2z5HN9Lj_gMuYClkyp_OGwj5A"
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect('budget.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    type TEXT,
    amount REAL,
    category TEXT,
    description TEXT
)
''')
conn.commit()

expense_categories = [
    "Аренда квартиры", "Коммуналка", "Зоо товары", "Аптека", "Врачи",
    "Гигиена и уход", "Одежда и обувь", "Общественный транспорт и такси",
    "Бензин", "Ремонт и обслуживание авто", "Бытовые товары", "Продукты",
    "Кафе и доставки", "Вредные привычки", "Подарки", "Подписки", "Техника",
    "Долги", "Мебель", "Ремонт", "Отдых и развлечения", "Мобильная связь",
    "Интернет", "Инвестиции", "Другое"
]

income_categories = ["Зарплата", "Фриланс", "Инвестиции", "Подарки", "Другое"]

def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ Добавить", "📊 Отчёты")
    markup.add("📋 Последние операции", "📤 Экспорт Excel")
    markup.add("🗑 Удалить операцию", "ℹ️ Помощь")
    return markup

def get_user_df(user_id):
    df = pd.read_sql_query("SELECT * FROM transactions WHERE user_id = ?", conn, params=(user_id,))
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "👋 Бот готов! Используй кнопки.", reply_markup=main_menu())

# Добавление операций (простое)
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_operation(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("➖ Расход", callback_data="add_expense"),
        telebot.types.InlineKeyboardButton("➕ Доход", callback_data="add_income")
    )
    bot.send_message(message.chat.id, "Что добавляем?", reply_markup=markup)

# ... (остальные функции добавления можно взять из предыдущих версий)

# ================== КРАСИВЫЕ ТЕКСТОВЫЕ ОТЧЁТЫ ==================
@bot.message_handler(func=lambda m: m.text == "📊 Отчёты")
def reports(message):
    user_id = message.from_user.id
    df = get_user_df(user_id)
    if df.empty:
        bot.send_message(message.chat.id, "Нет операций.")
        return

    now = datetime.now()
    month = df[df['date'].dt.month == now.month]
    
    income = month[month['type']=='income']['amount'].sum()
    expense = month[month['type']=='expense']['amount'].sum()
    
    text = f"<b>📊 Отчёт за {now.strftime('%B %Y')}</b>\n\n"
    text += f"➕ Доходы: {income:,.0f} ₽\n"
    text += f"➖ Расходы: {expense:,.0f} ₽\n"
    text += f"💰 Баланс: {income-expense:,.0f} ₽\n\n"
    
    if expense > 0:
        top = month[month['type']=='expense'].groupby('category')['amount'].sum().nlargest(8)
        text += "<b>🔥 Топ расходов:</b>\n"
        for cat, val in top.items():
            text += f"• {cat:<22} {val:>8,.0f} ₽\n"
    
    bot.send_message(message.chat.id, text, parse_mode='HTML')

# ================== ЭКСПОРТ В EXCEL С ГРАФИКАМИ ==================
@bot.message_handler(func=lambda m: m.text == "📤 Экспорт Excel")
def export_excel(message):
    user_id = message.from_user.id
    df = pd.read_sql_query("SELECT * FROM transactions WHERE user_id = ?", conn, params=(user_id,))
    
    if df.empty:
        bot.send_message(message.chat.id, "Нет данных.")
        return

    filename = f"budget_{user_id}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Все операции', index=False)
        summary = df.groupby(['type', 'category']).agg({'amount': 'sum'}).reset_index()
        summary.to_excel(writer, sheet_name='Сводка', index=False)
    
    # Добавляем графики
    wb = writer.book
    ws = wb['Сводка']
    
    expense_data = summary[summary['type'] == 'expense']
    if not expense_data.empty:
        chart = PieChart()
        labels = Reference(ws, min_col=2, min_row=2, max_row=len(expense_data)+1)
        data = Reference(ws, min_col=3, min_row=1, max_row=len(expense_data)+1)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(labels)
        chart.title = "Расходы по категориям"
        ws.add_chart(chart, "E2")
    
    chart2 = BarChart()
    chart2.add_data(data, titles_from_data=True)
    chart2.set_categories(labels)
    chart2.title = "Сравнение расходов"
    ws.add_chart(chart2, "E20")
    
    wb.save(filename)
    
    with open(filename, 'rb') as f:
        bot.send_document(message.chat.id, f, caption="📊 Твой бюджет в Excel с графиками!")
    
    os.remove(filename)

print("✅ Бот с текстовыми таблицами и Excel запущен!")
bot.infinity_polling()
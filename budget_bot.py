import telebot
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference

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
    bot.send_message(message.chat.id, "👋 Бот готов!", reply_markup=main_menu())

# Добавление (упрощённо)
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_operation(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("➖ Расход", callback_data="add_expense"),
        telebot.types.InlineKeyboardButton("➕ Доход", callback_data="add_income")
    )
    bot.send_message(message.chat.id, "Что добавляем?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def callback_add(call):
    tr_type = "expense" if call.data == "add_expense" else "income"
    cats = expense_categories if tr_type == "expense" else income_categories
    text = f"Выберите категорию:\n\n" + "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(cats)])
    msg = bot.send_message(call.message.chat.id, text)
    bot.register_next_step_handler(msg, lambda m: process_category(m, tr_type))

def process_category(message, tr_type):
    try:
        num = int(message.text.strip())
        cats = expense_categories if tr_type == "expense" else income_categories
        category = cats[num-1]
        bot.send_message(message.chat.id, f"✅ {category}\nВведите сумму:")
        bot.register_next_step_handler(message, lambda m: process_amount(m, category, tr_type))
    except:
        bot.send_message(message.chat.id, "❌ Введите номер.")

def process_amount(message, category, tr_type):
    try:
        amount = float(message.text.replace(',', '.').strip())
        bot.send_message(message.chat.id, "Комментарий (или '-'):")
        bot.register_next_step_handler(message, lambda m: save_transaction(m, tr_type, amount, category))
    except:
        bot.send_message(message.chat.id, "❌ Введите сумму.")

def save_transaction(message, tr_type, amount, category):
    user_id = message.from_user.id
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    description = message.text if message.text != "-" else ""
    cursor.execute("INSERT INTO transactions (user_id, date, type, amount, category, description) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, date, tr_type, amount, category, description))
    conn.commit()
    emoji = "➖" if tr_type == "expense" else "➕"
    bot.send_message(message.chat.id, f"{emoji} Записано: {category} — {amount} ₽", reply_markup=main_menu())

# ================== ОТЧЁТЫ ==================
@bot.message_handler(func=lambda m: m.text == "📊 Отчёты")
def choose_period_report(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    periods = ["День", "Неделя", "Месяц", "Всё время"]
    for p in periods:
        markup.add(telebot.types.InlineKeyboardButton(p, callback_data=f"report_{p}"))
    bot.send_message(message.chat.id, "Выберите период:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("report_"))
def generate_report(call):
    period = call.data.split("_")[1]
    user_id = call.from_user.id
    df = get_user_df(user_id)
    if df.empty:
        bot.send_message(call.message.chat.id, "Нет операций.")
        return

    now = datetime.now()
    if period == "День":
        filtered = df[df['date'].dt.date == now.date()]
    elif period == "Неделя":
        filtered = df[df['date'] >= now - timedelta(days=7)]
    elif period == "Месяц":
        filtered = df[df['date'].dt.month == now.month]
    else:
        filtered = df

    income = filtered[filtered['type']=='income']['amount'].sum()
    expense = filtered[filtered['type']=='expense']['amount'].sum()

    text = f"<b>Отчёт за {period}</b>\n\n"
    text += f"➕ Доходы: {income:,.0f} ₽\n➖ Расходы: {expense:,.0f} ₽\n💰 Баланс: {income-expense:,.0f} ₽\n\n"

    if expense > 0:
        top = filtered[filtered['type']=='expense'].groupby('category')['amount'].sum().nlargest(8)
        text += "<b>Топ расходов:</b>\n"
        for cat, val in top.items():
            text += f"• {cat}: {val:,.0f} ₽ ({val/expense*100:.1f}%)\n"

    bot.send_message(call.message.chat.id, text, parse_mode='HTML')

# ================== ЭКСПОРТ ==================
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
    
    with open(filename, 'rb') as f:
        bot.send_document(message.chat.id, f, caption="📊 Твой бюджет в Excel")
    os.remove(filename)

print("✅ Бот запущен!")
bot.infinity_polling()
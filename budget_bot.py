import telebot
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

TOKEN = "8881978694:AAEQA7iJby2z5HN9Lj_gMuYClkyp_OGwj5A"
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect('budget.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    type TEXT,
    amount REAL,
    category TEXT,
    description TEXT
)
''')
conn.commit()

# ================== НОВЫЕ КАТЕГОРИИ ==================
expense_categories = [
    "Аренда квартиры",
    "Коммуналка",
    "Зоо товары",
    "Аптека",
    "Врачи",
    "Гигиена и уход",
    "Одежда и обувь",
    "Общественный транспорт и такси",
    "Бензин",
    "Ремонт и обслуживание авто",
    "Бытовые товары",
    "Продукты",
    "Кафе и доставки",
    "Вредные привычки",
    "Подарки",
    "Подписки",
    "Техника",
    "Долги",
    "Мебель",
    "Ремонт",
    "Отдых и развлечения",
    "Мобильная связь",
    "Интернет",
    "Инвестиции",
    "Другое"
]

income_categories = ["Зарплата", "Фриланс", "Инвестиции", "Подарки", "Другое"]

def main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ Добавить", "📊 Отчёты")
    markup.add("📈 Графики", "📋 Последние операции")
    markup.add("🗑 Удалить операцию", "ℹ️ Помощь")
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 
        "🚀 <b>Бот обновлён!</b>\n\nНовые категории расходов добавлены.", 
        parse_mode='HTML', reply_markup=main_menu())

# ================== ДОБАВЛЕНИЕ ОПЕРАЦИЙ ==================
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
    text = f"Выберите категорию {'расхода' if tr_type == 'expense' else 'дохода'}:\n\n" + "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(cats)])
    msg = bot.send_message(call.message.chat.id, text)
    bot.register_next_step_handler(msg, lambda m: process_category(m, tr_type))

def process_category(message, tr_type):
    try:
        num = int(message.text.strip())
        cats = expense_categories if tr_type == "expense" else income_categories
        category = cats[num-1]
        bot.send_message(message.chat.id, f"✅ Выбрано: {category}\nВведите сумму:")
        bot.register_next_step_handler(message, lambda m: process_amount(m, category, tr_type))
    except:
        bot.send_message(message.chat.id, "❌ Введите правильный номер категории.")

def process_amount(message, category, tr_type):
    try:
        amount = float(message.text.replace(',', '.').strip())
        bot.send_message(message.chat.id, "Добавьте комментарий (или '-'):")
        bot.register_next_step_handler(message, lambda m: save_transaction(m, tr_type, amount, category))
    except:
        bot.send_message(message.chat.id, "❌ Введите сумму числом.")

def save_transaction(message, tr_type, amount, category):
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    description = message.text if message.text != "-" else ""
    cursor.execute("INSERT INTO transactions (date, type, amount, category, description) VALUES (?, ?, ?, ?, ?)",
                   (date, tr_type, amount, category, description))
    conn.commit()
    emoji = "➖" if tr_type == "expense" else "➕"
    bot.send_message(message.chat.id, f"{emoji} Записано!\n{category}: {amount} ₽", reply_markup=main_menu())

# ================== ОТЧЁТЫ, ГРАФИКИ, УДАЛЕНИЕ ==================
# (Остальной код оставлен без изменений — всё работает как раньше)

@bot.message_handler(func=lambda m: m.text == "📊 Отчёты")
def choose_period_report(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    periods = ["День", "Неделя", "Месяц", "Квартал", "Год", "Всё время"]
    for p in periods:
        markup.add(telebot.types.InlineKeyboardButton(p, callback_data=f"report_{p}"))
    bot.send_message(message.chat.id, "Выберите период отчёта:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("report_"))
def generate_report(call):
    period = call.data.split("_")[1]
    bot.send_message(call.message.chat.id, f"⏳ Формирую отчёт за {period}...")
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    if df.empty:
        bot.send_message(call.message.chat.id, "Нет данных.")
        return
    df['date'] = pd.to_datetime(df['date'])
    now = datetime.now()
    
    if period == "День":
        filtered = df[df['date'].dt.date == now.date()]
    elif period == "Неделя":
        filtered = df[df['date'] >= now - timedelta(days=7)]
    elif period == "Месяц":
        filtered = df[df['date'].dt.month == now.month]
    elif period == "Квартал":
        filtered = df[df['date'].dt.quarter == now.quarter]
    elif period == "Год":
        filtered = df[df['date'].dt.year == now.year]
    else:
        filtered = df
    
    income = filtered[filtered['type']=='income']['amount'].sum()
    expense = filtered[filtered['type']=='expense']['amount'].sum()
    
    text = f"<b>Отчёт за {period}</b>\n\n"
    text += f"➕ Доходы: {income:.0f} ₽\n➖ Расходы: {expense:.0f} ₽\n💰 Баланс: {income-expense:.0f} ₽\n\n"
    
    if expense > 0:
        top = filtered[filtered['type']=='expense'].groupby('category')['amount'].sum().nlargest(6)
        text += "<b>Топ расходов:</b>\n"
        for cat, val in top.items():
            text += f"• {cat}: {val:.0f} ₽ ({val/expense*100:.1f}%)\n"
    
    bot.send_message(call.message.chat.id, text, parse_mode='HTML')

# Графики и удаление операций (оставлены как были)
@bot.message_handler(func=lambda m: m.text == "📈 Графики")
def choose_period_graph(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    periods = ["Месяц", "Квартал", "Год", "Всё время"]
    for p in periods:
        markup.add(telebot.types.InlineKeyboardButton(p, callback_data=f"graph_{p}"))
    bot.send_message(message.chat.id, "Выберите период для графиков:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("graph_"))
def generate_graphs(call):
    period = call.data.split("_")[1]
    bot.send_message(call.message.chat.id, f"⏳ Строю графики за {period}...")
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    if df.empty:
        bot.send_message(call.message.chat.id, "Нет данных.")
        return
    df['date'] = pd.to_datetime(df['date'])
    now = datetime.now()
    
    if period == "Месяц":
        filtered = df[df['date'].dt.month == now.month]
    elif period == "Квартал":
        filtered = df[df['date'].dt.quarter == now.quarter]
    elif period == "Год":
        filtered = df[df['date'].dt.year == now.year]
    else:
        filtered = df

    exp = filtered[filtered['type'] == 'expense']
    if not exp.empty:
        plt.figure(figsize=(9,7))
        exp.groupby('category')['amount'].sum().plot(kind='pie', autopct='%1.1f%%', startangle=90)
        plt.title(f'Структура расходов — {period}')
        plt.ylabel('')
        plt.savefig('pie.png', bbox_inches='tight')
        with open('pie.png', 'rb') as p:
            bot.send_photo(call.message.chat.id, p, caption=f"📊 Расходы по категориям ({period})")
        os.remove('pie.png')

    if not exp.empty:
        plt.figure(figsize=(10,6))
        top_exp = exp.groupby('category')['amount'].sum().nlargest(8)
        top_exp.plot(kind='bar')
        plt.title(f'Топ расходов — {period}')
        plt.ylabel('Сумма ₽')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig('bar.png')
        with open('bar.png', 'rb') as p:
            bot.send_photo(call.message.chat.id, p, caption="📊 Топ категорий расходов")
        os.remove('bar.png')

    filtered_sorted = filtered.sort_values('date')
    filtered_sorted['balance'] = filtered_sorted.apply(lambda x: x['amount'] if x['type']=='income' else -x['amount'], axis=1).cumsum()
    plt.figure(figsize=(11,5))
    plt.plot(filtered_sorted['date'], filtered_sorted['balance'], marker='o', linewidth=2.5)
    plt.title(f'Динамика баланса — {period}')
    plt.xlabel('Дата')
    plt.ylabel('Баланс ₽')
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('trend.png')
    with open('trend.png', 'rb') as p:
        bot.send_photo(call.message.chat.id, p, caption=f"📈 Динамика баланса ({period})")
    os.remove('trend.png')

# Удаление и остальные функции
@bot.message_handler(func=lambda m: m.text == "🗑 Удалить операцию")
def delete_operation(message):
    cursor.execute("SELECT id, date, type, category, amount FROM transactions ORDER BY date DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "Нет операций.")
        return
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    text = "<b>Выберите операцию для удаления:</b>\n\n"
    for row in rows:
        emoji = "➕" if row[2] == "income" else "➖"
        short_date = row[1][:16]
        text += f"{emoji} {short_date} | {row[3]} | {row[4]} ₽\n"
        markup.add(telebot.types.InlineKeyboardButton(f"🗑 {short_date} — {row[3]}", callback_data=f"del_{row[0]}"))
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def confirm_delete(call):
    op_id = int(call.data.split("_")[1])
    cursor.execute("SELECT date, category, amount FROM transactions WHERE id = ?", (op_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("DELETE FROM transactions WHERE id = ?", (op_id,))
        conn.commit()
        bot.send_message(call.message.chat.id, f"🗑 Удалено:\n{row[0][:16]} | {row[1]} | {row[2]} ₽")
    else:
        bot.send_message(call.message.chat.id, "Операция не найдена.")

@bot.message_handler(func=lambda m: m.text in ["📋 Последние операции", "ℹ️ Помощь"])
def other_handlers(message):
    if message.text == "📋 Последние операции":
        cursor.execute("SELECT id, date, category, amount, type FROM transactions ORDER BY date DESC LIMIT 10")
        rows = cursor.fetchall()
        text = "<b>Последние 10 операций:</b>\n\n"
        for row in rows:
            emoji = "➕" if row[4] == "income" else "➖"
            text += f"{emoji} {row[1][:16]} | {row[2]} | {row[3]} ₽\n"
        bot.send_message(message.chat.id, text, parse_mode='HTML')
    else:
        bot.send_message(message.chat.id, "Используй кнопки для управления бюджетом.", reply_markup=main_menu())

print("✅ Бот с новыми категориями запущен!")
bot.infinity_polling()

import json
import logging
import os
from datetime import datetime
from typing import Any

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID",
    "1LLEE79yZpd2o-vBXDz0Z_uHx97lgR_Eo",
)
SHEET_NAME = os.getenv("SHEET_NAME", "Отчеты")

MACHINES = [
    "Экскаватор CAT 330",
    "Экскаватор CAT 320",
    "Самосвал MAN 20 м³",
    "Манипулятор-вездеход",
    "Кран-вездеход 25 т",
    "Мини-погрузчик CAT 242D",
    "Низкорамный трал 60 т",
    "Экскаватор-погрузчик",
    "Самосвал Урал Next",
]

WORK_TYPES = [
    "Земляные работы",
    "Разработка котлована",
    "Погрузка грунта",
    "Вывоз грунта",
    "Доставка материалов",
    "Планировка территории",
    "Перевозка техники",
    "Работа крана",
    "Работа манипулятора",
    "Другое",
]

RATE_TYPES = ["За час", "За смену", "За рейс", "Фиксированная"]
PAYMENT_STATUSES = ["Оплачено", "Частично", "Не оплачено", "Отсрочка"]

HEADERS = [
    "Дата и время сохранения",
    "Дата работы",
    "Техника",
    "Машинист / водитель",
    "Объект",
    "Заказчик",
    "Вид работы",
    "Начало",
    "Окончание",
    "Часы",
    "Тип ставки",
    "Ставка",
    "Рейсы",
    "Топливо, л",
    "Итоговая сумма",
    "Статус оплаты",
    "Примечание",
    "Пользователь Telegram",
    "Username Telegram",
    "Chat ID",
]

(
    MACHINE,
    DATE,
    DATE_MANUAL,
    DRIVER,
    OBJECT,
    CUSTOMER,
    WORK,
    START_TIME,
    END_TIME,
    RATE_TYPE,
    RATE,
    TRIPS,
    FUEL,
    PAYMENT,
    NOTE,
    CONFIRM,
) = range(16)


def _credentials() -> Credentials:
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    file_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    if raw_json:
        info = json.loads(raw_json)
        return Credentials.from_service_account_info(info, scopes=scopes)

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            "Не найден service_account.json. "
            "Добавьте файл или задайте GOOGLE_SERVICE_ACCOUNT_JSON."
        )

    return Credentials.from_service_account_file(file_path, scopes=scopes)


def get_worksheet():
    client = gspread.authorize(_credentials())
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=SHEET_NAME,
            rows=1000,
            cols=len(HEADERS),
        )

    if not worksheet.row_values(1):
        worksheet.update(
            range_name="A1:T1",
            values=[HEADERS],
            value_input_option="USER_ENTERED",
        )
        worksheet.freeze(rows=1)

    return worksheet


def save_report(worksheet, row_data: list[Any]) -> int:
    column_a = worksheet.col_values(1)
    next_row = max(len(column_a) + 1, 2)

    worksheet.update(
        range_name=f"A{next_row}:T{next_row}",
        values=[row_data],
        value_input_option="USER_ENTERED",
    )

    return next_row


def inline_keyboard(values: list[str], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(value, callback_data=f"{prefix}|{i}")]
            for i, value in enumerate(values)
        ]
    )


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["Новый отчет"]],
        resize_keyboard=True,
    )


def parse_number(value: str) -> float:
    return float(value.replace(" ", "").replace(",", "."))


def valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def valid_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%d.%m.%Y")
        return True
    except ValueError:
        return False


def calculate_hours(start: str, end: str) -> float:
    start_dt = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    minutes = (end_dt.hour * 60 + end_dt.minute) - (
        start_dt.hour * 60 + start_dt.minute
    )
    if minutes < 0:
        minutes += 24 * 60
    return round(minutes / 60, 2)


def calculate_amount(data: dict[str, Any]) -> float:
    rate = float(data.get("rate", 0))
    if data["rate_type"] == "За час":
        return round(rate * float(data["hours"]), 2)
    if data["rate_type"] == "За рейс":
        return round(rate * float(data["trips"]), 2)
    return round(rate, 2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "🚜 Выберите технику:",
        reply_markup=inline_keyboard(MACHINES, "machine"),
    )
    return MACHINE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Отчёт отменён.",
        reply_markup=main_keyboard(),
    )
    return ConversationHandler.END


async def machine_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("|", 1)[1])
    context.user_data["machine"] = MACHINES[index]
    await query.edit_message_text(
        "📅 Укажите дату работы:",
        reply_markup=inline_keyboard(["Сегодня", "Другая дата"], "date"),
    )
    return DATE


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("|", 1)[1])

    if index == 0:
        context.user_data["work_date"] = datetime.now().strftime("%d.%m.%Y")
        await query.edit_message_text("👷 Введите имя машиниста или водителя:")
        return DRIVER

    await query.edit_message_text("Введите дату в формате ДД.ММ.ГГГГ:")
    return DATE_MANUAL


async def date_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not valid_date(text):
        await update.message.reply_text("Неверный формат. Пример: 23.07.2026")
        return DATE_MANUAL
    context.user_data["work_date"] = text
    await update.message.reply_text("👷 Введите имя машиниста или водителя:")
    return DRIVER


async def driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["driver"] = update.message.text.strip()
    await update.message.reply_text("📍 Введите адрес или название объекта:")
    return OBJECT


async def object_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["object"] = update.message.text.strip()
    await update.message.reply_text("🏢 Введите заказчика или отправьте «-»:")
    return CUSTOMER


async def customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.message.text.strip()
    context.user_data["customer"] = "" if value == "-" else value
    await update.message.reply_text(
        "🛠 Выберите вид работы:",
        reply_markup=inline_keyboard(WORK_TYPES, "work"),
    )
    return WORK


async def work_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("|", 1)[1])
    context.user_data["work_type"] = WORK_TYPES[index]
    await query.edit_message_text("🕘 Время начала работы, например 08:00:")
    return START_TIME


async def start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not valid_time(text):
        await update.message.reply_text("Введите время в формате ЧЧ:ММ, например 08:00:")
        return START_TIME
    context.user_data["start_time"] = text
    await update.message.reply_text("🕔 Время окончания работы, например 17:00:")
    return END_TIME


async def end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not valid_time(text):
        await update.message.reply_text("Введите время в формате ЧЧ:ММ, например 17:00:")
        return END_TIME

    context.user_data["end_time"] = text
    context.user_data["hours"] = calculate_hours(
        context.user_data["start_time"],
        text,
    )
    await update.message.reply_text(
        f"Отработано: {context.user_data['hours']} ч.\nВыберите вид ставки:",
        reply_markup=inline_keyboard(RATE_TYPES, "rate"),
    )
    return RATE_TYPE


async def rate_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("|", 1)[1])
    context.user_data["rate_type"] = RATE_TYPES[index]
    await query.edit_message_text("💰 Введите ставку числом, например 6000:")
    return RATE


async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = parse_number(update.message.text)
        if value <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите положительное число, например 6000:")
        return RATE

    context.user_data["rate"] = value
    await update.message.reply_text("🚚 Количество рейсов. Если нет — отправьте 0:")
    return TRIPS


async def trips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = parse_number(update.message.text)
        if value < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число 0 или больше:")
        return TRIPS

    context.user_data["trips"] = value
    await update.message.reply_text("⛽ Расход топлива в литрах. Если не учитывается — 0:")
    return FUEL


async def fuel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        value = parse_number(update.message.text)
        if value < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число 0 или больше:")
        return FUEL

    context.user_data["fuel"] = value
    await update.message.reply_text(
        "💳 Выберите статус оплаты:",
        reply_markup=inline_keyboard(PAYMENT_STATUSES, "payment"),
    )
    return PAYMENT


async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("|", 1)[1])
    context.user_data["payment_status"] = PAYMENT_STATUSES[index]
    await query.edit_message_text("📝 Добавьте примечание или отправьте «-»:")
    return NOTE


async def note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.message.text.strip()
    context.user_data["note"] = "" if value == "-" else value
    context.user_data["amount"] = calculate_amount(context.user_data)

    d = context.user_data
    summary = (
        "Проверьте отчёт:\n\n"
        f"📅 {d['work_date']}\n"
        f"🚜 {d['machine']}\n"
        f"👷 {d['driver']}\n"
        f"📍 {d['object']}\n"
        f"🏢 {d['customer'] or '—'}\n"
        f"🛠 {d['work_type']}\n"
        f"🕘 {d['start_time']}–{d['end_time']}\n"
        f"⏱ {d['hours']} ч.\n"
        f"💰 {d['rate']:g} ₽ — {d['rate_type']}\n"
        f"🚚 Рейсы: {d['trips']:g}\n"
        f"⛽ Топливо: {d['fuel']:g} л\n"
        f"💳 {d['payment_status']}\n"
        f"🧾 Итог: {d['amount']:g} ₽\n"
        f"📝 {d['note'] or '—'}"
    )
    await update.message.reply_text(
        summary,
        reply_markup=inline_keyboard(["Сохранить", "Отменить"], "confirm"),
    )
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("|", 1)[1])

    if index == 1:
        context.user_data.clear()
        await query.edit_message_text("Отчёт отменён.")
        await query.message.reply_text("Готово.", reply_markup=main_keyboard())
        return ConversationHandler.END

    d = context.user_data
    user = update.effective_user

    row_data = [
        datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        d["work_date"],
        d["machine"],
        d["driver"],
        d["object"],
        d["customer"],
        d["work_type"],
        d["start_time"],
        d["end_time"],
        d["hours"],
        d["rate_type"],
        d["rate"],
        d["trips"],
        d["fuel"],
        d["amount"],
        d["payment_status"],
        d["note"],
        user.full_name,
        f"@{user.username}" if user.username else "",
        str(update.effective_chat.id),
    ]

    try:
        worksheet = get_worksheet()
        saved_row = save_report(worksheet, row_data)
        logger.info("Отчёт записан в таблицу '%s', строка %s", SHEET_NAME, saved_row)
    except Exception:
        logger.exception("Не удалось записать отчёт в Google Таблицу")
        await query.edit_message_text(
            "❌ Не удалось записать отчёт в Google Таблицу.\n\n"
            "Проверьте настройки Railway и журнал Deploy Logs."
        )
        return CONFIRM

    await query.edit_message_text(
        "✅ Отчёт сохранён в Google Таблицу.\n\n"
        f"Техника: {d['machine']}\n"
        f"Дата: {d['work_date']}\n"
        f"Сумма: {d['amount']:g} ₽\n"
        f"Строка таблицы: {saved_row}"
    )
    await query.message.reply_text(
        "Новый отчёт можно начать кнопкой ниже.",
        reply_markup=main_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Ошибка при обработке обновления", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка. Попробуйте ещё раз командой /start."
        )


def build_application() -> Application:
    app = Application.builder().token(TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("new", start),
            MessageHandler(filters.Regex("^Новый отчет$"), start),
        ],
        states={
            MACHINE: [CallbackQueryHandler(machine_selected, pattern=r"^machine\|")],
            DATE: [CallbackQueryHandler(date_selected, pattern=r"^date\|")],
            DATE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_manual)],
            DRIVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, driver)],
            OBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_name)],
            CUSTOMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, customer)],
            WORK: [CallbackQueryHandler(work_selected, pattern=r"^work\|")],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_time)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_time)],
            RATE_TYPE: [CallbackQueryHandler(rate_type_selected, pattern=r"^rate\|")],
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate)],
            TRIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, trips)],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, fuel)],
            PAYMENT: [CallbackQueryHandler(payment_selected, pattern=r"^payment\|")],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note)],
            CONFIRM: [CallbackQueryHandler(confirm, pattern=r"^confirm\|")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conversation)
    app.add_error_handler(error_handler)
    return app


if __name__ == "__main__":
    logger.info("Запуск Telegram-бота...")
    application = build_application()
    application.run_polling(drop_pending_updates=False)

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

BOT_VERSION = "3.2-final-multi-objects"
TOKEN = os.environ["BOT_TOKEN"]
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID",
    "1LLEE79yZpd2o-vBXDz0Z_uHx97lgR_Eo",
)
SHEET_NAME = os.getenv("SHEET_NAME", "Отчеты")

EQUIPMENT = [
    ("Экскаватор-погрузчик", "CAT 434E №1", "3151 МК 50"),
    ("Экскаватор-погрузчик", "CAT 434E №3", "6314 ХЕ 50"),
    ("Экскаватор-погрузчик", "CAT 434E №4", "1273 ХН 50"),
    ("Экскаватор-погрузчик", "CAT 434 №5", "1272 ХН 50"),
    ("Экскаватор-погрузчик", "CAT 444 №6", "5945 ХТ 50"),
    ("Минипогрузчик", "CAT 242", "1331 ХН 50"),
    ("Экскаватор", "CAT 330", "5106 ХХ 50"),
    ("Экскаватор", "CAT 320", "9346 ХХ 50"),
    ("Экскаватор", "Hitachi 180", "1271 ХН 50"),
    ("Экскаватор", "Hitachi 200", "3149 МК 50"),
    ("Самосвал шоссейный", "MAN TGS", "У 516 МС 790"),
    ("Самосвал шоссейный", "MAN TGS", "У 496 МС 790"),
    ("Самосвал шоссейный", "MAN TGS", "Х 333 ВТ 99"),
    ("Самосвал шоссейный", "MAN TGS", "С 625 ВУ 550"),
    ("Самосвал", "Урал NEXT", "А 677 МА 790"),
    ("Самосвал", "Урал NEXT", "А 646 МА 790"),
    ("Самосвал", "Урал NEXT", "С 873 ВС 790"),
    ("Самосвал", "Урал NEXT", "С 918 ВС 790"),
    ("Самосвал", "Урал NEXT", "А 668 МА 790"),
    ("Манипулятор", "КамАЗ", "В 727 КН 790"),
    ("Манипулятор", "КамАЗ", "В 746 КН 790"),
    ("Манипулятор", "КамАЗ", "У 695 РУ 790"),
    ("Кран", "КамАЗ", "О 437 УС 797"),
    ("Тягач", "MAN TGS", "В 777 ЕН 150"),
]

MULTI_OBJECT_PLATES = {
    "У 516 МС 790",
    "У 496 МС 790",
    "Х 333 ВТ 99",
    "С 625 ВУ 550",
    "В 777 ЕН 150",
}

RATE_TYPES = ["За час", "За смену", "За рейс", "Фиксированная", "-"]
PAYMENT_STATUSES = ["Оплачено", "Частично", "Не оплачено", "Отсрочка"]

HEADERS = [
    "Дата работы",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Машинист / водитель",
]
for i in range(1, 5):
    HEADERS.extend([
        f"Объект {i}",
        f"Заказчик {i}",
        f"Ставка за рейс {i}, ₽",
        f"Рейсы {i}",
    ])
HEADERS.extend([
    "Начало",
    "Окончание",
    "Рабочее время, ч",
    "Вид ставки",
    "Ставка, ₽",
    "Всего рейсов",
    "Сумма, ₽",
    "Статус оплаты",
    "Примечание",
    "Дата и время сохранения",
    "Пользователь Telegram",
    "Username Telegram",
    "Chat ID",
])

OLD_HEADERS = [
    "Дата работы", "Наименование техники", "Модель", "Гос. номер",
    "Машинист / водитель", "Объект", "Заказчик", "Начало", "Окончание",
    "Рабочее время, ч", "Вид ставки", "Ставка, ₽", "Рейсы", "Сумма, ₽",
    "Статус оплаты", "Примечание", "Дата и время сохранения",
    "Пользователь Telegram", "Username Telegram", "Chat ID",
]

(
    MACHINE, DATE, DATE_MANUAL, DRIVER, OBJECT_COUNT, OBJECT_NAME, CUSTOMER,
    OBJECT_TRIP_RATE, OBJECT_TRIPS, START_TIME, END_TIME, RATE_TYPE, RATE,
    GLOBAL_TRIPS, PAYMENT, NOTE, CONFIRM, EDIT_SELECT_REPORT,
    EDIT_SELECT_FIELD, EDIT_VALUE, EDIT_PAYMENT, EDIT_RATE_TYPE,
) = range(22)

BASE_COL = {
    "driver": 5,
    "start_time": 22,
    "end_time": 23,
    "hours": 24,
    "rate_type": 25,
    "rate": 26,
    "total_trips": 27,
    "amount": 28,
    "payment_status": 29,
    "note": 30,
}


def object_col(index: int, field: str) -> int:
    offsets = {"object": 0, "customer": 1, "trip_rate": 2, "trips": 3}
    return 6 + (index - 1) * 4 + offsets[field]


def _credentials() -> Credentials:
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    file_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if raw_json:
        return Credentials.from_service_account_info(json.loads(raw_json), scopes=scopes)
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            "Не найден service_account.json. Добавьте файл или задайте "
            "GOOGLE_SERVICE_ACCOUNT_JSON."
        )
    return Credentials.from_service_account_file(file_path, scopes=scopes)


def a1_col(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def pad_row(row: list[str]) -> list[str]:
    return row + [""] * (len(HEADERS) - len(row))


def normalize_number(value: Any) -> str | float:
    if value in (None, "", "-"):
        return "-"
    number = float(str(value).replace(" ", "").replace(",", "."))
    return int(number) if number.is_integer() else round(number, 2)


def number_or_zero(value: Any) -> float:
    if value in (None, "", "-"):
        return 0.0
    return float(str(value).replace(" ", "").replace(",", "."))


def format_number(value: Any) -> str:
    if value in (None, "", "-"):
        return "-"
    number = number_or_zero(value)
    return f"{number:g}"


def valid_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%d.%m.%Y")
        return True
    except ValueError:
        return False


def valid_time_or_dash(value: str) -> bool:
    if value == "-":
        return True
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except ValueError:
        return False


def calculate_hours(start: str, end: str) -> str | float:
    if start == "-" or end == "-":
        return "-"
    start_dt = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    minutes = (end_dt.hour * 60 + end_dt.minute) - (start_dt.hour * 60 + start_dt.minute)
    if minutes < 0:
        minutes += 24 * 60
    # Автоматически вычитаем один час обеда.
    hours = max(0.0, minutes / 60 - 1)
    return round(hours, 2)


def is_multi_machine(data: dict[str, Any]) -> bool:
    return data.get("plate") in MULTI_OBJECT_PLATES


def calculate_totals(data: dict[str, Any]) -> tuple[str | float, float]:
    if is_multi_machine(data):
        total_trips = sum(number_or_zero(item.get("trips")) for item in data["objects"])
        amount = sum(
            number_or_zero(item.get("trip_rate")) * number_or_zero(item.get("trips"))
            for item in data["objects"]
        )
        return normalize_number(total_trips), round(amount, 2)

    total_trips = normalize_number(data.get("global_trips", "-"))
    rate = number_or_zero(data.get("rate"))
    rate_type = data.get("rate_type", "-")
    hours = number_or_zero(data.get("hours"))
    trips = number_or_zero(total_trips)
    if rate_type == "За час":
        amount = rate * hours
    elif rate_type == "За рейс":
        amount = rate * trips
    elif rate_type in {"За смену", "Фиксированная"}:
        amount = rate
    else:
        amount = 0.0
    return total_trips, round(amount, 2)


def migrate_old_rows(worksheet) -> None:
    current = worksheet.row_values(1)
    if current == HEADERS:
        return
    if current != OLD_HEADERS:
        worksheet.update(
            range_name=f"A1:{a1_col(len(HEADERS))}1",
            values=[HEADERS],
            value_input_option="USER_ENTERED",
        )
        return

    old_rows = worksheet.get_all_values()[1:]
    new_rows: list[list[Any]] = []
    for old in old_rows:
        old += [""] * (len(OLD_HEADERS) - len(old))
        new = [""] * len(HEADERS)
        new[0:5] = old[0:5]
        new[5] = old[5]
        new[6] = old[6]
        new[7] = old[11] if old[10] == "За рейс" else "-"
        new[8] = old[12] or "-"
        new[21] = old[7]
        new[22] = old[8]
        new[23] = old[9]
        new[24] = old[10]
        new[25] = old[11]
        new[26] = old[12]
        new[27] = old[13]
        new[28] = old[14]
        new[29] = old[15]
        new[30] = old[16]
        new[31] = old[17]
        new[32] = old[18]
        new[33] = old[19]
        new_rows.append(new)

    worksheet.clear()
    worksheet.resize(rows=max(1000, len(new_rows) + 10), cols=len(HEADERS))
    worksheet.update(
        range_name=f"A1:{a1_col(len(HEADERS))}{len(new_rows) + 1}",
        values=[HEADERS] + new_rows,
        value_input_option="USER_ENTERED",
    )


def format_worksheet(worksheet) -> None:
    worksheet.resize(cols=len(HEADERS))
    worksheet.freeze(rows=1)
    worksheet.format(
        f"A1:{a1_col(len(HEADERS))}1",
        {
            "backgroundColor": {"red": 0.08, "green": 0.28, "blue": 0.48},
            "textFormat": {
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                "bold": True,
                "fontSize": 10,
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
        },
    )


def get_worksheet():
    client = gspread.authorize(_credentials())
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=SHEET_NAME, rows=1000, cols=len(HEADERS)
        )
    migrate_old_rows(worksheet)
    worksheet.update(
        range_name=f"A1:{a1_col(len(HEADERS))}1",
        values=[HEADERS],
        value_input_option="USER_ENTERED",
    )
    try:
        format_worksheet(worksheet)
    except Exception:
        logger.exception("Не удалось оформить таблицу")
    return worksheet


def first_empty_row(worksheet) -> int:
    values = worksheet.get("A2:A")
    for row_number, row in enumerate(values, start=2):
        if not row or not str(row[0]).strip():
            return row_number
    return len(values) + 2


def save_report(worksheet, row_data: list[Any]) -> int:
    row_number = first_empty_row(worksheet)
    end_col = a1_col(len(HEADERS))
    worksheet.update(
        range_name=f"A{row_number}:{end_col}{row_number}",
        values=[row_data],
        value_input_option="USER_ENTERED",
    )
    worksheet.format(
        f"A{row_number}:{end_col}{row_number}",
        {"verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"},
    )
    return row_number


def equipment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"{index}. {name} {model} — {plate}",
            callback_data=f"machine|{index - 1}",
        )]
        for index, (name, model, plate) in enumerate(EQUIPMENT, start=1)
    ])


def inline_keyboard(values: list[str], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(value, callback_data=f"{prefix}|{i}")]
        for i, value in enumerate(values)
    ])


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🚜 Новый отчет", "✏️ Изменить отчет"]], resize_keyboard=True
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Выберите действие:", reply_markup=main_keyboard()
    )
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "🚜 Выберите технику:", reply_markup=equipment_keyboard()
    )
    return MACHINE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Отчёт отменён.", reply_markup=main_keyboard()
    )
    return ConversationHandler.END


async def machine_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    index = int(query.data.split("|", 1)[1])
    name, model, plate = EQUIPMENT[index]
    context.user_data.update({
        "equipment_name": name,
        "equipment_model": model,
        "plate": plate,
        "objects": [],
    })
    await query.edit_message_text(
        "📅 Укажите дату работы:",
        reply_markup=inline_keyboard(["Сегодня", "Другая дата"], "date"),
    )
    return DATE


async def date_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if int(query.data.split("|", 1)[1]) == 0:
        context.user_data["work_date"] = datetime.now().strftime("%d.%m.%Y")
        await query.edit_message_text("👷 Введите имя машиниста или водителя:")
        return DRIVER
    await query.edit_message_text("Введите дату в формате ДД.ММ.ГГГГ:")
    return DATE_MANUAL


async def date_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not valid_date(text):
        await update.message.reply_text("Неверный формат. Пример: 30.07.2026")
        return DATE_MANUAL
    context.user_data["work_date"] = text
    await update.message.reply_text("👷 Введите имя машиниста или водителя:")
    return DRIVER


async def driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["driver"] = update.message.text.strip()
    if is_multi_machine(context.user_data):
        await update.message.reply_text(
            "Сколько объектов указать? Выберите от 1 до 4:",
            reply_markup=inline_keyboard(["1", "2", "3", "4"], "objcount"),
        )
        return OBJECT_COUNT
    context.user_data["object_count"] = 1
    context.user_data["current_object"] = 1
    await update.message.reply_text("📍 Введите объект 1:")
    return OBJECT_NAME


async def object_count_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    count = int(query.data.split("|", 1)[1]) + 1
    context.user_data["object_count"] = count
    context.user_data["current_object"] = 1
    await query.edit_message_text("📍 Введите объект 1:")
    return OBJECT_NAME


async def object_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["pending_object"] = {"object": update.message.text.strip()}
    number = context.user_data["current_object"]
    await update.message.reply_text(f"🏢 Введите заказчика {number} или отправьте «-»:")
    return CUSTOMER


async def customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["pending_object"]["customer"] = "" if text == "-" else text
    if is_multi_machine(context.user_data):
        number = context.user_data["current_object"]
        await update.message.reply_text(
            f"💰 Введите ставку за рейс для объекта {number} или «-»:"
        )
        return OBJECT_TRIP_RATE

    context.user_data["pending_object"].update({"trip_rate": "-", "trips": "-"})
    context.user_data["objects"].append(context.user_data.pop("pending_object"))
    await update.message.reply_text("🕘 Введите время начала ЧЧ:ММ или «-»:")
    return START_TIME


async def object_trip_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        value = normalize_number(text)
        if value != "-" and number_or_zero(value) < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число 0 или больше либо «-»:")
        return OBJECT_TRIP_RATE
    context.user_data["pending_object"]["trip_rate"] = value
    number = context.user_data["current_object"]
    await update.message.reply_text(
        f"🚚 Введите количество рейсов по объекту {number} или «-»:"
    )
    return OBJECT_TRIPS


async def object_trips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        value = normalize_number(text)
        if value != "-" and number_or_zero(value) < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число 0 или больше либо «-»:")
        return OBJECT_TRIPS

    context.user_data["pending_object"]["trips"] = value
    context.user_data["objects"].append(context.user_data.pop("pending_object"))
    current = context.user_data["current_object"]
    if current < context.user_data["object_count"]:
        context.user_data["current_object"] = current + 1
        await update.message.reply_text(f"📍 Введите объект {current + 1}:")
        return OBJECT_NAME

    await update.message.reply_text("🕘 Введите время начала ЧЧ:ММ или «-»:")
    return START_TIME


async def start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not valid_time_or_dash(text):
        await update.message.reply_text("Введите время ЧЧ:ММ, например 08:00, либо «-»:")
        return START_TIME
    context.user_data["start_time"] = text
    await update.message.reply_text("🕔 Введите время окончания ЧЧ:ММ или «-»:")
    return END_TIME


async def end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not valid_time_or_dash(text):
        await update.message.reply_text("Введите время ЧЧ:ММ, например 17:00, либо «-»:")
        return END_TIME
    context.user_data["end_time"] = text
    context.user_data["hours"] = calculate_hours(context.user_data["start_time"], text)
    await update.message.reply_text(
        f"Рабочее время: {format_number(context.user_data['hours'])} ч. "
        "(если указано время, 1 час обеда уже вычтен).\nВыберите вид ставки:",
        reply_markup=inline_keyboard(RATE_TYPES, "rate_type"),
    )
    return RATE_TYPE


async def rate_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["rate_type"] = RATE_TYPES[int(query.data.split("|", 1)[1])]
    await query.edit_message_text("💰 Введите ставку или «-»:")
    return RATE


async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        value = normalize_number(text)
        if value != "-" and number_or_zero(value) < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число 0 или больше либо «-»:")
        return RATE
    context.user_data["rate"] = value

    if is_multi_machine(context.user_data):
        context.user_data["global_trips"] = "-"
        return await ask_payment(update, context)

    await update.message.reply_text("🚚 Введите количество рейсов или «-»:")
    return GLOBAL_TRIPS


async def global_trips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        value = normalize_number(text)
        if value != "-" and number_or_zero(value) < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число 0 или больше либо «-»:")
        return GLOBAL_TRIPS
    context.user_data["global_trips"] = value
    return await ask_payment(update, context)


async def ask_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "💳 Выберите статус оплаты:",
        reply_markup=inline_keyboard(PAYMENT_STATUSES, "payment"),
    )
    return PAYMENT


async def payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["payment_status"] = PAYMENT_STATUSES[
        int(query.data.split("|", 1)[1])
    ]
    await query.edit_message_text("📝 Добавьте примечание или отправьте «-»:")
    return NOTE


def report_text(data: dict[str, Any]) -> str:
    lines = [
        "Проверьте отчёт:\n",
        f"📅 {data['work_date']}",
        f"🚜 {data['equipment_name']} {data['equipment_model']}",
        f"🔢 {data['plate']}",
        f"👷 {data['driver']}",
    ]
    for index, item in enumerate(data["objects"], start=1):
        lines.extend([
            f"📍 Объект {index}: {item['object']}",
            f"🏢 Заказчик {index}: {item.get('customer') or '—'}",
        ])
        if is_multi_machine(data):
            lines.append(
                f"🚚 {format_number(item.get('trips'))} рейс.; "
                f"ставка {format_number(item.get('trip_rate'))} ₽/рейс"
            )
    lines.extend([
        f"🕘 {data['start_time']}–{data['end_time']}",
        f"⏱ {format_number(data['hours'])} ч.",
        f"💰 {data['rate_type']}; ставка {format_number(data['rate'])} ₽",
        f"🚚 Всего рейсов: {format_number(data['total_trips'])}",
        f"🧾 Сумма: {format_number(data['amount'])} ₽",
        f"💳 {data['payment_status']}",
        f"📝 {data['note'] or '—'}",
    ])
    return "\n".join(lines)


async def note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["note"] = "" if text == "-" else text
    total_trips, amount = calculate_totals(context.user_data)
    context.user_data["total_trips"] = total_trips
    context.user_data["amount"] = amount
    await update.message.reply_text(
        report_text(context.user_data),
        reply_markup=inline_keyboard(["Сохранить", "Отменить"], "confirm"),
    )
    return CONFIRM


def build_row(data: dict[str, Any], user: Any, chat_id: int) -> list[Any]:
    row: list[Any] = [
        data["work_date"], data["equipment_name"], data["equipment_model"],
        data["plate"], data["driver"],
    ]
    for i in range(4):
        if i < len(data["objects"]):
            item = data["objects"][i]
            trip_rate = item.get("trip_rate", "-")
            trips = item.get("trips", "-")
            # Для обычной техники единственный объект получает общие рейсы.
            # Это сохраняет корректный пересчёт при последующем изменении отчёта.
            if i == 0 and not is_multi_machine(data):
                trips = data.get("global_trips", "-")
                if data.get("rate_type") == "За рейс":
                    trip_rate = data.get("rate", "-")
            row.extend([
                item.get("object", ""), item.get("customer", ""),
                trip_rate, trips,
            ])
        else:
            row.extend(["", "", "-", "-"])
    row.extend([
        data["start_time"], data["end_time"], data["hours"],
        data["rate_type"], data["rate"], data["total_trips"], data["amount"],
        data["payment_status"], data["note"],
        datetime.now().strftime("%d.%m.%Y %H:%M:%S"), user.full_name,
        f"@{user.username}" if user.username else "", str(chat_id),
    ])
    return row


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if int(query.data.split("|", 1)[1]) == 1:
        context.user_data.clear()
        await query.edit_message_text("Отчёт отменён.")
        await query.message.reply_text("Выберите действие:", reply_markup=main_keyboard())
        return ConversationHandler.END

    try:
        worksheet = get_worksheet()
        saved_row = save_report(
            worksheet,
            build_row(context.user_data, update.effective_user, update.effective_chat.id),
        )
    except Exception:
        logger.exception("Не удалось записать отчёт")
        await query.edit_message_text("❌ Не удалось записать отчёт. Проверьте Railway Logs.")
        return CONFIRM

    await query.edit_message_text(
        "✅ Отчёт сохранён.\n\n"
        f"Техника: {context.user_data['equipment_name']} "
        f"{context.user_data['equipment_model']}\n"
        f"Гос. номер: {context.user_data['plate']}\n"
        f"Всего рейсов: {format_number(context.user_data['total_trips'])}\n"
        f"Сумма: {format_number(context.user_data['amount'])} ₽\n"
        f"Строка таблицы: {saved_row}"
    )
    await query.message.reply_text("Выберите действие:", reply_markup=main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


def report_summary(row_number: int, raw_row: list[str]) -> str:
    row = pad_row(raw_row)
    return (
        f"Строка {row_number}\n"
        f"Дата: {row[0]}\n"
        f"Техника: {row[1]} {row[2]} — {row[3]}\n"
        f"Водитель: {row[4] or '—'}\n"
        f"Объект 1: {row[5] or '—'}\n"
        f"Заказчик 1: {row[6] or '—'}\n"
        f"Начало–окончание: {row[21] or '—'}–{row[22] or '—'}\n"
        f"Рабочее время: {row[23] or '—'}\n"
        f"Вид ставки: {row[24] or '—'}\n"
        f"Ставка: {row[25] or '—'}\n"
        f"Всего рейсов: {row[26] or '—'}\n"
        f"Сумма: {row[27] or '—'} ₽\n"
        f"Статус: {row[28] or '—'}"
    )


def edit_fields_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("👷 Водителя", callback_data="editfield|driver")],
        [InlineKeyboardButton("🕘 Начало", callback_data="editfield|start_time")],
        [InlineKeyboardButton("🕔 Окончание", callback_data="editfield|end_time")],
        [InlineKeyboardButton("💰 Вид ставки", callback_data="editfield|rate_type")],
        [InlineKeyboardButton("💵 Ставку", callback_data="editfield|rate")],
        [InlineKeyboardButton("💳 Статус оплаты", callback_data="editfield|payment_status")],
        [InlineKeyboardButton("📝 Примечание", callback_data="editfield|note")],
    ]
    for i in range(1, 5):
        buttons.append([
            InlineKeyboardButton(f"📍 Объект {i}", callback_data=f"editfield|object_{i}"),
            InlineKeyboardButton(f"🏢 Заказчик {i}", callback_data=f"editfield|customer_{i}"),
        ])
        buttons.append([
            InlineKeyboardButton(f"💰 Ставка/рейс {i}", callback_data=f"editfield|trip_rate_{i}"),
            InlineKeyboardButton(f"🚚 Рейсы {i}", callback_data=f"editfield|trips_{i}"),
        ])
    return InlineKeyboardMarkup(buttons)


async def edit_report_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    try:
        rows = get_worksheet().get_all_values()
    except Exception:
        logger.exception("Не удалось загрузить отчёты")
        await update.effective_message.reply_text(
            "❌ Не удалось загрузить отчёты.", reply_markup=main_keyboard()
        )
        return ConversationHandler.END

    reports = []
    for row_number in range(len(rows), 1, -1):
        row = pad_row(rows[row_number - 1])
        if row[0].strip():
            reports.append((row_number, row))
        if len(reports) >= 20:
            break
    if not reports:
        await update.effective_message.reply_text(
            "В таблице пока нет отчётов.", reply_markup=main_keyboard()
        )
        return ConversationHandler.END

    buttons = [[InlineKeyboardButton(
        f"{row[0]} | {row[2]} | {row[3]} | {row[4] or 'без водителя'}"[:64],
        callback_data=f"editrow|{row_number}",
    )] for row_number, row in reports]
    await update.effective_message.reply_text(
        "Выберите отчёт для изменения:", reply_markup=InlineKeyboardMarkup(buttons)
    )
    return EDIT_SELECT_REPORT


async def edit_report_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    row_number = int(query.data.split("|", 1)[1])
    try:
        row = get_worksheet().row_values(row_number)
    except Exception:
        logger.exception("Не удалось открыть отчёт")
        await query.edit_message_text("❌ Не удалось открыть отчёт.")
        return ConversationHandler.END
    context.user_data["edit_row"] = row_number
    await query.edit_message_text(
        report_summary(row_number, row) + "\n\nЧто изменить?",
        reply_markup=edit_fields_keyboard(),
    )
    return EDIT_SELECT_FIELD


async def edit_field_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.split("|", 1)[1]
    context.user_data["edit_field"] = field
    if field == "payment_status":
        await query.edit_message_text(
            "Выберите статус:", reply_markup=inline_keyboard(PAYMENT_STATUSES, "editpayment")
        )
        return EDIT_PAYMENT
    if field == "rate_type":
        await query.edit_message_text(
            "Выберите вид ставки:", reply_markup=inline_keyboard(RATE_TYPES, "editratetype")
        )
        return EDIT_RATE_TYPE

    prompts = {
        "driver": "Введите водителя:",
        "start_time": "Введите время начала ЧЧ:ММ или «-»: ",
        "end_time": "Введите время окончания ЧЧ:ММ или «-»: ",
        "rate": "Введите ставку или «-»: ",
        "note": "Введите примечание или «-»: ",
    }
    if field.startswith("object_"):
        prompt = "Введите объект или «-»:"
    elif field.startswith("customer_"):
        prompt = "Введите заказчика или «-»:"
    elif field.startswith("trip_rate_"):
        prompt = "Введите ставку за рейс или «-»:"
    elif field.startswith("trips_"):
        prompt = "Введите количество рейсов или «-»:"
    else:
        prompt = prompts[field]
    await query.edit_message_text(prompt)
    return EDIT_VALUE


def field_column(field: str) -> int:
    if field in BASE_COL:
        return BASE_COL[field]
    prefix, index_text = field.rsplit("_", 1)
    return object_col(int(index_text), prefix)


def recalculate_row_values(row: list[str]) -> tuple[str | float, float, str | float]:
    row = pad_row(row)
    hours = calculate_hours(row[21] or "-", row[22] or "-")
    total_trips = sum(number_or_zero(row[object_col(i, "trips") - 1]) for i in range(1, 5))
    multi_amount = sum(
        number_or_zero(row[object_col(i, "trip_rate") - 1])
        * number_or_zero(row[object_col(i, "trips") - 1])
        for i in range(1, 5)
    )
    if row[3] in MULTI_OBJECT_PLATES:
        amount = multi_amount
    else:
        rate_type = row[24] or "-"
        rate = number_or_zero(row[25])
        if rate_type == "За час":
            amount = rate * number_or_zero(hours)
        elif rate_type == "За рейс":
            amount = rate * total_trips
        elif rate_type in {"За смену", "Фиксированная"}:
            amount = rate
        else:
            amount = 0
    return hours, round(amount, 2), normalize_number(total_trips)


async def edit_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("edit_field")
    row_number = context.user_data.get("edit_row")
    if not field or not row_number:
        await update.message.reply_text("Сеанс изменения завершён.", reply_markup=main_keyboard())
        return ConversationHandler.END

    text = update.message.text.strip()
    if field in {"start_time", "end_time"} and not valid_time_or_dash(text):
        await update.message.reply_text("Введите ЧЧ:ММ или «-»:")
        return EDIT_VALUE
    if field == "rate" or field.startswith("trip_rate_") or field.startswith("trips_"):
        try:
            value: Any = normalize_number(text)
            if value != "-" and number_or_zero(value) < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите число 0 или больше либо «-»:")
            return EDIT_VALUE
    elif field == "driver":
        value = text
    else:
        value = "" if text == "-" else text

    try:
        worksheet = get_worksheet()
        worksheet.update_cell(row_number, field_column(field), value)
        row = worksheet.row_values(row_number)
        hours, amount, total_trips = recalculate_row_values(row)
        worksheet.update(
            range_name=f"X{row_number}:AB{row_number}",
            values=[[hours, pad_row(row)[24], pad_row(row)[25], total_trips, amount]],
            value_input_option="USER_ENTERED",
        )
        updated = worksheet.row_values(row_number)
    except Exception:
        logger.exception("Не удалось изменить отчёт")
        await update.message.reply_text("❌ Не удалось изменить отчёт.", reply_markup=main_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Отчёт изменён.\n\n" + report_summary(row_number, updated),
        reply_markup=main_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def edit_payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    row_number = context.user_data.get("edit_row")
    status = PAYMENT_STATUSES[int(query.data.split("|", 1)[1])]
    try:
        worksheet = get_worksheet()
        worksheet.update_cell(row_number, BASE_COL["payment_status"], status)
        updated = worksheet.row_values(row_number)
    except Exception:
        logger.exception("Не удалось изменить статус")
        await query.edit_message_text("❌ Не удалось изменить отчёт.")
        return ConversationHandler.END
    await query.edit_message_text("✅ Статус изменён.\n\n" + report_summary(row_number, updated))
    await query.message.reply_text("Выберите действие:", reply_markup=main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def edit_rate_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    row_number = context.user_data.get("edit_row")
    value = RATE_TYPES[int(query.data.split("|", 1)[1])]
    try:
        worksheet = get_worksheet()
        worksheet.update_cell(row_number, BASE_COL["rate_type"], value)
        row = worksheet.row_values(row_number)
        hours, amount, total_trips = recalculate_row_values(row)
        worksheet.update(
            range_name=f"X{row_number}:AB{row_number}",
            values=[[hours, value, pad_row(row)[25], total_trips, amount]],
            value_input_option="USER_ENTERED",
        )
        updated = worksheet.row_values(row_number)
    except Exception:
        logger.exception("Не удалось изменить вид ставки")
        await query.edit_message_text("❌ Не удалось изменить отчёт.")
        return ConversationHandler.END
    await query.edit_message_text("✅ Вид ставки изменён.\n\n" + report_summary(row_number, updated))
    await query.message.reply_text("Выберите действие:", reply_markup=main_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def version_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Версия бота: {BOT_VERSION}\n"
        f"Техники в списке: {len(EQUIPMENT)}\n"
        "Поддерживаются до 4 объектов для шоссейных MAN и тягача."
    )


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
            CommandHandler("start", show_menu),
            CommandHandler("new", start),
            MessageHandler(filters.Regex(r"^(Новый отчет|🚜 Новый отчет)$"), start),
            MessageHandler(filters.Regex(r"^(Изменить отчет|✏️ Изменить отчет)$"), edit_report_start),
        ],
        states={
            MACHINE: [CallbackQueryHandler(machine_selected, pattern=r"^machine\|")],
            DATE: [CallbackQueryHandler(date_selected, pattern=r"^date\|")],
            DATE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_manual)],
            DRIVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, driver)],
            OBJECT_COUNT: [CallbackQueryHandler(object_count_selected, pattern=r"^objcount\|")],
            OBJECT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_name)],
            CUSTOMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, customer)],
            OBJECT_TRIP_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_trip_rate)],
            OBJECT_TRIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_trips)],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_time)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_time)],
            RATE_TYPE: [CallbackQueryHandler(rate_type_selected, pattern=r"^rate_type\|")],
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate)],
            GLOBAL_TRIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, global_trips)],
            PAYMENT: [CallbackQueryHandler(payment_selected, pattern=r"^payment\|")],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note)],
            CONFIRM: [CallbackQueryHandler(confirm, pattern=r"^confirm\|")],
            EDIT_SELECT_REPORT: [CallbackQueryHandler(edit_report_selected, pattern=r"^editrow\|")],
            EDIT_SELECT_FIELD: [CallbackQueryHandler(edit_field_selected, pattern=r"^editfield\|")],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_received)],
            EDIT_PAYMENT: [CallbackQueryHandler(edit_payment_selected, pattern=r"^editpayment\|")],
            EDIT_RATE_TYPE: [CallbackQueryHandler(edit_rate_type_selected, pattern=r"^editratetype\|")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(CommandHandler("version", version_command), group=-1)
    app.add_handler(conversation, group=0)
    app.add_error_handler(error_handler)
    return app


if __name__ == "__main__":
    logger.info("Запуск Telegram-бота. Версия: %s", BOT_VERSION)
    build_application().run_polling(drop_pending_updates=False)

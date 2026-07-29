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

BOT_VERSION = "3.0-multi-objects"

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

RATE_TYPES = ["За час", "За смену", "За рейс", "Фиксированная", "-"]

MULTI_OBJECT_PLATES = {
    "У 516 МС 790", "У 496 МС 790", "Х 333 ВТ 99",
    "С 625 ВУ 550", "В 777 ЕН 150",
}
PAYMENT_STATUSES = ["Оплачено", "Частично", "Не оплачено", "Отсрочка"]

HEADERS = [
    "Дата работы",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Машинист / водитель",
    "Объект",
    "Заказчик",
    "Начало",
    "Окончание",
    "Рабочее время, ч",
    "Вид ставки",
    "Ставка, ₽",
    "Рейсы",
    "Сумма, ₽",
    "Статус оплаты",
    "Примечание",
    "Дата и время сохранения",
    "Пользователь Telegram",
    "Username Telegram",
    "Chat ID",
    "Ставка за рейс — объект 1, ₽",
    "Рейсы — объект 1",
    "Объект 2",
    "Заказчик 2",
    "Ставка за рейс — объект 2, ₽",
    "Рейсы — объект 2",
    "Объект 3",
    "Заказчик 3",
    "Ставка за рейс — объект 3, ₽",
    "Рейсы — объект 3",
    "Объект 4",
    "Заказчик 4",
    "Ставка за рейс — объект 4, ₽",
    "Рейсы — объект 4",
]

(
    MACHINE,
    DATE,
    DATE_MANUAL,
    DRIVER,
    OBJECT,
    CUSTOMER,
    START_TIME,
    END_TIME,
    RATE_TYPE,
    RATE,
    TRIPS,
    PAYMENT,
    NOTE,
    CONFIRM,
    MULTI_COUNT,
    MULTI_OBJECT,
    MULTI_CUSTOMER,
    MULTI_RATE,
    MULTI_TRIPS,
) = range(19)

EDIT_SELECT_REPORT = 19
EDIT_SELECT_FIELD = 20
EDIT_VALUE = 21
EDIT_PAYMENT = 22

COL = {
    "driver": 5,
    "object": 6,
    "customer": 7,
    "start_time": 8,
    "end_time": 9,
    "hours": 10,
    "rate_type": 11,
    "rate": 12,
    "trips": 13,
    "amount": 14,
    "payment_status": 15,
    "note": 16,
}

EDIT_FIELDS = {
    "start_time": "🕘 Время начала",
    "end_time": "🕔 Время окончания",
    "rate": "💰 Ставку",
    "trips": "🚚 Количество рейсов",
    "object": "📍 Объект",
    "customer": "🏢 Заказчика",
    "driver": "👷 Машиниста / водителя",
    "payment_status": "💳 Статус оплаты",
    "note": "📝 Примечание",
}


def _credentials() -> Credentials:
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    file_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    if raw_json:
        return Credentials.from_service_account_info(
            json.loads(raw_json),
            scopes=scopes,
        )

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            "Не найден service_account.json. "
            "Добавьте файл или задайте GOOGLE_SERVICE_ACCOUNT_JSON."
        )

    return Credentials.from_service_account_file(file_path, scopes=scopes)


def format_worksheet(worksheet) -> None:
    sheet_id = worksheet.id
    widths = [
        105, 180, 135, 125, 165, 210, 180, 85, 85, 125,
        120, 105, 90, 110, 125, 220, 155, 170, 150, 125,
        135, 90, 210, 180, 135, 90, 210, 180, 135, 90,
        210, 180, 135, 90,
    ]

    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(HEADERS),
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {
                            "red": 0.08,
                            "green": 0.28,
                            "blue": 0.48,
                        },
                        "textFormat": {
                            "foregroundColor": {
                                "red": 1,
                                "green": 1,
                                "blue": 1,
                            },
                            "bold": True,
                            "fontSize": 11,
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "properties": {"pixelSize": 42},
                "fields": "pixelSize",
            }
        },
        {
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(HEADERS),
                    }
                }
            }
        },
    ]

    for index, width in enumerate(widths):
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": index,
                        "endIndex": index + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            }
        )

    worksheet.spreadsheet.batch_update({"requests": requests})


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

    if worksheet.col_count < len(HEADERS):
        worksheet.resize(cols=len(HEADERS))

    worksheet.update(
        range_name=f"A1:{gspread.utils.rowcol_to_a1(1, len(HEADERS))}",
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
    worksheet.update(
        range_name=f"A{row_number}:{gspread.utils.rowcol_to_a1(row_number, len(HEADERS))}",
        values=[row_data],
        value_input_option="USER_ENTERED",
    )
    worksheet.format(
        f"A{row_number}:{gspread.utils.rowcol_to_a1(row_number, len(HEADERS))}",
        {
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
            "borders": {
                "bottom": {
                    "style": "SOLID",
                    "color": {
                        "red": 0.82,
                        "green": 0.86,
                        "blue": 0.90,
                    },
                }
            },
        },
    )
    return row_number


def equipment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{index}. {model} — {plate}",
                    callback_data=f"machine|{index - 1}",
                )
            ]
            for index, (_, model, plate) in enumerate(EQUIPMENT, start=1)
        ]
    )


def inline_keyboard(values: list[str], prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(value, callback_data=f"{prefix}|{i}")]
            for i, value in enumerate(values)
        ]
    )


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["🚜 Новый отчет", "✏️ Изменить отчет"]],
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

    # Автоматически вычитаем 1 час обеда.
    return round(max(0, minutes - 60) / 60, 2)


def calculate_amount(data: dict[str, Any]) -> float | str:
    if data.get("multi_amount") is not None:
        return data["multi_amount"]
    if data.get("rate") == "-" or data.get("rate_type") == "-":
        return "-"
    rate_value = float(data.get("rate", 0))
    if data["rate_type"] == "За час":
        if data.get("hours") == "-":
            return "-"
        return round(rate_value * float(data["hours"]), 2)
    if data["rate_type"] == "За рейс":
        if data.get("trips") == "-":
            return "-"
        return round(rate_value * float(data["trips"]), 2)
    return round(rate_value, 2)


def calculate_amount_values(
    rate_type: str,
    rate_value: float,
    hours_value: float,
    trips_value: float,
) -> float:
    if rate_type == "За час":
        return round(rate_value * hours_value, 2)
    if rate_type == "За рейс":
        return round(rate_value * trips_value, 2)
    return round(rate_value, 2)


def pad_row(row: list[str], length: int = len(HEADERS)) -> list[str]:
    return row + [""] * max(0, length - len(row))


def report_summary(row_number: int, row: list[str]) -> str:
    row = pad_row(row)
    return (
        f"Отчёт, строка {row_number}\n\n"
        f"📅 {row[0]}\n"
        f"🚜 {row[1]} — {row[2]}\n"
        f"🔢 {row[3]}\n"
        f"👷 {row[4]}\n"
        f"📍 {row[5]}\n"
        f"🏢 {row[6] or '—'}\n"
        f"🕘 {row[7]}–{row[8]}\n"
        f"⏱ {row[9]} ч.\n"
        f"💰 {row[11]} ₽ — {row[10]}\n"
        f"🚚 Рейсы: {row[12] or '0'}\n"
        f"🧾 Сумма: {row[13]} ₽\n"
        f"💳 {row[14]}\n"
        f"📝 {row[15] or '—'}"
    )


def edit_fields_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"editfield|{key}")]
        for key, label in EDIT_FIELDS.items()
    ]
    return InlineKeyboardMarkup(buttons)


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Выберите действие:",
        reply_markup=main_keyboard(),
    )
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.effective_message.reply_text(
        "🚜 Выберите технику:",
        reply_markup=equipment_keyboard(),
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
    name, model, plate = EQUIPMENT[index]

    context.user_data["equipment_name"] = name
    context.user_data["equipment_model"] = model
    context.user_data["plate"] = plate

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
    if context.user_data.get("plate") in MULTI_OBJECT_PLATES:
        await update.message.reply_text(
            "Сколько объектов было у машины? Введите число от 1 до 4:"
        )
        return MULTI_COUNT
    await update.message.reply_text("📍 Введите адрес или название объекта:")
    return OBJECT


async def multi_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        count = int(update.message.text.strip())
        if count < 1 or count > 4:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите целое число от 1 до 4:")
        return MULTI_COUNT
    context.user_data["object_count"] = count
    context.user_data["objects"] = []
    context.user_data["current_object"] = {}
    await update.message.reply_text("📍 Введите объект 1:")
    return MULTI_OBJECT


async def multi_object(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["current_object"] = {"object": update.message.text.strip()}
    await update.message.reply_text("🏢 Введите заказчика для этого объекта или «-»:")
    return MULTI_CUSTOMER


async def multi_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["current_object"]["customer"] = "" if text == "-" else text
    await update.message.reply_text("💰 Введите ставку за рейс для этого объекта или «-»:")
    return MULTI_RATE


async def multi_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "-":
        value = "-"
    else:
        try:
            value = parse_number(text)
            if value < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите число или «-»:")
            return MULTI_RATE
    context.user_data["current_object"]["rate"] = value
    await update.message.reply_text("🚚 Введите количество рейсов по этому объекту:")
    return MULTI_TRIPS


async def multi_trips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        trips_value = parse_number(update.message.text.strip())
        if trips_value < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введите число 0 или больше:")
        return MULTI_TRIPS
    current = context.user_data["current_object"]
    current["trips"] = trips_value
    context.user_data["objects"].append(current)
    index = len(context.user_data["objects"])
    if index < context.user_data["object_count"]:
        context.user_data["current_object"] = {}
        await update.message.reply_text(f"📍 Введите объект {index + 1}:")
        return MULTI_OBJECT
    objects = context.user_data["objects"]
    context.user_data["object"] = objects[0]["object"]
    context.user_data["customer"] = objects[0]["customer"]
    context.user_data["trips"] = sum(float(item["trips"]) for item in objects)
    context.user_data["multi_amount"] = round(sum(
        (float(item["rate"]) * float(item["trips"]))
        if item["rate"] != "-" else 0
        for item in objects
    ), 2)
    await update.message.reply_text("🕘 Время начала работы или «-»:")
    return START_TIME


async def object_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["object"] = update.message.text.strip()
    await update.message.reply_text("🏢 Введите заказчика или отправьте «-»:")
    return CUSTOMER


async def customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.message.text.strip()
    context.user_data["customer"] = "" if value == "-" else value
    await update.message.reply_text("🕘 Время начала работы, например 08:00:")
    return START_TIME


async def start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text != "-" and not valid_time(text):
        await update.message.reply_text(
            "Введите время в формате ЧЧ:ММ, например 08:00, или «-»:"
        )
        return START_TIME

    context.user_data["start_time"] = text
    await update.message.reply_text("🕔 Время окончания работы, например 17:00, или «-»:")
    return END_TIME


async def end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text != "-" and not valid_time(text):
        await update.message.reply_text(
            "Введите время в формате ЧЧ:ММ, например 17:00, или «-»:"
        )
        return END_TIME

    context.user_data["end_time"] = text
    start_value = context.user_data["start_time"]
    if start_value == "-" or text == "-":
        context.user_data["hours"] = "-"
        hours_text = "-"
    else:
        context.user_data["hours"] = calculate_hours(start_value, text)
        hours_text = f"{context.user_data['hours']:g} ч. (обед 1 час вычтен)"

    await update.message.reply_text(
        f"Рабочее время: {hours_text}\n"
        "Выберите вид ставки:",
        reply_markup=inline_keyboard(RATE_TYPES, "rate"),
    )
    return RATE_TYPE


async def rate_type_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()

    index = int(query.data.split("|", 1)[1])
    context.user_data["rate_type"] = RATE_TYPES[index]
    if context.user_data["rate_type"] == "-":
        context.user_data["rate"] = "-"
        if context.user_data.get("plate") in MULTI_OBJECT_PLATES:
            await query.edit_message_text("💳 Выберите статус оплаты:", reply_markup=inline_keyboard(PAYMENT_STATUSES, "payment"))
            return PAYMENT
        await query.edit_message_text("🚚 Количество рейсов или «-»:")
        return TRIPS
    await query.edit_message_text("💰 Введите ставку числом, например 6000, или «-»:")
    return RATE


async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "-":
        value = "-"
    else:
        try:
            value = parse_number(text)
            if value <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите положительное число или «-»:")
            return RATE
    context.user_data["rate"] = value
    if context.user_data.get("plate") in MULTI_OBJECT_PLATES:
        await update.message.reply_text("💳 Выберите статус оплаты:", reply_markup=inline_keyboard(PAYMENT_STATUSES, "payment"))
        return PAYMENT
    await update.message.reply_text("🚚 Количество рейсов или «-»:")
    return TRIPS


async def trips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if text == "-":
        value = "-"
    else:
        try:
            value = parse_number(text)
            if value < 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Введите число 0 или больше либо «-»:")
            return TRIPS

    context.user_data["trips"] = value
    await update.message.reply_text(
        "💳 Выберите статус оплаты:",
        reply_markup=inline_keyboard(PAYMENT_STATUSES, "payment"),
    )
    return PAYMENT


async def payment_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()

    index = int(query.data.split("|", 1)[1])
    context.user_data["payment_status"] = PAYMENT_STATUSES[index]

    await query.edit_message_text(
        "📝 Добавьте примечание или отправьте «-»:"
    )
    return NOTE


async def note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    value = update.message.text.strip()
    context.user_data["note"] = "" if value == "-" else value
    context.user_data["amount"] = calculate_amount(context.user_data)

    d = context.user_data
    summary = (
        "Проверьте отчёт:\n\n"
        f"📅 {d['work_date']}\n"
        f"🚜 {d['equipment_name']}\n"
        f"🔧 {d['equipment_model']}\n"
        f"🔢 Гос. номер: {d['plate']}\n"
        f"👷 {d['driver']}\n"
        f"📍 {d['object']}\n"
        f"🏢 {d['customer'] or '—'}\n"
        f"🕘 {d['start_time']}–{d['end_time']}\n"
        f"⏱ Рабочее время: {d['hours']} ч.\n"
        f"💰 {d['rate']} ₽ — {d['rate_type']}\n"
        f"🚚 Рейсы всего: {d['trips']}\n"
        f"💳 {d['payment_status']}\n"
        f"🧾 Итог: {d['amount']} ₽\n"
        f"📝 {d['note'] or '—'}"
    )

    if d.get("objects"):
        details = []
        for i, item in enumerate(d["objects"], start=1):
            details.append(
                f"\nОбъект {i}: {item['object']} | "
                f"заказчик: {item['customer'] or '—'} | "
                f"ставка/рейс: {item['rate']} ₽ | рейсов: {item['trips']}"
            )
        summary += "".join(details)

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
        d["work_date"],
        d["equipment_name"],
        d["equipment_model"],
        d["plate"],
        d["driver"],
        d["object"],
        d["customer"],
        d["start_time"],
        d["end_time"],
        d["hours"],
        d["rate_type"],
        d["rate"],
        d["trips"],
        d["amount"],
        d["payment_status"],
        d["note"],
        datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        user.full_name,
        f"@{user.username}" if user.username else "",
        str(update.effective_chat.id),
    ]
    objects = d.get("objects", [])
    for i in range(4):
        item = objects[i] if i < len(objects) else {}
        if i == 0:
            row_data.extend([item.get("rate", ""), item.get("trips", "")])
        else:
            row_data.extend([
                item.get("object", ""), item.get("customer", ""),
                item.get("rate", ""), item.get("trips", ""),
            ])

    try:
        worksheet = get_worksheet()
        saved_row = save_report(worksheet, row_data)
    except Exception:
        logger.exception("Не удалось записать отчёт в Google Таблицу")
        await query.edit_message_text(
            "❌ Не удалось записать отчёт в Google Таблицу.\n\n"
            "Откройте Railway → Deployments → View logs."
        )
        return CONFIRM

    await query.edit_message_text(
        "✅ Отчёт сохранён в Google Таблицу.\n\n"
        f"Техника: {d['equipment_name']} {d['equipment_model']}\n"
        f"Гос. номер: {d['plate']}\n"
        f"Дата: {d['work_date']}\n"
        f"Рабочее время: {d['hours']} ч.\n"
        f"Сумма: {d['amount']} ₽\n"
        f"Строка таблицы: {saved_row}"
    )

    await query.message.reply_text(
        "Выберите следующее действие:",
        reply_markup=main_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def edit_report_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data.clear()

    try:
        worksheet = get_worksheet()
        rows = worksheet.get_all_values()
    except Exception:
        logger.exception("Не удалось загрузить отчёты")
        await update.effective_message.reply_text(
            "❌ Не удалось загрузить отчёты из Google Таблицы.",
            reply_markup=main_keyboard(),
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
            "В таблице пока нет отчётов для изменения.",
            reply_markup=main_keyboard(),
        )
        return ConversationHandler.END

    buttons = []
    for row_number, row in reports:
        label = f"{row[0]} | {row[2]} | {row[3]} | {row[4] or 'без водителя'}"
        buttons.append(
            [InlineKeyboardButton(label[:60], callback_data=f"editrow|{row_number}")]
        )

    await update.effective_message.reply_text(
        "Выберите отчёт для изменения.\nПоказаны последние 20 отчётов:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return EDIT_SELECT_REPORT


async def edit_report_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()

    row_number = int(query.data.split("|", 1)[1])

    try:
        worksheet = get_worksheet()
        row = worksheet.row_values(row_number)
    except Exception:
        logger.exception("Не удалось открыть отчёт")
        await query.edit_message_text("❌ Не удалось открыть выбранный отчёт.")
        return ConversationHandler.END

    if not row:
        await query.edit_message_text("Этот отчёт больше не найден.")
        return ConversationHandler.END

    context.user_data["edit_row"] = row_number

    await query.edit_message_text(
        report_summary(row_number, row) + "\n\nЧто изменить?",
        reply_markup=edit_fields_keyboard(),
    )
    return EDIT_SELECT_FIELD


async def edit_field_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()

    field = query.data.split("|", 1)[1]
    context.user_data["edit_field"] = field

    if field == "payment_status":
        await query.edit_message_text(
            "Выберите новый статус оплаты:",
            reply_markup=inline_keyboard(PAYMENT_STATUSES, "editpayment"),
        )
        return EDIT_PAYMENT

    prompts = {
        "start_time": "Введите новое время начала в формате ЧЧ:ММ:",
        "end_time": "Введите новое время окончания в формате ЧЧ:ММ:",
        "rate": "Введите новую ставку числом:",
        "trips": "Введите новое количество рейсов:",
        "object": "Введите новый объект:",
        "customer": "Введите нового заказчика или «-»:",
        "driver": "Введите имя машиниста или водителя:",
        "note": "Введите новое примечание или «-»:",
    }

    await query.edit_message_text(prompts[field])
    return EDIT_VALUE


def recalculate_row(worksheet, row_number: int) -> tuple[Any, Any]:
    row = pad_row(worksheet.row_values(row_number))

    if row[7] == "-" or row[8] == "-" or not valid_time(row[7]) or not valid_time(row[8]):
        hours_value: Any = "-"
    else:
        hours_value = calculate_hours(row[7], row[8])

    if row[3] in MULTI_OBJECT_PLATES:
        pairs = [(20, 21), (24, 25), (28, 29), (32, 33)]
        total = 0.0
        has_rate = False
        for rate_i, trips_i in pairs:
            rate_text = row[rate_i] if rate_i < len(row) else ""
            trips_text = row[trips_i] if trips_i < len(row) else ""
            if rate_text and rate_text != "-" and trips_text and trips_text != "-":
                total += parse_number(rate_text) * parse_number(trips_text)
                has_rate = True
        amount_value: Any = round(total, 2) if has_rate else "-"
    else:
        rate_type = row[10]
        rate_text = row[11]
        trips_text = row[12]
        if rate_type == "-" or rate_text == "-" or not rate_text:
            amount_value = "-"
        else:
            rate_value = parse_number(rate_text)
            trips_value = 0 if trips_text in {"", "-"} else parse_number(trips_text)
            if rate_type == "За час" and hours_value == "-":
                amount_value = "-"
            else:
                amount_value = calculate_amount_values(
                    rate_type, rate_value, float(hours_value) if hours_value != "-" else 0, trips_value
                )

    worksheet.update_cell(row_number, 10, hours_value)
    worksheet.update_cell(row_number, 14, amount_value)
    return hours_value, amount_value


async def edit_value_received(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    field = context.user_data.get("edit_field")
    row_number = context.user_data.get("edit_row")

    if not field or not row_number:
        await update.message.reply_text(
            "Сеанс изменения завершён. Нажмите «✏️ Изменить отчет» ещё раз.",
            reply_markup=main_keyboard(),
        )
        return ConversationHandler.END

    text = update.message.text.strip()

    if field in {"start_time", "end_time"} and text != "-" and not valid_time(text):
        await update.message.reply_text(
            "Неверный формат. Введите время, например 08:00:"
        )
        return EDIT_VALUE

    if field == "rate":
        if text == "-":
            value: Any = "-"
        else:
            try:
                value = parse_number(text)
                if value <= 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Введите положительное число или «-»:")
                return EDIT_VALUE
    elif field == "trips":
        if text == "-":
            value = "-"
        else:
            try:
                value = parse_number(text)
                if value < 0:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("Введите число 0 или больше либо «-»:")
                return EDIT_VALUE
    elif field in {"customer", "note"}:
        value = "" if text == "-" else text
    else:
        value = text

    try:
        worksheet = get_worksheet()
        worksheet.update_cell(row_number, COL[field], value)
        hours_value, amount_value = recalculate_row(worksheet, row_number)
        updated_row = worksheet.row_values(row_number)
    except Exception:
        logger.exception("Не удалось изменить отчёт")
        await update.message.reply_text(
            "❌ Не удалось изменить отчёт. Проверьте Railway Logs.",
            reply_markup=main_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ Отчёт изменён.\n\n"
        f"Рабочее время: {hours_value:g} ч.\n"
        f"Сумма: {amount_value:g} ₽\n\n"
        + report_summary(row_number, updated_row),
        reply_markup=main_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def edit_payment_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    await query.answer()

    row_number = context.user_data.get("edit_row")
    index = int(query.data.split("|", 1)[1])
    status = PAYMENT_STATUSES[index]

    if not row_number:
        await query.edit_message_text("Сеанс изменения завершён.")
        return ConversationHandler.END

    try:
        worksheet = get_worksheet()
        worksheet.update_cell(row_number, COL["payment_status"], status)
        updated_row = worksheet.row_values(row_number)
    except Exception:
        logger.exception("Не удалось изменить статус оплаты")
        await query.edit_message_text("❌ Не удалось изменить отчёт.")
        return ConversationHandler.END

    await query.edit_message_text(
        "✅ Статус оплаты изменён.\n\n"
        + report_summary(row_number, updated_row)
    )
    await query.message.reply_text(
        "Выберите действие:",
        reply_markup=main_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def version_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.effective_message.reply_text(
        f"Версия бота: {BOT_VERSION}\n"
        "Поддерживаются до 4 объектов и отдельные ставки за рейс."
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
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
            MessageHandler(
                filters.Regex(r"^(Новый отчет|🚜 Новый отчет)$"),
                start,
            ),
            MessageHandler(
                filters.Regex(r"^(Изменить отчет|✏️ Изменить отчет)$"),
                edit_report_start,
            ),
        ],
        states={
            MACHINE: [CallbackQueryHandler(machine_selected, pattern=r"^machine\|")],
            DATE: [CallbackQueryHandler(date_selected, pattern=r"^date\|")],
            DATE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_manual)],
            DRIVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, driver)],
            MULTI_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, multi_count)],
            MULTI_OBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, multi_object)],
            MULTI_CUSTOMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, multi_customer)],
            MULTI_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, multi_rate)],
            MULTI_TRIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, multi_trips)],
            OBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_name)],
            CUSTOMER: [MessageHandler(filters.TEXT & ~filters.COMMAND, customer)],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_time)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_time)],
            RATE_TYPE: [CallbackQueryHandler(rate_type_selected, pattern=r"^rate\|")],
            RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate)],
            TRIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, trips)],
            PAYMENT: [CallbackQueryHandler(payment_selected, pattern=r"^payment\|")],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note)],
            CONFIRM: [CallbackQueryHandler(confirm, pattern=r"^confirm\|")],
            EDIT_SELECT_REPORT: [
                CallbackQueryHandler(edit_report_selected, pattern=r"^editrow\|")
            ],
            EDIT_SELECT_FIELD: [
                CallbackQueryHandler(edit_field_selected, pattern=r"^editfield\|")
            ],
            EDIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value_received)
            ],
            EDIT_PAYMENT: [
                CallbackQueryHandler(
                    edit_payment_selected,
                    pattern=r"^editpayment\|",
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Служебная команда регистрируется в отдельной приоритетной группе,
    # чтобы она работала даже во время незавершённого диалога.
    app.add_handler(CommandHandler("version", version_command), group=-1)

    app.add_handler(conversation, group=0)
    app.add_error_handler(error_handler)
    return app


if __name__ == "__main__":
    logger.info("Запуск Telegram-бота. Версия: %s", BOT_VERSION)
    application = build_application()
    application.run_polling(drop_pending_updates=False)

import json
import logging
import os
from datetime import datetime, timedelta
import time
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
    MessageHandler,
    filters,
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_VERSION = "6.5.7-back-during-report"
TOKEN = os.environ["BOT_TOKEN"]
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID",
    "1LLEE79yZpd2o-vBXDz0Z_uHx97lgR_Eo",
)

SHEET_SPECIAL = "Спецтехника"
SHEET_DUMP = "Самосвалы"
SHEET_OSAGO = "ОСАГО"
SHEET_DIAG = "Диагностические карты"
SHEET_REFS = "Справочники"  # старая вкладка используется только для миграции
SHEET_DRIVERS = "Водители"
SHEET_OBJECTS = "Объекты"
SHEET_CUSTOMERS = "Заказчики"
SHEET_CUSTOMER_REPORT = "Поиск заказчика"
SHEET_EQUIPMENT = "Техника"
SHEET_DRIVER_MAP = "Водители техники"

SPECIAL_EQUIPMENT = [
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
    ("Самосвал", "Урал NEXT", "А 677 МА 790"),
    ("Самосвал", "Урал NEXT", "А 646 МА 790"),
    ("Самосвал", "Урал NEXT", "С 873 ВС 790"),
    ("Самосвал", "Урал NEXT", "С 918 ВС 790"),
    ("Самосвал", "Урал NEXT", "А 668 МА 790"),
    ("Манипулятор", "КамАЗ", "В 727 КН 790"),
    ("Манипулятор", "КамАЗ", "В 746 КН 790"),
    ("Манипулятор", "КамАЗ", "У 695 РУ 790"),
    ("Кран", "КамАЗ", "О 437 УС 797"),
]

DUMP_EQUIPMENT = [
    ("Самосвал шоссейный", "MAN TGS", "У 516 МС 790"),
    ("Самосвал шоссейный", "MAN TGS", "У 496 МС 790"),
    ("Самосвал шоссейный", "MAN TGS", "Х 333 ВТ 99"),
    ("Самосвал шоссейный", "MAN TGS", "С 625 ВУ 550"),
    ("Тягач", "MAN TGS", "В 777 ЕН 150"),
]

RATE_TYPES = ["За час", "За смену", "За рейс", "Фиксированная", "-"]
PAYMENT_STATUSES = ["Оплачено", "Частично", "Не оплачено", "Отсрочка"]

SPECIAL_HEADERS = [
    "Дата работы",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Машинист / водитель",
    "Заказчик",
    "Объект",
    "Начало",
    "Окончание",
    "Рабочее время, ч",
    "Вид ставки",
    "Ставка, ₽",
    "Ставка за рейс, ₽",
    "Рейс",
    "Сумма, ₽",
    "Примечание",
    "Дата и время сохранения",
    "Пользователь Telegram",
    "Username Telegram",
    "Chat ID",
]

DUMP_HEADERS = [
    "Дата работы",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Машинист / водитель",
]
for i in range(1, 5):
    DUMP_HEADERS.extend(
        [
            f"Заказчик {i}",
            f"Объект {i}",
            f"Ставка за рейс {i}, ₽",
            f"Рейсы {i}",
            f"Объём кузова {i}, м³",
            f"Общий объём {i}, м³",
        ]
    )
DUMP_HEADERS.extend(
    [
        "Всего рейсов",
        "Общий объём, м³",
        "Общая сумма, ₽",
        "Примечание",
        "Дата и время сохранения",
        "Пользователь Telegram",
        "Username Telegram",
        "Chat ID",
        "Заказчики (фильтр)",
    ]
)

OSAGO_HEADERS = [
    "№",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Дата начала",
    "Дата окончания",
    "Осталось дней",
    "Допущенные водители",
    "Статус",
    "Примечание",
]

OSAGO_EQUIPMENT = [
    ("Урал NEXT", "С 873 ВС 790"),
    ("Урал NEXT", "С 918 ВС 790"),
    ("Урал NEXT", "А 668 МА 790"),
    ("Урал NEXT", "А 677 МА 790"),
    ("Урал NEXT", "А 646 МА 790"),
    ("MAN TGS ТЯГАЧ", "В 777 ЕН 150"),
    ("MAN TGS 41.440", "У 516 МС 790"),
    ("MAN TGS 41.440", "У 496 МС 790"),
    ("MAN TGS 41.400", "Х 333 ВТ 99"),
    ("MAN TGS 41.400", "С 625 ВУ 550"),
    ("КамАЗ", "В 727 КН 790"),
    ("КамАЗ", "В 746 КН 790"),
    ("КамАЗ", "У 777 КР 190"),
    ("КамАЗ", "У 695 РУ 790"),
    ("MAN TGA", "М 999 ХЕ 93"),
    ("CAT 434E (1)", "3151 МК 50"),
    ("CAT 444Е (3)", "6314 ХЕ 50"),
    ("CAT  (4)", "1273ХН 50"),
    ("CAT 434Е (5)", "1272ХН 50"),
    ("CAT 444 (6)", "5945 ХТ 50"),
]

OSAGO_PRESET_DATES = {
    "А 668 МА 790": ("29.10.2025", "28.10.2026"),
}

DIAG_HEADERS = [
    "№",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Дата оформления",
    "Срок действия до",
    "Осталось дней",
    "Статус",
    "Примечание",
]

DIAG_EQUIPMENT = [
    ("Урал NEXT", "С 873 ВС 790"),
    ("Урал NEXT", "С 918 ВС 790"),
    ("Урал NEXT", "А 668 МА 790"),
    ("Урал NEXT", "А 677 МА 790"),
    ("Урал NEXT", "А 646 МА 790"),
    ("MAN TGS ТЯГАЧ", "В 777 ЕН 150"),
    ("MAN TGS 41.440", "У 516 МС 790"),
    ("MAN TGS 41.440", "У 496 МС 790"),
    ("MAN TGS 41.400", "Х 333 ВТ 99"),
    ("MAN TGS 41.400", "С 625 ВУ 550"),
    ("КамАЗ", "В 727 КН 790"),
    ("КамАЗ", "В 746 КН 790"),
    ("КамАЗ", "У 777 КР 190"),
    ("КамАЗ", "У 695 РУ 790"),
    ("MAN TGA", "М 999 ХЕ 93"),
]

DIAG_PRESET_DATES = {
    "А 668 МА 790": ("15.05.2026", "15.05.2027"),
}

REF_HEADERS = ["Водители", "Объекты", "Заказчики"]
REF_TITLES = {"drivers": "Водители", "objects": "Объекты", "customers": "Заказчики"}
DIRECTORY_SHEETS = {"drivers": SHEET_DRIVERS, "objects": SHEET_OBJECTS, "customers": SHEET_CUSTOMERS}
DIRECTORY_HEADERS = {"drivers": ["Водитель"], "objects": ["Объект"], "customers": ["Заказчик", "Последняя цена спецтехники, ₽", "Последняя цена самосвала, ₽"]}

CUSTOMER_REPORT_HEADERS = [
    "Дата",
    "Техника",
    "Модель",
    "Гос. номер",
    "Водитель",
    "Объект",
    "Заказчик",
    "Ставка, ₽/м³",
    "Рейсы",
    "Объём кузова, м³",
    "Общий объём, м³",
    "Сумма, ₽",
]
EQUIPMENT_HEADERS = ["Категория", "Модель", "Гос. номер"]
LEGACY_OBJECT_NAMES = {
    "земляные работы", "разработка котлована", "погрузка грунта", "вывоз грунта",
    "доставка материалов", "планировка территории", "перевозка техники",
    "работа крана", "работа манипулятора", "другое",
}


DEFAULT_DRIVER_ROWS = [
    ("CAT 434E №1", "3151 МК 50", "Сайдаев М.", "Да"),
    ("CAT 434E №3", "6314 ХЕ 50", "Сахиб Иргали", "Да"),
    ("CAT 434E №4", "1273 ХН 50", "Харитов Виталий", "Да"),
    ("CAT 444 №6", "5945 ХТ 50", "Нурматов Богдан", "Да"),
    ("CAT 330", "5106 ХХ 50", "Напрушкин Антон", "Да"),
    ("CAT 320", "9346 ХХ 50", "Гулуцу Виталий", "Да"),
    ("Hitachi 180", "1271 ХН 50", "Ситдиков Денис", "Да"),
    ("Урал NEXT", "А 646 МА 790", "Дроботенко Михаил", "Да"),
    ("Урал NEXT", "А 677 МА 790", "Турсунов Фарход", "Да"),
    ("Урал NEXT", "С 873 ВС 790", "Абезбаев Зафар", "Да"),
    ("КамАЗ", "У 695 РУ 790", "Храмков Влад", "Да"),
    ("КамАЗ", "О 437 УС 797", "Веселов Михаил", "Да"),
    ("MAN TGS", "У 516 МС 790", "Изотов Артем", "Да"),
    ("MAN TGS", "У 496 МС 790", "Рыжов Олег", "Да"),
    ("MAN TGS", "Х 333 ВТ 99", "Манаенков Алексей", "Да"),
    ("MAN TGS", "С 625 ВУ 550", "Лобов Михаил", "Да"),
    ("MAN TGS", "В 777 ЕН 150", "Нестеров Сергей", "Да"),
]
DRIVER_MAP_HEADERS = ["Модель", "Гос. номер", "Водитель", "Основной"]
_SHEET_CACHE = None
_REF_CACHE = {"drivers": None, "objects": None, "customers": None}
_DRIVER_CACHE = {}
_DIRECTORY_SHEETS = {}


def creds() -> Credentials:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
    path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    return Credentials.from_service_account_file(path, scopes=scopes)


def book():
    return gspread.authorize(creds()).open_by_key(SPREADSHEET_ID)


def col_letter(n: int) -> str:
    return gspread.utils.rowcol_to_a1(1, n).rstrip("1")


def ensure_sheet(spreadsheet, title: str, headers: list[str], rows: int = 1000):
    created = False
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=rows, cols=max(10, len(headers)))
        created = True
    if ws.col_count < len(headers):
        ws.add_cols(len(headers) - ws.col_count)
    current_headers = ws.row_values(1)
    if current_headers[:len(headers)] != headers:
        ws.update(
            f"A1:{col_letter(len(headers))}1",
            [headers],
            value_input_option="USER_ENTERED",
        )
    if created or current_headers[:len(headers)] != headers:
        ws.freeze(rows=1)
        ws.format(
            f"A1:{col_letter(len(headers))}1",
            {
                "backgroundColor": {"red": 0.08, "green": 0.28, "blue": 0.48},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
            },
        )
    return ws

def normalize_plate(value: str) -> str:
    """Нормализует госномер для сопоставления, не меняя отображаемое значение."""
    return re.sub(r"[^0-9A-ZА-ЯЁ]", "", str(value or "").upper())


def migrate_osago_sheet(ws) -> None:
    """Переводит существующую вкладку ОСАГО на новую структуру без потери нужных полей."""
    try:
        values = ws.get_all_values()
        if not values:
            return

        old_headers = [str(x).strip() for x in values[0]]
        if old_headers[:len(OSAGO_HEADERS)] == OSAGO_HEADERS:
            return

        # Если это старая версия, переносим только оставшиеся нужные поля по названиям.
        known_old = {
            "№", "Категория", "Наименование техники", "Модель", "Гос. номер",
            "Страховая компания", "Серия и номер полиса", "Дата начала",
            "Дата окончания", "Осталось дней", "Допущенные водители",
            "Ограничение", "Статус", "Примечание",
        }
        if not any(h in known_old for h in old_headers):
            return

        index = {h: i for i, h in enumerate(old_headers) if h}
        migrated = []
        for row in values[1:]:
            if not any(str(x).strip() for x in row):
                continue
            def get(name):
                i = index.get(name)
                return row[i] if i is not None and i < len(row) else ""

            migrated.append([
                get("№"),
                get("Наименование техники"),
                get("Модель"),
                get("Гос. номер"),
                get("Дата начала"),
                get("Дата окончания"),
                get("Осталось дней"),
                get("Допущенные водители"),
                get("Статус"),
                get("Примечание"),
            ])

        ws.clear()
        ws.update(
            f"A1:{col_letter(len(OSAGO_HEADERS))}1",
            [OSAGO_HEADERS],
            value_input_option="USER_ENTERED",
        )
        if migrated:
            ws.update(
                f"A2:{col_letter(len(OSAGO_HEADERS))}{len(migrated)+1}",
                migrated,
                value_input_option="USER_ENTERED",
            )
        logger.info("Вкладка ОСАГО переведена на новую структуру")
    except Exception:
        logger.exception("Не удалось мигрировать вкладку ОСАГО")


def seed_osago_equipment(ws) -> None:
    """Гарантирует наличие нужной техники в ОСАГО, не стирая введённые данные."""
    try:
        values = ws.get_all_values()
        rows = values[1:] if len(values) > 1 else []

        by_plate = {}
        for row_num, row in enumerate(rows, start=2):
            padded = row + [""] * max(0, len(OSAGO_HEADERS) - len(row))
            plate = padded[3].strip()
            if plate:
                by_plate[normalize_plate(plate)] = (row_num, padded)

        append_rows = []
        update_data = []

        for name, plate in OSAGO_EQUIPMENT:
            key = normalize_plate(plate)
            preset_start, preset_end = OSAGO_PRESET_DATES.get(plate, ("", ""))

            if key in by_plate:
                row_num, old = by_plate[key]

                if old[1] != name or old[3] != plate:
                    update_data.append({
                        "range": f"B{row_num}:D{row_num}",
                        "values": [[name, old[2], plate]],
                    })

                start_value = old[4].strip()
                end_value = old[5].strip()
                new_start = start_value or preset_start
                new_end = end_value or preset_end

                if new_start != start_value or new_end != end_value:
                    update_data.append({
                        "range": f"E{row_num}:F{row_num}",
                        "values": [[new_start, new_end]],
                    })
            else:
                append_rows.append([
                    "",
                    name,
                    "",
                    plate,
                    preset_start,
                    preset_end,
                    "",
                    "",
                    "",
                    "",
                ])

        if append_rows:
            first_row = max(len(rows) + 2, 2)
            ws.update(
                f"A{first_row}:J{first_row + len(append_rows) - 1}",
                append_rows,
                value_input_option="USER_ENTERED",
            )

        if update_data:
            ws.spreadsheet.values_batch_update({
                "valueInputOption": "USER_ENTERED",
                "data": [
                    {
                        "range": f"'{ws.title}'!{item['range']}",
                        "values": item["values"],
                    }
                    for item in update_data
                ],
            })

        logger.info(
            "ОСАГО: проверено %s единиц, добавлено %s",
            len(OSAGO_EQUIPMENT),
            len(append_rows),
        )
    except Exception:
        logger.exception("Не удалось синхронизировать парк техники ОСАГО")
        return


def migrate_diag_sheet(ws) -> None:
    """Переводит вкладку «Диагностические карты» на новую структуру."""
    try:
        values = ws.get_all_values()
        if not values:
            return

        current_headers = [str(x).strip() for x in values[0]]
        if current_headers[:len(DIAG_HEADERS)] == DIAG_HEADERS:
            return

        index = {h: i for i, h in enumerate(current_headers) if h}
        migrated = []

        for row in values[1:]:
            if not any(str(x).strip() for x in row):
                continue

            def get(*names):
                for name in names:
                    i = index.get(name)
                    if i is not None and i < len(row):
                        return row[i]
                return ""

            migrated.append([
                get("№"),
                get("Наименование техники"),
                get("Модель"),
                get("Гос. номер"),
                get("Дата оформления", "Дата выдачи"),
                get("Срок действия до", "Дата окончания", "Действует до"),
                get("Осталось дней"),
                get("Статус"),
                get("Примечание"),
            ])

        ws.clear()
        ws.update(
            f"A1:{col_letter(len(DIAG_HEADERS))}1",
            [DIAG_HEADERS],
            value_input_option="USER_ENTERED",
        )
        if migrated:
            ws.update(
                f"A2:{col_letter(len(DIAG_HEADERS))}{len(migrated)+1}",
                migrated,
                value_input_option="USER_ENTERED",
            )
        logger.info("Вкладка Диагностические карты переведена на новую структуру")
    except Exception:
        logger.exception("Не удалось мигрировать вкладку Диагностические карты")


def seed_diag_equipment(ws) -> None:
    """Гарантирует наличие техники в диагностических картах, не стирая ручные данные."""
    try:
        values = ws.get_all_values()
        rows = values[1:] if len(values) > 1 else []

        by_plate = {}
        for row_num, row in enumerate(rows, start=2):
            padded = row + [""] * max(0, len(DIAG_HEADERS) - len(row))
            plate = padded[3].strip()
            if plate:
                by_plate[normalize_plate(plate)] = (row_num, padded)

        append_rows = []
        update_data = []

        for name, plate in DIAG_EQUIPMENT:
            key = normalize_plate(plate)
            preset_issue, preset_valid_to = DIAG_PRESET_DATES.get(plate, ("", ""))

            if key in by_plate:
                row_num, old = by_plate[key]

                if old[1] != name or old[3] != plate:
                    update_data.append({
                        "range": f"B{row_num}:D{row_num}",
                        "values": [[name, old[2], plate]],
                    })

                issue_value = old[4].strip()
                valid_to_value = old[5].strip()
                new_issue = issue_value or preset_issue
                new_valid_to = valid_to_value or preset_valid_to

                if new_issue != issue_value or new_valid_to != valid_to_value:
                    update_data.append({
                        "range": f"E{row_num}:F{row_num}",
                        "values": [[new_issue, new_valid_to]],
                    })
            else:
                append_rows.append([
                    "",
                    name,
                    "",
                    plate,
                    preset_issue,
                    preset_valid_to,
                    "",
                    "",
                    "",
                ])

        if append_rows:
            first_row = max(len(rows) + 2, 2)
            ws.update(
                f"A{first_row}:I{first_row + len(append_rows) - 1}",
                append_rows,
                value_input_option="USER_ENTERED",
            )

        if update_data:
            ws.spreadsheet.values_batch_update({
                "valueInputOption": "USER_ENTERED",
                "data": [
                    {
                        "range": f"'{ws.title}'!{item['range']}",
                        "values": item["values"],
                    }
                    for item in update_data
                ],
            })

        logger.info(
            "Диагностические карты: проверено %s единиц, добавлено %s",
            len(DIAG_EQUIPMENT),
            len(append_rows),
        )
    except Exception:
        logger.exception("Не удалось синхронизировать диагностические карты")
        return


def setup_document_sheet(ws, kind: str) -> None:
    if kind == "osago":
        last_col, end_col, days_col, status_col = "J", 6, 7, 9
    else:
        last_col, end_col, days_col, status_col = "I", 6, 7, 8

    # Если формулы уже установлены, повторно сотни ячеек не переписываем.
    dcol = col_letter(days_col)
    scol = col_letter(status_col)
    existing_a2 = ws.acell("A2", value_render_option="FORMULA").value or ""
    existing_days = ws.acell(f"{dcol}2", value_render_option="FORMULA").value or ""
    existing_status = ws.acell(f"{scol}2", value_render_option="FORMULA").value or ""
    formulas_ready = all(str(x).startswith("=") for x in (existing_a2, existing_days, existing_status))

    try:
        ws.set_basic_filter(f"A1:{last_col}500")
    except Exception:
        logger.exception("Не удалось установить фильтр для %s", ws.title)

    if formulas_ready:
        return

    rows = []
    for row in range(2, 502):
        end_letter = col_letter(end_col)
        days_letter = col_letter(days_col)
        rows.append(
            [
                f'=IF(B{row}="";"";ROW()-1)',
                f'=IF({end_letter}{row}="";"";{end_letter}{row}-TODAY())',
                (
                    f'=IF({end_letter}{row}="";"Нет данных";'
                    f'IF({days_letter}{row}<0;"Просрочен";'
                    f'IF({days_letter}{row}<=30;"Заканчивается";"Действует")))'
                ),
            ]
        )

    ws.update("A2:A501", [[x[0]] for x in rows], value_input_option="USER_ENTERED")
    ws.update(f"{dcol}2:{dcol}501", [[x[1]] for x in rows], value_input_option="USER_ENTERED")
    ws.update(f"{scol}2:{scol}501", [[x[2]] for x in rows], value_input_option="USER_ENTERED")

    sheet_id = ws.id
    requests = []
    for text, color in [
        ("Действует", {"red": 0.78, "green": 0.94, "blue": 0.80}),
        ("Заканчивается", {"red": 1.0, "green": 0.93, "blue": 0.65}),
        ("Просрочен", {"red": 0.98, "green": 0.72, "blue": 0.72}),
        ("Нет данных", {"red": 0.90, "green": 0.90, "blue": 0.90}),
    ]:
        requests.append(
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [
                            {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "endRowIndex": 501,
                                "startColumnIndex": status_col - 1,
                                "endColumnIndex": status_col,
                            }
                        ],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": text}],
                            },
                            "format": {
                                "backgroundColor": color,
                                "textFormat": {"bold": True},
                            },
                        },
                    },
                    "index": 0,
                }
            }
        )
    try:
        ws.spreadsheet.batch_update({"requests": requests})
    except Exception:
        logger.exception("Не удалось добавить условное форматирование %s", ws.title)


def setup_dashboard(ws, kind: str) -> None:
    if kind == "osago":
        start_col, status_col = "L", "I"
    else:
        start_col, status_col = "K", "H"
    # Сводку переписываем при запуске, чтобы исправлять старые формулы #ERROR!.
    start_num = gspread.utils.a1_to_rowcol(start_col + "1")[1]
    required_cols = start_num + 1
    if ws.col_count < required_cols:
        ws.add_cols(required_cols - ws.col_count)
    end_col = col_letter(required_cols)
    ws.update(
        f"{start_col}1:{end_col}5",
        [
            ["Сводка", "Количество"],
            ["Всего документов", f'=COUNTIF({status_col}2:{status_col};"<>")'],
            ["Действует", f'=COUNTIF({status_col}2:{status_col};"Действует")'],
            ["Заканчивается", f'=COUNTIF({status_col}2:{status_col};"Заканчивается")'],
            ["Просрочен", f'=COUNTIF({status_col}2:{status_col};"Просрочен")'],
        ],
        value_input_option="USER_ENTERED",
    )
    ws.format(
        f"{start_col}1:{end_col}1",
        {
            "backgroundColor": {"red": 0.08, "green": 0.28, "blue": 0.48},
            "textFormat": {
                "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                "bold": True,
            },
        },
    )


def migrate_dump_remove_time_columns(ws) -> None:
    """Однократно удаляет из вкладки Самосвалы старые колонки Начало/Окончание/Рабочее время."""
    headers = ws.row_values(1)
    if len(headers) >= 8 and headers[5:8] == ["Начало", "Окончание", "Рабочее время, ч"]:
        ws.delete_columns(6, 8)
        logger.info("Во вкладке Самосвалы удалены колонки Начало, Окончание и Рабочее время")


def migrate_swap_customer_object_columns(ws, sheet_code: str) -> None:
    """Меняет местами Заказчик и Объект в уже существующих таблицах.

    Спецтехника:
      F Заказчик, G Объект

    Самосвалы:
      F Заказчик 1, G Объект 1
      L Заказчик 2, M Объект 2
      R Заказчик 3, S Объект 3
      X Заказчик 4, Y Объект 4
    """
    try:
        headers = ws.row_values(1)
        values = ws.get_all_values()
        if not values:
            return

        if sheet_code == "special":
            if len(headers) >= 7 and headers[5] == "Объект" and headers[6] == "Заказчик":
                swapped = []
                for row in values:
                    padded = row + [""] * max(0, 7 - len(row))
                    swapped.append([padded[6], padded[5]])
                ws.update(
                    f"F1:G{len(swapped)}",
                    swapped,
                    value_input_option="USER_ENTERED",
                )
                logger.info("Спецтехника: колонки Заказчик и Объект переставлены")
            return

        # Самосвалы: четыре пары. Работаем по каждой паре отдельно.
        pairs = [
            (6, "Объект 1", "Заказчик 1"),
            (12, "Объект 2", "Заказчик 2"),
            (18, "Объект 3", "Заказчик 3"),
            (24, "Объект 4", "Заказчик 4"),
        ]
        for col_1based, object_header, customer_header in pairs:
            idx = col_1based - 1
            headers = ws.row_values(1)
            if len(headers) <= idx + 1:
                continue
            if headers[idx] != object_header or headers[idx + 1] != customer_header:
                continue

            swapped = []
            for row in values:
                padded = row + [""] * max(0, idx + 2 - len(row))
                swapped.append([padded[idx + 1], padded[idx]])

            start = col_letter(col_1based)
            end = col_letter(col_1based + 1)
            ws.update(
                f"{start}1:{end}{len(swapped)}",
                swapped,
                value_input_option="USER_ENTERED",
            )

        logger.info("Самосвалы: колонки Заказчик/Объект проверены и переставлены")
    except Exception:
        logger.exception("Не удалось поменять местами Заказчик и Объект во вкладке %s", ws.title)


def migrate_price_directory_to_customers(objects_ws, customers_ws) -> None:
    """Переводит хранение последних цен полностью на заказчика.

    B — последняя цена Спецтехники.
    C — последняя цена Самосвалов.

    Старая цена заказчика из колонки B сохраняется как цена Спецтехники.
    Старая объектная цена Самосвалов удаляется, т.к. теперь цена относится к заказчику.
    """
    try:
        # Объекты больше не содержат цену.
        object_headers = objects_ws.row_values(1)
        if len(object_headers) >= 2:
            objects_ws.delete_columns(2)
        objects_ws.update(
            "A1",
            [["Объект"]],
            value_input_option="USER_ENTERED",
        )

        # Заказчики: сохраняем существующую колонку B и добавляем C.
        if customers_ws.col_count < 3:
            customers_ws.add_cols(3 - customers_ws.col_count)

        customers_ws.update(
            "A1:C1",
            [[
                "Заказчик",
                "Последняя цена спецтехники, ₽",
                "Последняя цена самосвала, ₽",
            ]],
            value_input_option="USER_ENTERED",
        )
    except Exception:
        logger.exception("Не удалось перевести хранение цен полностью на заказчиков")


def migrate_remove_payment_status(ws) -> None:
    """Удаляет старую колонку «Статус оплаты», сохраняя остальные данные."""
    headers = ws.row_values(1)
    if "Статус оплаты" in headers:
        col = headers.index("Статус оплаты") + 1
        ws.delete_columns(col)
        logger.info("Во вкладке %s удалена колонка Статус оплаты", ws.title)


def special_hours_formula(row: int) -> str:
    """Формула отработанных часов для Спецтехники.

    H = Начало, I = Окончание.
    Из общего времени смены автоматически вычитается 1 час обеда.
    MOD корректно считает смену, которая закончилась после полуночи.
    Если смена короче 1 часа, результат не уходит в минус.
    """
    return (
        f'=IF(OR(H{row}="";H{row}="-";I{row}="";I{row}="-");"-";'
        f'MAX(0;ROUND(MOD(I{row}-H{row};1)*24-1;2)))'
    )


def special_amount_formula(row: int) -> str:
    """Автоматическая сумма за смену Спецтехники.

    При ставке «За час»: Рабочее время × Ставка.
    При ставке «За рейс»: Ставка за рейс × Рейс.
    Формула пересчитывается Google Sheets при ручном изменении исходных ячеек.
    """
    return (
        f'=IF(OR(K{row}="";K{row}="-");"-";'
        f'IF(K{row}="За час";'
        f'IF(OR(L{row}="";L{row}="-";J{row}="";J{row}="-");"-";ROUND(L{row}*J{row};2));'
        f'IF(K{row}="За рейс";'
        f'IF(OR(M{row}="";M{row}="-";N{row}="";N{row}="-");"-";ROUND(M{row}*N{row};2));'
        f'IF(OR(L{row}="";L{row}="-");"-";L{row}))))'
    )


def dump_row_formulas(row: int) -> dict[int, str]:
    """Формулы Самосвалов. Ключ — номер колонки (1-based)."""
    # Заказчик/Объект занимают F:G, L:M, R:S, X:Y.
    # Ставки и расчётные колонки остаются H:K, N:Q, T:W, Z:AC.
    formulas = {}
    blocks = [(8, 9, 10, 11), (14, 15, 16, 17), (20, 21, 22, 23), (26, 27, 28, 29)]
    for rate_col, trips_col, body_col, total_col in blocks:
        r = col_letter(trips_col)
        b = col_letter(body_col)
        formulas[total_col] = (
            f'=IF(OR({r}{row}="";{r}{row}="-";{b}{row}="";{b}{row}="-");"-";'
            f'{r}{row}*{b}{row})'
        )

    formulas[30] = (
        f'=IF(COUNTA(I{row};O{row};U{row};AA{row})=0;"-";'
        f'SUM(I{row};O{row};U{row};AA{row}))'
    )
    formulas[31] = (
        f'=IF(COUNTA(K{row};Q{row};W{row};AC{row})=0;"-";'
        f'SUM(K{row};Q{row};W{row};AC{row}))'
    )
    formulas[32] = (
        f'=IF(COUNTA(H{row};N{row};T{row};Z{row})=0;"-";'
        f'IFERROR(K{row}*H{row};0)+IFERROR(Q{row}*N{row};0)+'
        f'IFERROR(W{row}*T{row};0)+IFERROR(AC{row}*Z{row};0))'
    )
    return formulas


def remove_google_sheets_tables_keep_data(ws) -> None:
    """Убирает объект Google Sheets «Таблица», сохраняя данные и формулы.

    Меню вида «Изменить тип столбца / Столбец для фильтра» относится к новой
    сущности Google Sheets Table. Оно не является классическим BasicFilter.
    Чтобы получить обычное меню фильтра по значениям, таблица преобразуется
    обратно в обычный диапазон, после чего ставится BasicFilter.
    """
    try:
        sp = ws.spreadsheet

        # Получаем метаданные листов, включая Tables.
        metadata = None
        params = {
            "fields": "sheets(properties(sheetId,title),tables(tableId,name,range))"
        }

        client = getattr(sp, "client", None)
        http_client = getattr(client, "http_client", None)

        if http_client is not None and hasattr(http_client, "fetch_sheet_metadata"):
            metadata = http_client.fetch_sheet_metadata(sp.id, params=params)
        elif client is not None and hasattr(client, "fetch_sheet_metadata"):
            metadata = client.fetch_sheet_metadata(sp.id, params=params)
        elif hasattr(sp, "fetch_sheet_metadata"):
            metadata = sp.fetch_sheet_metadata(params=params)

        if not metadata:
            logger.info("Метаданные Tables для %s недоступны; пропускаем удаление Table", ws.title)
            return

        sheet_meta = None
        for sheet in metadata.get("sheets", []):
            props = sheet.get("properties", {})
            if props.get("sheetId") == ws.id:
                sheet_meta = sheet
                break

        tables = (sheet_meta or {}).get("tables", [])
        if not tables:
            logger.info("На листе %s объектов Google Sheets Table нет", ws.title)
            return

        # Сохраняем значения именно как формулы, чтобы не потерять расчёты.
        last_col = col_letter(max(1, ws.col_count))
        last_row = max(1, ws.row_count)
        save_range = f"A1:{last_col}{last_row}"

        try:
            snapshot = ws.get(
                save_range,
                value_render_option="FORMULA",
            )
        except Exception:
            # Совместимость со старыми версиями gspread.
            snapshot = ws.get_all_values()

        delete_requests = [
            {"deleteTable": {"tableId": table["tableId"]}}
            for table in tables
            if table.get("tableId")
        ]

        if not delete_requests:
            return

        # DeleteTable удаляет также содержимое таблицы, поэтому после запроса
        # сразу возвращаем сохранённые значения/формулы.
        sp.batch_update({"requests": delete_requests})

        if snapshot:
            row_count = len(snapshot)
            col_count = max((len(r) for r in snapshot), default=1)
            normalized = [
                list(r) + [""] * (col_count - len(r))
                for r in snapshot
            ]
            restore_range = f"A1:{col_letter(col_count)}{row_count}"
            ws.update(
                restore_range,
                normalized,
                value_input_option="USER_ENTERED",
            )

        logger.info(
            "На листе %s удалено Google Sheets Tables: %s; данные восстановлены",
            ws.title,
            len(delete_requests),
        )

    except Exception:
        logger.exception(
            "Не удалось преобразовать Google Sheets Table в обычный диапазон на %s",
            ws.title,
        )


def ensure_standard_value_filter(ws, headers: list[str]) -> None:
    """Гарантированно включает обычный фильтр Google Sheets на всю таблицу.

    Это именно фильтр с выпадающим меню в заголовках:
    сортировка, фильтр по условию, фильтр по значению, поиск и галочки.
    """
    try:
        # Если лист оформлен как новая Google Sheets «Таблица», сначала
        # преобразуем её обратно в обычный диапазон.
        remove_google_sheets_tables_keep_data(ws)

        # Работаем строго в пределах реального размера листа.
        last_col = col_letter(len(headers))
        last_row = max(2, ws.row_count)

        # Сначала удаляем старый basic filter отдельным запросом.
        try:
            ws.spreadsheet.batch_update(
                {"requests": [{"clearBasicFilter": {"sheetId": ws.id}}]}
            )
        except Exception:
            # Если фильтра не было, это не должно мешать дальнейшей установке.
            logger.info("На листе %s старого basic filter не было", ws.title)

        # gspread сам формирует корректный BasicFilter.
        ws.set_basic_filter(f"A1:{last_col}{last_row}")

        # Закрепляем строку заголовков.
        ws.freeze(rows=1, cols=5)

        logger.info(
            "Стандартный выпадающий фильтр включён на %s: A1:%s%s",
            ws.title,
            last_col,
            last_row,
        )
    except Exception:
        logger.exception(
            "Не удалось включить стандартный выпадающий фильтр на %s",
            ws.title,
        )


def style_special_sheet(ws) -> None:
    """Оформляет вкладку Спецтехника и включает фильтр по каждой колонке."""
    try:
        last_col = col_letter(len(SPECIAL_HEADERS))
        last_row = max(ws.row_count, 1000)

        ws.freeze(rows=1, cols=5)

        # Стандартный фильтр будет установлен отдельно после полного оформления листа.

        # Общий аккуратный вид таблицы.
        ws.format(
            f"A1:{last_col}{last_row}",
            {
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
                "borders": {
                    "top": {"style": "SOLID", "color": {"red": 0.86, "green": 0.88, "blue": 0.91}},
                    "bottom": {"style": "SOLID", "color": {"red": 0.86, "green": 0.88, "blue": 0.91}},
                    "left": {"style": "SOLID", "color": {"red": 0.86, "green": 0.88, "blue": 0.91}},
                    "right": {"style": "SOLID", "color": {"red": 0.86, "green": 0.88, "blue": 0.91}},
                },
            },
        )

        # Шапка.
        ws.format(
            f"A1:{last_col}1",
            {
                "backgroundColor": {"red": 0.04, "green": 0.24, "blue": 0.43},
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

        # Поля с числами и временем.
        ws.format("A2:A", {"horizontalAlignment": "CENTER"})
        ws.format("D2:D", {"horizontalAlignment": "CENTER"})
        ws.format("H2:J", {"horizontalAlignment": "CENTER"})
        ws.format("K2:O", {"horizontalAlignment": "RIGHT"})

        # Денежные столбцы.
        for col in ("L", "M", "O"):
            ws.format(
                f"{col}2:{col}",
                {
                    "numberFormat": {
                        "type": "NUMBER",
                        "pattern": '#,##0.00 "₽"',
                    }
                },
            )

        # Удобные ширины столбцов.
        widths = {
            0: 105,  # дата
            1: 155,  # техника
            2: 115,  # модель
            3: 120,  # госномер
            4: 160,  # водитель
            5: 180,  # заказчик
            6: 190,  # объект
            7: 80, 8: 80, 9: 105,
            10: 110, 11: 105, 12: 125, 13: 75, 14: 120,
            15: 180, 16: 145, 17: 140, 18: 135, 19: 110,
        }
        requests = []
        for index, width in widths.items():
            requests.append(
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": ws.id,
                            "dimension": "COLUMNS",
                            "startIndex": index,
                            "endIndex": index + 1,
                        },
                        "properties": {"pixelSize": width},
                        "fields": "pixelSize",
                    }
                }
            )

        # Высота шапки.
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": 1,
                    },
                    "properties": {"pixelSize": 44},
                    "fields": "pixelSize",
                }
            }
        )

        ws.spreadsheet.batch_update({"requests": requests})
        logger.info("Вкладка Спецтехника оформлена; фильтр включён для всех колонок")
    except Exception:
        logger.exception("Не удалось оформить вкладку Спецтехника")


def apply_ruble_format(ws, header_name: str) -> None:
    """Форматирует денежную колонку как российские рубли."""
    try:
        headers = ws.row_values(1)
        if header_name not in headers:
            return

        col = headers.index(header_name) + 1
        letter = col_letter(col)

        ws.format(
            f"{letter}2:{letter}{ws.row_count}",
            {
                "numberFormat": {
                    "type": "NUMBER",
                    "pattern": '#,##0.00 "₽"',
                },
                "horizontalAlignment": "RIGHT",
            },
        )
        logger.info(
            "Во вкладке %s колонка %s отформатирована в рублях",
            ws.title,
            header_name,
        )
    except Exception:
        logger.exception(
            "Не удалось применить рублёвый формат во вкладке %s",
            ws.title,
        )


def apply_report_formulas(special, dump) -> None:
    """Ставит формулы только на существующие строки отчётов."""
    try:
        # Формулы Спецтехники ставим с запасом, чтобы ручные изменения в таблице
        # пересчитывались без участия Telegram-бота.
        special_formula_last_row = min(max(special.row_count, 1000), 5000)

        hours_formulas = [[special_hours_formula(r)] for r in range(2, special_formula_last_row + 1)]
        amount_formulas = [[special_amount_formula(r)] for r in range(2, special_formula_last_row + 1)]

        special.update(
            f"J2:J{special_formula_last_row}",
            hours_formulas,
            value_input_option="USER_ENTERED",
        )
        special.update(
            f"O2:O{special_formula_last_row}",
            amount_formulas,
            value_input_option="USER_ENTERED",
        )

        d_rows = dump.get_all_values()
        if len(d_rows) > 1:
            # 7 производных колонок: K,Q,W,AC,AD,AE,AF.
            columns = {11: [], 17: [], 23: [], 29: [], 30: [], 31: [], 32: []}
            for r in range(2, len(d_rows) + 1):
                f = dump_row_formulas(r)
                for c in columns:
                    columns[c].append([f[c]])
            for c, values in columns.items():
                letter = col_letter(c)
                dump.update(
                    f"{letter}2:{letter}{len(d_rows)}",
                    values,
                    value_input_option="USER_ENTERED",
                )
    except Exception:
        logger.exception("Не удалось установить формулы отчётов")


def build_customer_filter_text(objects: list[dict[str, Any]]) -> str:
    """Собирает уникальных заказчиков отчёта в одну строку для фильтра."""
    result = []
    seen = set()
    for item in objects:
        customer = str(item.get("customer", "") or "").strip()
        key = normalize(customer)
        if customer and key not in seen:
            result.append(customer)
            seen.add(key)
    return " | ".join(result)


def setup_dump_customer_filter(ws, customers_ws=None) -> None:
    """Настраивает отдельный фильтр для каждого заказчика.

    В служебной колонке «Заказчики (фильтр)» хранится обычный текст со всеми
    заказчиками строки. Дополнительно создаются отдельные Filter Views Google
    Sheets с названиями «Заказчик: <название>». Каждый такой фильтр показывает
    все строки, где встречается именно выбранный заказчик — независимо от того,
    записан он как Заказчик 1, 2, 3 или 4.
    """
    helper_col = len(DUMP_HEADERS)
    helper_letter = col_letter(helper_col)

    try:
        # Чтобы Гос. номер (D) и Машинист/водитель (E) оставались видимы,
        # Google Sheets требует закрепить непрерывный диапазон слева A:E.
        ws.freeze(rows=1, cols=5)
        rows = ws.get_all_values()

        # Заполняем служебную колонку для уже существующих отчетов.
        # После удаления колонок времени:
        # F(6), L(12), R(18), X(24) = Заказчик 1..4.
        if len(rows) > 1:
            values = []
            changed = False
            for row in rows[1:]:
                padded = row + [""] * max(0, helper_col - len(row))
                customers = []
                seen = set()

                for idx in (5, 11, 17, 23):
                    customer = padded[idx].strip() if idx < len(padded) else ""
                    key = normalize(customer)
                    if customer and key not in seen:
                        customers.append(customer)
                        seen.add(key)

                text = " | ".join(customers)
                old_value = padded[helper_col - 1].strip() if len(padded) >= helper_col else ""
                values.append([text])
                if old_value != text:
                    changed = True

            if changed:
                ws.update(
                    f"{helper_letter}2:{helper_letter}{len(rows)}",
                    values,
                    value_input_option="USER_ENTERED",
                )

        # Filter Views создаём отдельно.
        # Обычный выпадающий basic filter ставится после этой функции отдельным запросом,
        # чтобы ошибка одного Filter View не могла убрать фильтр из заголовков.
        requests = []

        # Получаем сохраненных заказчиков.
        customers = []
        if customers_ws is not None:
            for value in customers_ws.col_values(1)[1:]:
                value = " ".join((value or "").strip().split())
                if value and normalize(value) not in {normalize(x) for x in customers}:
                    customers.append(value)

        # Удаляем старые созданные ботом Filter Views, чтобы не плодить дубли.
        try:
            metadata = ws.spreadsheet.fetch_sheet_metadata()
            for sheet_meta in metadata.get("sheets", []):
                props = sheet_meta.get("properties", {})
                if props.get("sheetId") != ws.id:
                    continue
                for view in sheet_meta.get("filterViews", []) or []:
                    title = (view.get("title") or "").strip()
                    if title.startswith("Заказчик: "):
                        requests.append(
                            {"deleteFilterView": {"filterId": view["filterViewId"]}}
                        )
        except Exception:
            logger.exception("Не удалось прочитать существующие Filter Views")

        # Создаем отдельное представление для каждого заказчика.
        # Критерий применяется к служебной колонке и ищет точное имя как часть текста.
        for customer in customers:
            requests.append(
                {
                    "addFilterView": {
                        "filter": {
                            "title": f"Заказчик: {customer}"[:100],
                            "range": {
                                "sheetId": ws.id,
                                "startRowIndex": 0,
                                "endRowIndex": ws.row_count,
                                "startColumnIndex": 0,
                                "endColumnIndex": len(DUMP_HEADERS),
                            },
                            "criteria": {
                                str(helper_col - 1): {
                                    "condition": {
                                        "type": "TEXT_CONTAINS",
                                        "values": [{"userEnteredValue": customer}],
                                    }
                                }
                            },
                        }
                    }
                }
            )

        # Filter Views отправляем отдельно от основного фильтра.
        if requests:
            ws.spreadsheet.batch_update({"requests": requests})
        logger.info(
            "Созданы индивидуальные фильтры заказчиков: %s",
            len(customers),
        )
    except Exception:
        logger.exception("Не удалось настроить индивидуальные фильтры заказчиков")


def _initialize_sheets_once(force: bool = False):
    global _SHEET_CACHE, _DIRECTORY_SHEETS
    if _SHEET_CACHE is not None and not force:
        return _SHEET_CACHE

    sp = book()
    titles = [ws.title for ws in sp.worksheets()]
    if "Отчеты" in titles and SHEET_SPECIAL not in titles:
        sp.worksheet("Отчеты").update_title(SHEET_SPECIAL)

    try:
        special_existing = sp.worksheet(SHEET_SPECIAL)
        migrate_swap_customer_object_columns(special_existing, "special")
        migrate_remove_payment_status(special_existing)
    except gspread.WorksheetNotFound:
        pass
    special = ensure_sheet(sp, SHEET_SPECIAL, SPECIAL_HEADERS)

    try:
        dump_existing = sp.worksheet(SHEET_DUMP)
        migrate_dump_remove_time_columns(dump_existing)
        migrate_swap_customer_object_columns(dump_existing, "dump")
        migrate_remove_payment_status(dump_existing)
    except gspread.WorksheetNotFound:
        pass
    dump = ensure_sheet(sp, SHEET_DUMP, DUMP_HEADERS)
    apply_report_formulas(special, dump)
    apply_ruble_format(special, "Сумма, ₽")
    apply_ruble_format(dump, "Общая сумма, ₽")

    try:
        osago_existing = sp.worksheet(SHEET_OSAGO)
        migrate_osago_sheet(osago_existing)
    except gspread.WorksheetNotFound:
        pass

    osago = ensure_sheet(sp, SHEET_OSAGO, OSAGO_HEADERS, 600)
    seed_osago_equipment(osago)

    try:
        diag_existing = sp.worksheet(SHEET_DIAG)
        migrate_diag_sheet(diag_existing)
    except gspread.WorksheetNotFound:
        pass

    diag = ensure_sheet(sp, SHEET_DIAG, DIAG_HEADERS, 600)
    seed_diag_equipment(diag)
    drivers_ws = ensure_sheet(sp, SHEET_DRIVERS, DIRECTORY_HEADERS["drivers"], 500)

    # Сначала открываем справочники, затем корректируем старую структуру цен.
    try:
        objects_existing = sp.worksheet(SHEET_OBJECTS)
    except gspread.WorksheetNotFound:
        objects_existing = None
    try:
        customers_existing = sp.worksheet(SHEET_CUSTOMERS)
    except gspread.WorksheetNotFound:
        customers_existing = None

    objects_ws = ensure_sheet(sp, SHEET_OBJECTS, DIRECTORY_HEADERS["objects"], 500)
    customers_ws = ensure_sheet(sp, SHEET_CUSTOMERS, DIRECTORY_HEADERS["customers"], 500)
    migrate_price_directory_to_customers(objects_ws, customers_ws)
    apply_ruble_format(customers_ws, "Последняя цена спецтехники, ₽")
    apply_ruble_format(customers_ws, "Последняя цена самосвала, ₽")

    style_special_sheet(special)
    setup_dump_customer_filter(dump, customers_ws)

    # ВАЖНО: ставим обычные фильтры последними, после оформления и Filter Views.
    # Тогда в каждой колонке заголовка появляется выпадающее меню Google Sheets.
    ensure_standard_value_filter(special, SPECIAL_HEADERS)
    ensure_standard_value_filter(dump, DUMP_HEADERS)
    equipment_ws = ensure_sheet(sp, SHEET_EQUIPMENT, EQUIPMENT_HEADERS, 200)
    driver_map = ensure_sheet(sp, SHEET_DRIVER_MAP, DRIVER_MAP_HEADERS, 300)
    _DIRECTORY_SHEETS = {"drivers": drivers_ws, "objects": objects_ws, "customers": customers_ws}

    # Документные вкладки оформляем только один раз за процесс.
    setup_document_sheet(osago, "osago")
    setup_dashboard(osago, "osago")
    setup_document_sheet(diag, "diag")
    setup_dashboard(diag, "diag")

    # Список техники заполняется один раз.
    if len(equipment_ws.get_all_values()) <= 1:
        equipment_rows = [list(x) for x in (SPECIAL_EQUIPMENT + DUMP_EQUIPMENT)]
        equipment_ws.update(
            f"A2:C{len(equipment_rows)+1}", equipment_rows, value_input_option="USER_ENTERED"
        )

    # Привязки водителей заполняются один раз.
    if len(driver_map.get_all_values()) <= 1:
        driver_map.update(
            f"A2:D{len(DEFAULT_DRIVER_ROWS)+1}",
            [list(row) for row in DEFAULT_DRIVER_ROWS],
            value_input_option="USER_ENTERED",
        )

    # Миграция старой вкладки «Справочники» в отдельные вкладки.
    if SHEET_REFS in titles:
        old_refs = sp.worksheet(SHEET_REFS)
        old_rows = old_refs.get_all_values()
        for kind, col_idx in (("drivers", 0), ("objects", 1), ("customers", 2)):
            current = {normalize(v) for v in _DIRECTORY_SHEETS[kind].col_values(1)[1:] if v.strip()}
            additions = []
            for row in old_rows[1:]:
                if len(row) <= col_idx or not row[col_idx].strip():
                    continue
                value = " ".join(row[col_idx].strip().split())
                if kind == "objects" and normalize(value) in LEGACY_OBJECT_NAMES:
                    continue
                if normalize(value) not in current:
                    additions.append([value]); current.add(normalize(value))
            if additions:
                first = first_empty_row(_DIRECTORY_SHEETS[kind], 1)
                _DIRECTORY_SHEETS[kind].update(
                    f"A{first}:A{first+len(additions)-1}", additions, value_input_option="USER_ENTERED"
                )

    # Базовые водители добавляются в отдельную вкладку одним запросом.
    existing = {normalize(v) for v in drivers_ws.col_values(1)[1:] if v.strip()}
    missing = [[row[2]] for row in DEFAULT_DRIVER_ROWS if normalize(row[2]) not in existing]
    if missing:
        first = first_empty_row(drivers_ws, 1)
        drivers_ws.update(
            f"A{first}:A{first+len(missing)-1}", missing, value_input_option="USER_ENTERED"
        )

    _SHEET_CACHE = (special, dump, None, driver_map)
    return _SHEET_CACHE


def initialize_sheets(force: bool = False):
    """Инициализация Google Sheets с повторами при временной ошибке API."""
    last_exc = None
    for attempt in range(1, 4):
        try:
            return _initialize_sheets_once(force=force)
        except Exception as exc:
            last_exc = exc
            text = str(exc)
            retryable = (
                "429" in text
                or "Quota exceeded" in text
                or "RESOURCE_EXHAUSTED" in text
                or "503" in text
                or "500" in text
            )
            logger.exception(
                "Ошибка Google Sheets при инициализации, попытка %s/3",
                attempt,
            )
            if not retryable or attempt == 3:
                raise
            time.sleep(20 * attempt)
    raise last_exc


def first_empty_row(ws, column: int = 1) -> int:
    values = ws.col_values(column)
    return max(2, len(values) + 1)


def save_row(ws, row: list[Any]) -> int:
    n = first_empty_row(ws, 1)
    ws.update(
        f"A{n}:{col_letter(len(row))}{n}",
        [row],
        value_input_option="USER_ENTERED",
    )
    return n


def normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def ref_values(kind: str) -> list[str]:
    cached = _REF_CACHE.get(kind)
    if cached is not None:
        return list(cached)
    initialize_sheets()
    ws = _DIRECTORY_SHEETS[kind]
    values = [v.strip() for v in ws.col_values(1)[1:] if v.strip()]
    if kind == "objects":
        values = [v for v in values if normalize(v) not in LEGACY_OBJECT_NAMES]
    # Удаляем дубли, сохраняя порядок.
    result, seen = [], set()
    for v in values:
        key = normalize(v)
        if key not in seen:
            result.append(v); seen.add(key)
    _REF_CACHE[kind] = result
    return list(result)


def search_ref_values(kind: str, query: str, limit: int = 12) -> list[str]:
    q = normalize(query)
    if not q:
        return []
    values = ref_values(kind)
    exact = [v for v in values if normalize(v) == q]
    starts = [v for v in values if normalize(v).startswith(q) and normalize(v) != q]
    contains = [v for v in values if q in normalize(v) and not normalize(v).startswith(q)]
    return (exact + starts + contains)[:limit]


def add_ref(kind: str, value: str) -> tuple[bool, str]:
    value = " ".join(value.strip().split())
    if not value:
        return False, "Пустое значение нельзя добавить."
    if kind == "objects" and normalize(value) in LEGACY_OBJECT_NAMES:
        return False, "Это название относится к старому списку видов работ и не может быть объектом."
    values = ref_values(kind)
    if normalize(value) in {normalize(v) for v in values}:
        return False, "Такая запись уже существует."
    initialize_sheets()
    ws = _DIRECTORY_SHEETS[kind]
    row = first_empty_row(ws, 1)
    ws.update_cell(row, 1, value)
    _REF_CACHE[kind] = None
    return True, value


def parse_price_value(value: Any) -> float | None:
    """Преобразует цену из Google Sheets в число.

    Поддерживает как сырые числа, так и отображаемые значения вида:
    3 125,00 ₽ / 3125.00 / 3 125 ₽.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text == "-":
        return None

    # Убираем рубль, обычные/неразрывные пробелы и прочие символы,
    # оставляя цифры, минус и разделители.
    text = text.replace("\xa0", "").replace(" ", "").replace("₽", "")
    text = re.sub(r"[^0-9,.\-]", "", text)

    if not text:
        return None

    # Для русской записи 3.125,50: точки тысяч убираем, запятую делаем точкой.
    if "," in text:
        if "." in text and text.rfind(",") > text.rfind("."):
            text = text.replace(".", "")
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        # На случай 3.125.500
        text = text.replace(".", "")

    try:
        return float(text)
    except ValueError:
        return None


def get_customer_price(customer_name: str, category: str = "special") -> float | None:
    """Возвращает последнюю цену заказчика для нужной категории."""
    initialize_sheets()
    ws = _DIRECTORY_SHEETS["customers"]
    target = normalize(customer_name)
    price_col = 1 if category == "special" else 2  # B или C, zero-based

    # ВАЖНО: читаем сырые значения. Иначе денежный формат возвращает
    # текст вида «3 125,00 ₽», который раньше не распознавался как число.
    try:
        rows = ws.get_all_values(value_render_option="UNFORMATTED_VALUE")
    except TypeError:
        rows = ws.get_all_values()

    for row in rows[1:]:
        if row and normalize(row[0]) == target:
            if len(row) <= price_col:
                return None
            return parse_price_value(row[price_col])

    return None


def set_customer_price(customer_name: str, price: float, category: str = "special") -> None:
    """Надёжно сохраняет последнюю цену заказчика."""
    initialize_sheets()
    ws = _DIRECTORY_SHEETS["customers"]
    target = normalize(customer_name)
    sheet_col = 2 if category == "special" else 3

    numeric_price = float(price)

    try:
        rows = ws.get_all_values(value_render_option="UNFORMATTED_VALUE")
    except TypeError:
        rows = ws.get_all_values()

    target_row = None
    for row_num, row in enumerate(rows[1:], start=2):
        if row and normalize(row[0]) == target:
            target_row = row_num
            break

    if target_row is None:
        target_row = first_empty_row(ws, 1)
        values = [customer_name, "", ""]
        values[sheet_col - 1] = numeric_price
        ws.update(
            f"A{target_row}:C{target_row}",
            [values],
            value_input_option="USER_ENTERED",
        )
    else:
        # Пишем только ячейку цены, не затрагивая вторую категорию.
        ws.update(
            f"{col_letter(sheet_col)}{target_row}",
            [[numeric_price]],
            value_input_option="USER_ENTERED",
        )

    # Сбрасываем только кэш списка; данные Google Sheets остаются источником истины.
    _REF_CACHE["customers"] = None

    # Контрольное чтение. Не даём ошибке проверки сломать отчёт,
    # но пишем в лог, если Google не вернул сохранённое значение.
    try:
        saved = ws.cell(target_row, sheet_col).value
        parsed = parse_price_value(saved)
        if parsed is None or abs(parsed - numeric_price) > 0.001:
            logger.warning(
                "Цена заказчика могла не сохраниться: %s, категория=%s, ожидалось=%s, получено=%r",
                customer_name,
                category,
                numeric_price,
                saved,
            )
        else:
            logger.info(
                "Цена заказчика сохранена: %s, категория=%s, цена=%s",
                customer_name,
                category,
                numeric_price,
            )
    except Exception:
        logger.exception("Не удалось проверить сохранение цены заказчика")


async def prompt_dump_customer_price(message, context: ContextTypes.DEFAULT_TYPE):
    """Предлагает последнюю цену выбранного заказчика при отчёте Самосвалов."""
    d = context.user_data
    current = d["current"]
    customer = current.get("customer", "")
    saved = get_customer_price(customer, "dump")
    current["saved_price"] = saved

    if saved is None:
        d["step"] = "dump_rate"
        await message.reply_text("Введите ставку для этого заказчика или «-»:")
        return

    await message.reply_text(
        f"Для заказчика «{customer}» последняя цена Самосвалов: {saved:g} ₽.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"✅ Использовать {saved:g} ₽",
                        callback_data="dumpcustprice|use",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✏️ Изменить цену",
                        callback_data="dumpcustprice|change",
                    )
                ],
            ]
        ),
    )


async def prompt_dump_object_price(message, context: ContextTypes.DEFAULT_TYPE):
    """Совместимость: цена Самосвалов теперь хранится у заказчика."""
    await prompt_dump_customer_price(message, context)


async def prompt_special_price(message, context: ContextTypes.DEFAULT_TYPE):
    """Предлагает сохранённую цену заказчика либо ввод новой."""
    d = context.user_data
    saved = get_customer_price(d.get("customer", ""))
    if d.get("rate_type") == "-":
        d["rate"] = "-"
        d["rate_trip"] = "-"
        d["trips"] = "-"
        d["step"] = "note"
        await message.reply_text("Введите примечание или «-»:")
        return

    d["saved_customer_price"] = saved
    if saved is not None:
        await message.reply_text(
            f"Для заказчика «{d['customer']}» последняя цена Спецтехники: {saved:g} ₽.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(f"✅ Использовать {saved:g} ₽", callback_data="custprice|use")],
                    [InlineKeyboardButton("✏️ Изменить цену", callback_data="custprice|change")],
                ]
            ),
        )
    else:
        d["step"] = "rate_trip" if d["rate_type"] == "За рейс" else "rate"
        text = "Введите ставку за рейс или «-»:" if d["rate_type"] == "За рейс" else "Введите ставку или «-»:"
        await message.reply_text(text)


def delete_ref(kind: str, index: int) -> str:
    values = ref_values(kind)
    if index < 0 or index >= len(values):
        raise ValueError("Запись не найдена")
    initialize_sheets()
    ws = _DIRECTORY_SHEETS[kind]
    target = values[index]
    column_values = ws.col_values(1)
    for row, item in enumerate(column_values[1:], start=2):
        if normalize(item) == normalize(target):
            ws.update_cell(row, 1, "")
            _REF_CACHE[kind] = None
            return target
    raise ValueError("Запись не найдена")

def drivers_for_plate(plate: str) -> list[tuple[str, bool]]:
    if plate in _DRIVER_CACHE:
        return list(_DRIVER_CACHE[plate])
    _, _, _, driver_map = initialize_sheets()
    rows = driver_map.get_all_values()[1:]
    result = []
    for row in rows:
        if len(row) >= 3 and normalize(row[1]) == normalize(plate):
            result.append((row[2].strip(), len(row) > 3 and normalize(row[3]) == normalize("Да")))
    result.sort(key=lambda x: (not x[1], x[0]))
    _DRIVER_CACHE[plate] = result
    return list(result)


def add_driver_for_plate(model: str, plate: str, driver: str, primary: bool = False) -> tuple[bool, str]:
    driver = " ".join(driver.strip().split())
    if not driver:
        return False, "Пустое имя нельзя добавить."
    existing = drivers_for_plate(plate)
    if normalize(driver) in {normalize(x[0]) for x in existing}:
        return False, "Этот водитель уже привязан к технике."
    _, _, _, driver_map = initialize_sheets()
    row = first_empty_row(driver_map, 1)
    driver_map.update(
        f"A{row}:D{row}",
        [[model, plate, driver, "Да" if primary or not existing else "Нет"]],
        value_input_option="USER_ENTERED",
    )
    _DRIVER_CACHE.pop(plate, None)
    add_ref("drivers", driver)
    return True, driver


def remove_driver_for_plate(plate: str, driver: str) -> tuple[bool, str]:
    """Удаляет привязку водителя к конкретной технике, не удаляя его из общего справочника."""
    _, _, _, driver_map = initialize_sheets()
    rows = driver_map.get_all_values()
    target_plate = normalize(plate)
    target_driver = normalize(driver)

    for row_num, row in enumerate(rows[1:], start=2):
        if len(row) >= 3 and normalize(row[1]) == target_plate and normalize(row[2]) == target_driver:
            driver_map.delete_rows(row_num)
            _DRIVER_CACHE.pop(plate, None)

            # Если после удаления остались водители, а основного нет — первого делаем основным.
            remaining = drivers_for_plate(plate)
            if remaining and not any(primary for _, primary in remaining):
                for rn, r in enumerate(driver_map.get_all_values()[1:], start=2):
                    if len(r) >= 3 and normalize(r[1]) == target_plate:
                        driver_map.update_cell(rn, 4, "Да")
                        _DRIVER_CACHE.pop(plate, None)
                        break

            return True, driver

    return False, "Привязка водителя к этой технике не найдена."


async def show_driver_management(message, context: ContextTypes.DEFAULT_TYPE):
    """Показывает управление водителями, закреплёнными за выбранной техникой."""
    d = context.user_data
    assigned = drivers_for_plate(d["plate"])
    rows = []

    for index, (name, primary) in enumerate(assigned):
        prefix = "✅ " if primary else ""
        rows.append([
            InlineKeyboardButton(
                f"❌ Удалить: {prefix}{name}",
                callback_data=f"driverdelete|{index}",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "👷 Назначить из общего списка",
            callback_data="driverassignexisting|0",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            "➕ Добавить нового водителя",
            callback_data="driveraddmachine|0",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            "⬅️ Назад к выбору водителя",
            callback_data="driverback|0",
        )
    ])

    text = f"Водители для {d['model']} — {d['plate']}:"
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))



def get_previous_special_report(work_date: str, plate: str) -> dict[str, Any] | None:
    """Ищет последний отчёт этой техники за предыдущий календарный день."""
    try:
        selected = datetime.strptime(work_date, "%d.%m.%Y")
        previous_date = (selected - timedelta(days=1)).strftime("%d.%m.%Y")

        special, _, _, _ = initialize_sheets()
        rows = special.get_all_values()

        # Идём снизу вверх: если за день было несколько записей, берём последнюю.
        for row in reversed(rows[1:]):
            padded = row + [""] * max(0, len(SPECIAL_HEADERS) - len(row))
            if padded[0].strip() != previous_date:
                continue
            if normalize(padded[3]) != normalize(plate):
                continue

            return {
                "previous_date": previous_date,
                "driver": padded[4].strip(),
                "customer": padded[5].strip(),
                "object": padded[6].strip(),
                "start": padded[7].strip() or "-",
                "end": padded[8].strip() or "-",
                "rate_type": padded[10].strip() or "-",
                "rate": padded[11].strip() or "-",
                "rate_trip": padded[12].strip() or "-",
                "trips": padded[13].strip() or "-",
                "note": padded[15].strip() if len(padded) > 15 else "",
            }

        return None
    except Exception:
        logger.exception(
            "Не удалось найти предыдущий отчёт Спецтехники: %s / %s",
            work_date,
            plate,
        )
        return None


async def offer_previous_special_or_continue(message, context: ContextTypes.DEFAULT_TYPE):
    """Предлагает повторить сведения предыдущего дня для выбранной спецтехники."""
    d = context.user_data

    if d.get("category") != "special":
        await ask_machine_driver(message, context)
        return

    previous = get_previous_special_report(d["work_date"], d["plate"])
    if not previous:
        await ask_machine_driver(message, context)
        return

    d["previous_special"] = previous
    d["step"] = "previous_special_offer"

    text = (
        f"Нашёл отчёт по этой технике за {previous['previous_date']}.\n\n"
        f"Водитель: {previous['driver'] or '—'}\n"
        f"Заказчик: {previous['customer'] or '—'}\n"
        f"Объект: {previous['object'] or '—'}\n"
        f"Время: {previous['start']}–{previous['end']}\n"
        f"Вид ставки: {previous['rate_type']}\n"
        f"Ставка: {previous['rate']}\n"
        f"Ставка за рейс: {previous['rate_trip']}\n"
        f"Рейс: {previous['trips']}\n\n"
        "Повторить эти сведения?"
    )

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔁 Повторить сведения",
                        callback_data="prevspecial|repeat",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✍️ Заполнить заново",
                        callback_data="prevspecial|new",
                    )
                ],
            ]
        ),
    )


def apply_previous_special_report(d: dict[str, Any]) -> None:
    """Копирует предыдущий отчёт в текущий, оставляя выбранную новую дату."""
    previous = d["previous_special"]

    d["driver"] = previous["driver"]
    d["customer"] = previous["customer"]
    d["object"] = previous["object"]
    d["start"] = previous["start"]
    d["end"] = previous["end"]
    d["hours"] = work_hours(d["start"], d["end"])
    d["rate_type"] = previous["rate_type"]
    d["rate"] = previous["rate"]
    d["rate_trip"] = previous["rate_trip"]
    d["trips"] = previous["trips"]
    d["note"] = previous["note"]
    d["amount"] = calc_special(d)



async def ask_machine_driver(message, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    assigned = drivers_for_plate(d["plate"])
    rows = []
    for index, (name, primary) in enumerate(assigned):
        label = f"✅ {name}" if primary else name
        rows.append([InlineKeyboardButton(label, callback_data=f"machdriver|{index}")])
    rows.append([InlineKeyboardButton("👷 Выбрать из общего списка", callback_data="driverother|0")])
    rows.append([InlineKeyboardButton("➕ Добавить водителя для этой техники", callback_data="driveraddmachine|0")])
    rows.append([InlineKeyboardButton("⚙️ Управление водителями", callback_data="drivermanage|0")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="reportback|0")])
    await message.reply_text("Выберите водителя для этой техники:", reply_markup=InlineKeyboardMarkup(rows))


def number_or_dash(text: str) -> float | str:
    text = text.strip()
    return "-" if text == "-" else float(text.replace(" ", "").replace(",", "."))


def valid_time(text: str) -> bool:
    if text.strip() == "-":
        return True
    try:
        datetime.strptime(text.strip(), "%H:%M")
        return True
    except ValueError:
        return False


def work_hours(start: str, end: str) -> float | str:
    if "-" in (start, end):
        return "-"
    s = datetime.strptime(start, "%H:%M")
    e = datetime.strptime(end, "%H:%M")
    minutes = e.hour * 60 + e.minute - (s.hour * 60 + s.minute)
    if minutes < 0:
        minutes += 1440
    return round(max(0, minutes - 60) / 60, 2)


def calc_special(d: dict[str, Any]) -> float | str:
    rt = d["rate_type"]
    rate = d.get("rate", "-")
    rate_trip = d.get("rate_trip", "-")
    trips = d.get("trips", "-")
    hours = d["hours"]
    if rt == "-":
        return "-"
    if rt == "За час":
        return "-" if "-" in (rate, hours) else round(float(rate) * float(hours), 2)
    if rt == "За рейс":
        return "-" if "-" in (rate_trip, trips) else round(float(rate_trip) * float(trips), 2)
    return "-" if rate == "-" else round(float(rate), 2)


def calc_dump(objects: list[dict[str, Any]]):
    total_trips = total_volume = total_amount = 0.0
    has_t = has_v = has_a = False
    for obj in objects:
        trips, volume, rate_trip = obj["trips"], obj["volume"], obj["rate_trip"]
        if trips != "-":
            total_trips += float(trips)
            has_t = True

        object_volume = None
        if obj.get("total_volume") not in (None, "", "-"):
            object_volume = float(obj["total_volume"])
        elif trips != "-" and volume != "-":
            object_volume = float(trips) * float(volume)

        if object_volume is not None:
            total_volume += object_volume
            has_v = True

        # Общая сумма по объекту = общий объём × ставка.
        if object_volume is not None and rate_trip != "-":
            total_amount += object_volume * float(rate_trip)
            has_a = True

    return (
        round(total_trips, 2) if has_t else "-",
        round(total_volume, 2) if has_v else "-",
        round(total_amount, 2) if has_a else "-",
    )


def recalculate_dump_totals(ws) -> None:
    """Пересчитывает итоговые колонки Самосвалов для всех существующих строк."""
    try:
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return

        updates = []
        changed = False

        for row in rows[1:]:
            padded = row + [""] * max(0, len(DUMP_HEADERS) - len(row))

            total_trips = 0.0
            total_volume = 0.0
            total_amount = 0.0
            has_trips = False
            has_volume = False
            has_amount = False

            for i in range(4):
                base = 5 + i * 6
                rate = padded[base + 2]
                trips = padded[base + 3]
                body_volume = padded[base + 4]
                object_total_volume = padded[base + 5]

                trips_num = _to_float(trips)
                body_num = _to_float(body_volume)
                rate_num = _to_float(rate)
                volume_num = _to_float(object_total_volume)

                if str(trips).strip() not in ("", "-"):
                    total_trips += trips_num
                    has_trips = True

                if str(object_total_volume).strip() in ("", "-") and trips_num and body_num:
                    volume_num = trips_num * body_num

                if volume_num:
                    total_volume += volume_num
                    has_volume = True

                if volume_num and str(rate).strip() not in ("", "-"):
                    total_amount += volume_num * rate_num
                    has_amount = True

            new_values = [
                round(total_trips, 2) if has_trips else "-",
                round(total_volume, 2) if has_volume else "-",
                round(total_amount, 2) if has_amount else "-",
            ]

            old_values = padded[29:32]  # AD:AF
            if [str(x) for x in old_values] != [str(x) for x in new_values]:
                changed = True

            updates.append(new_values)

        if changed:
            ws.update(
                f"AD2:AF{len(rows)}",
                updates,
                value_input_option="USER_ENTERED",
            )
            logger.info("Пересчитаны итоги вкладки Самосвалы: %s строк", len(updates))
    except Exception:
        logger.exception("Не удалось пересчитать итоги вкладки Самосвалы")


def menu():
    return ReplyKeyboardMarkup(
        [
            ["🚜 Спецтехника", "🚛 Самосвалы"],
            ["🔎 По заказчику"],
            ["✏️ Изменить отчет", "⚙️ Справочники"],
        ],
        resize_keyboard=True,
    )


def buttons(values: list[str], prefix: str):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(v, callback_data=f"{prefix}|{i}")] for i, v in enumerate(values)]
    )


def machine_buttons(items):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{i + 1}. {name} | {model} | {plate}",
                    callback_data=f"machine|{i}",
                )
            ]
            for i, (name, model, plate) in enumerate(items)
        ]
    )


def ref_search_keyboard(kind: str, include_none: bool = False):
    rows = [[InlineKeyboardButton("🔍 Найти", callback_data=f"refsearch|{kind}")]]
    rows.append([InlineKeyboardButton("➕ Добавить новый", callback_data=f"refadd|{kind}")])
    if include_none:
        rows.append([InlineKeyboardButton("➖ Без заказчика", callback_data=f"refnone|{kind}")])
    return InlineKeyboardMarkup(rows)


def ref_results_keyboard(kind: str, values: list[str], include_none: bool = False):
    rows = [
        [InlineKeyboardButton(v[:55], callback_data=f"refresult|{kind}|{i}")]
        for i, v in enumerate(values)
    ]
    rows.append([InlineKeyboardButton("🔍 Искать ещё", callback_data=f"refsearch|{kind}")])
    rows.append([InlineKeyboardButton("➕ Добавить новый", callback_data=f"refadd|{kind}")])
    if include_none:
        rows.append([InlineKeyboardButton("➖ Без заказчика", callback_data=f"refnone|{kind}")])
    return InlineKeyboardMarkup(rows)


def _to_float(value: Any) -> float:
    text = str(value or "").strip().replace(" ", "").replace(",", ".")
    if not text or text == "-":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def build_customer_report(customer: str):
    """Ищет заказчика одновременно в Заказчик 1..4 и возвращает детальные строки."""
    _, dump, _, _ = initialize_sheets()
    rows = dump.get_all_values()
    target = normalize(customer)
    result = []

    for row in rows[1:]:
        if not row or not str(row[0]).strip():
            continue

        padded = row + [""] * max(0, len(DUMP_HEADERS) - len(row))

        # Базовые поля A:E
        work_date = padded[0]
        name = padded[1]
        model = padded[2]
        plate = padded[3]
        driver = padded[4]

        # Каждый блок занимает 6 колонок:
        # Заказчик, Объект, Ставка, Рейсы, Объем кузова, Общий объем.
        for i in range(4):
            base = 5 + i * 6
            row_customer = padded[base]
            obj = padded[base + 1]
            rate = padded[base + 2]
            trips = padded[base + 3]
            body_volume = padded[base + 4]
            total_volume = padded[base + 5]

            if normalize(row_customer) != target:
                continue

            # Для выбранного заказчика считаем только его конкретный блок.
            amount = _to_float(total_volume) * _to_float(rate)

            result.append(
                {
                    "date": work_date,
                    "name": name,
                    "model": model,
                    "plate": plate,
                    "driver": driver,
                    "object": obj,
                    "customer": row_customer,
                    "rate": rate,
                    "trips": trips,
                    "body_volume": body_volume,
                    "total_volume": total_volume,
                    "amount": round(amount, 2),
                }
            )

    return result


def write_customer_report_sheet(customer: str, items: list[dict[str, Any]]) -> None:
    """Записывает результат поиска в отдельную вкладку одним пакетным обновлением."""
    sp = book()
    ws = ensure_sheet(sp, SHEET_CUSTOMER_REPORT, CUSTOMER_REPORT_HEADERS, 500)

    # Очищаем только данные, оставляя заголовок.
    if ws.row_count > 1:
        ws.batch_clear([f"A2:L{ws.row_count}"])

    rows = []
    total_trips = 0.0
    total_volume = 0.0
    total_amount = 0.0

    for item in items:
        trips = _to_float(item["trips"])
        volume = _to_float(item["total_volume"])
        amount = _to_float(item["amount"])
        total_trips += trips
        total_volume += volume
        total_amount += amount

        rows.append(
            [
                item["date"],
                item["name"],
                item["model"],
                item["plate"],
                item["driver"],
                item["object"],
                item["customer"],
                item["rate"],
                item["trips"],
                item["body_volume"],
                item["total_volume"],
                item["amount"],
            ]
        )

    if rows:
        ws.update(
            f"A2:L{len(rows) + 1}",
            rows,
            value_input_option="USER_ENTERED",
        )

    summary_row = len(rows) + 3
    ws.update(
        f"A{summary_row}:D{summary_row + 3}",
        [
            ["Заказчик", customer, "", ""],
            ["Всего рейсов", round(total_trips, 2), "", ""],
            ["Общий объём, м³", round(total_volume, 2), "", ""],
            ["Общая сумма, ₽", round(total_amount, 2), "", ""],
        ],
        value_input_option="USER_ENTERED",
    )


async def customer_search_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data.update(flow="customer_report")
    await ask_ref(
        update.effective_message,
        context,
        "customers",
        "customer_report",
        include_none=False,
    )


async def show_customer_report(message, context: ContextTypes.DEFAULT_TYPE, customer: str):
    try:
        items = build_customer_report(customer)
        write_customer_report_sheet(customer, items)
    except Exception as exc:
        logger.exception("Ошибка поиска по заказчику %s", customer)
        await message.reply_text(
            f"Не удалось сформировать отчёт по заказчику «{customer}». "
            f"Ошибка: {type(exc).__name__}: {exc}",
            reply_markup=menu(),
        )
        context.user_data.clear()
        return

    if not items:
        await message.reply_text(
            f"По заказчику «{customer}» рейсы не найдены.",
            reply_markup=menu(),
        )
        context.user_data.clear()
        return

    total_trips = sum(_to_float(x["trips"]) for x in items)
    total_volume = sum(_to_float(x["total_volume"]) for x in items)
    total_amount = sum(_to_float(x["amount"]) for x in items)

    lines = [
        f"🏢 Заказчик: {customer}",
        f"Найдено позиций: {len(items)}",
        f"Всего рейсов: {round(total_trips, 2)}",
        f"Общий объём: {round(total_volume, 2)} м³",
        f"Общая сумма: {round(total_amount, 2):,.2f} ₽".replace(",", " "),
        "",
        "Последние записи:",
    ]

    for item in items[-15:]:
        lines.append(
            f"• {item['date']} | {item['plate']} | {item['object']} | "
            f"{item['trips']} рейс. | {item['total_volume']} м³ | "
            f"{item['amount']:,.2f} ₽".replace(",", " ")
        )

    if len(items) > 15:
        lines.append(f"…ещё {len(items) - 15} позиций смотрите во вкладке «{SHEET_CUSTOMER_REPORT}».")

    await message.reply_text("\n".join(lines), reply_markup=menu())
    context.user_data.clear()


async def sync_documents_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно заполняет ОСАГО и диагностические карты."""
    try:
        sp = book()
        osago = ensure_sheet(sp, SHEET_OSAGO, OSAGO_HEADERS, 600)
        diag = ensure_sheet(sp, SHEET_DIAG, DIAG_HEADERS, 600)

        seed_osago_equipment(osago)
        seed_diag_equipment(diag)
        setup_document_sheet(osago, "osago")
        setup_dashboard(osago, "osago")
        setup_document_sheet(diag, "diag")
        setup_dashboard(diag, "diag")

        await update.effective_message.reply_text(
            f"✅ Документы синхронизированы без перезаписи ручных данных.\n"
            f"ОСАГО: {len(OSAGO_EQUIPMENT)} машин.\n"
            f"Диагностические карты: {len(DIAG_EQUIPMENT)} машин.",
            reply_markup=menu(),
        )
    except Exception as exc:
        logger.exception("Ошибка синхронизации документов")
        await update.effective_message.reply_text(
            f"❌ Ошибка: {type(exc).__name__}: {exc}",
            reply_markup=menu(),
        )


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"✅ Бот работает.\nВерсия: {BOT_VERSION}",
        reply_markup=menu(),
    )


async def filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительно восстанавливает выпадающие фильтры Спецтехники и Самосвалов."""
    try:
        special, dump, _, _ = initialize_sheets()
        ensure_standard_value_filter(special, SPECIAL_HEADERS)
        ensure_standard_value_filter(dump, DUMP_HEADERS)
        await update.effective_message.reply_text(
            "✅ Таблицы преобразованы в обычные диапазоны, классические выпадающие фильтры восстановлены во вкладках "
            "«Спецтехника» и «Самосвалы».",
            reply_markup=menu(),
        )
    except Exception as exc:
        logger.exception("Ошибка восстановления фильтров")
        await update.effective_message.reply_text(
            f"❌ Не удалось восстановить фильтры: {type(exc).__name__}: {exc}",
            reply_markup=menu(),
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    initialize_sheets()
    await update.effective_message.reply_text("Выберите раздел:", reply_markup=menu())


async def version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"Версия бота: {BOT_VERSION}\n"
        "Вкладки: Спецтехника, Самосвалы, Поиск заказчика, ОСАГО, Диагностические карты, Водители, Объекты, Заказчики, Техника."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.effective_message.reply_text("Действие отменено.", reply_markup=menu())


async def begin_special(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data.update(flow="new", category="special", step="machine")
    await update.effective_message.reply_text(
        "Выберите спецтехнику:", reply_markup=machine_buttons(SPECIAL_EQUIPMENT)
    )


async def begin_dump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data.update(flow="new", category="dump", step="machine")
    await update.effective_message.reply_text(
        "Выберите самосвал или тягач:", reply_markup=machine_buttons(DUMP_EQUIPMENT)
    )


async def refs_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data.update(flow="refs", step="refs_menu")
    await update.effective_message.reply_text(
        "Выберите справочник:",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("👷 Водители", callback_data="refs|drivers")],
                [InlineKeyboardButton("📍 Объекты", callback_data="refs|objects")],
                [InlineKeyboardButton("🏢 Заказчики", callback_data="refs|customers")],
            ]
        ),
    )


def back_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Назад", callback_data="reportback|0")]]
    )


def with_back(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup:
    """Добавляет кнопку «Назад» к существующей inline-клавиатуре."""
    rows = []
    if markup is not None:
        rows = [list(row) for row in markup.inline_keyboard]
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="reportback|0")])
    return InlineKeyboardMarkup(rows)


async def show_special_step_from_data(message, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Возвращает пользователя на нужный этап отчёта Спецтехники."""
    d = context.user_data

    if target == "machine":
        d["step"] = "machine"
        await message.reply_text(
            "Выберите технику:",
            reply_markup=with_back(machine_keyboard(SPECIAL_EQUIPMENT)),
        )
    elif target == "date":
        d["step"] = "date_choice"
        await message.reply_text(
            "Укажите дату работы:",
            reply_markup=with_back(buttons(["Сегодня", "Завтра", "Другая дата"], "date")),
        )
    elif target == "driver":
        await ask_machine_driver(message, context)
    elif target == "start":
        d["step"] = "start_time"
        await message.reply_text(
            f"Текущее начало: {d.get('start', '—')}\nВведите время начала ЧЧ:ММ или «-»:",
            reply_markup=back_markup(),
        )
    elif target == "end":
        d["step"] = "end_time"
        await message.reply_text(
            f"Текущее окончание: {d.get('end', '—')}\nВведите время окончания ЧЧ:ММ или «-»:",
            reply_markup=back_markup(),
        )
    elif target == "object":
        await ask_ref(message, context, "objects", "special_object")
    elif target == "customer":
        await ask_ref(message, context, "customers", "special_customer", include_none=True)
    elif target == "rate_type":
        d["step"] = "rate_type"
        await message.reply_text(
            "Выберите вид ставки:",
            reply_markup=with_back(buttons(RATE_TYPES, "ratetype")),
        )
    elif target == "price":
        await prompt_special_price(message, context)
    elif target == "trips":
        d["step"] = "trips"
        await message.reply_text(
            f"Текущее количество рейсов: {d.get('trips', '—')}\nВведите количество рейсов или «-»:",
            reply_markup=back_markup(),
        )
    elif target == "note":
        d["step"] = "note"
        await message.reply_text(
            f"Текущее примечание: {d.get('note') or '—'}\nВведите примечание или «-»:",
            reply_markup=back_markup(),
        )


async def go_back_in_report(message, context: ContextTypes.DEFAULT_TYPE):
    """Шаг назад во время заполнения отчёта без потери уже введённых данных."""
    d = context.user_data
    category = d.get("category")
    step = d.get("step")

    if category == "special":
        mapping = {
            "date_choice": "machine",
            "date_manual": "date",
            "previous_special_offer": "date",
            "start_time": "driver",
            "end_time": "start",
            "ref_choice": None,
            "ref_search_query": None,
            "rate_type": "customer",
            "rate": "rate_type",
            "rate_trip": "rate_type",
            "trips": "price",
            "note": "trips" if d.get("rate_type") == "За рейс" else "price",
            "confirm": "note",
        }

        # Для справочников понимаем, что именно сейчас выбирается.
        if step in ("ref_choice", "ref_search_query"):
            kind = d.get("ref_kind")
            next_step = d.get("ref_next_step")
            if kind == "objects":
                target = "end"
            elif kind == "customers" and next_step == "special_customer":
                target = "object"
            elif kind == "drivers":
                target = "driver"
            else:
                target = "end"
        else:
            target = mapping.get(step)

        if target:
            await show_special_step_from_data(message, context, target)
        else:
            await message.reply_text("Это первый шаг отчёта.", reply_markup=menu())
        return

    # Самосвалы: сохраняем возможность вернуться хотя бы к предыдущему
    # логическому блоку без отмены всего отчёта.
    if category == "dump":
        if step in ("object_count", "ref_choice", "ref_search_query"):
            await ask_machine_driver(message, context)
        elif step in ("dump_rate", "dump_trips", "dump_volume"):
            # Возвращаемся к выбору текущего объекта/заказчика.
            await ask_ref(message, context, "objects", "dump_object")
        elif step == "note":
            d["step"] = "object_count"
            await message.reply_text(
                "Сколько объектов?",
                reply_markup=with_back(buttons(["1", "2", "3", "4"], "objcount")),
            )
        elif step == "confirm":
            d["step"] = "note"
            await message.reply_text(
                f"Текущее примечание: {d.get('note') or '—'}\nВведите примечание или «-»:",
                reply_markup=back_markup(),
            )
        else:
            await message.reply_text("Вернитесь к предыдущему шагу.", reply_markup=back_markup())




async def ask_ref(message, context: ContextTypes.DEFAULT_TYPE, kind: str, next_step: str, include_none: bool = False):
    context.user_data["ref_next_step"] = next_step
    context.user_data["ref_kind"] = kind
    context.user_data["ref_include_none"] = include_none
    context.user_data["step"] = "ref_choice"
    label = {"drivers": "водителя", "objects": "объект", "customers": "заказчика"}[kind]
    await message.reply_text(
        f"Выберите {label}: поиск по сохранённым данным или добавление нового.",
        reply_markup=with_back(ref_search_keyboard(kind, include_none=include_none)),
    )


async def after_ref_selected(message, context: ContextTypes.DEFAULT_TYPE, kind: str, value: str):
    d = context.user_data
    next_step = d.get("ref_next_step")
    if kind == "drivers":
        if next_step == "assign_machine_driver":
            ok, result = add_driver_for_plate(d["model"], d["plate"], value)
            if ok:
                await message.reply_text(
                    f"✅ Водитель {result} закреплён за {d['model']} — {d['plate']}."
                )
            else:
                await message.reply_text(result)
            await show_driver_management(message, context)
            return

        d["driver"] = value
        if d.get("category") == "dump":
            d["step"] = "object_count"
            await message.reply_text(
                "Сколько объектов?",
                reply_markup=buttons(["1", "2", "3", "4"], "objcount"),
            )
        else:
            d["step"] = "start_time"
            await message.reply_text("Введите время начала ЧЧ:ММ или «-»:")
    elif kind == "objects":
        if d["category"] == "special":
            d["object"] = value
            await ask_ref(message, context, "customers", "special_customer", include_none=True)
        else:
            d["current"] = {"object": value}
            await ask_ref(message, context, "customers", "dump_customer", include_none=True)
    elif kind == "customers":
        if next_step == "customer_report":
            await show_customer_report(message, context, value)
        elif next_step == "special_customer":
            d["customer"] = value
            d["step"] = "rate_type"
            await message.reply_text(
                "Выберите вид ставки:", reply_markup=buttons(RATE_TYPES, "ratetype")
            )
        else:
            d["current"]["customer"] = value
            await prompt_dump_customer_price(message, context)


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    action = parts[0]
    d = context.user_data

    if action == "reportback":
        await q.edit_message_text("⬅️ Возвращаемся на предыдущий шаг.")
        await go_back_in_report(q.message, context)
        return

    if action == "machine":
        items = SPECIAL_EQUIPMENT if d["category"] == "special" else DUMP_EQUIPMENT
        d["name"], d["model"], d["plate"] = items[int(parts[1])]
        d["step"] = "date_choice"
        await q.edit_message_text(
            "Укажите дату работы:",
            reply_markup=buttons(["Сегодня", "Завтра", "Другая дата"], "date"),
        )
    elif action == "date":
        choice = parts[1]
        if choice == "0":
            d["work_date"] = datetime.now().strftime("%d.%m.%Y")
            await q.edit_message_text(f"Дата выбрана: {d['work_date']}")
            await offer_previous_special_or_continue(q.message, context)
        elif choice == "1":
            d["work_date"] = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
            await q.edit_message_text(f"Дата выбрана: {d['work_date']}")
            await offer_previous_special_or_continue(q.message, context)
        else:
            d["step"] = "date_manual"
            await q.edit_message_text("Введите дату ДД.ММ.ГГГГ:", reply_markup=back_markup())
    elif action == "prevspecial":
        choice = parts[1]

        if choice == "repeat":
            previous = d.get("previous_special")
            if not previous:
                await q.edit_message_text(
                    "Предыдущий отчёт уже недоступен. Заполните сведения заново."
                )
                await ask_machine_driver(q.message, context)
                return

            apply_previous_special_report(d)
            d["step"] = "confirm"

            await q.edit_message_text(
                "✅ Сведения предыдущего дня перенесены на выбранную дату."
            )
            await q.message.reply_text(
                summary(d),
                reply_markup=with_back(buttons(["Сохранить", "Отменить"], "confirm")),
            )
        else:
            d.pop("previous_special", None)
            await q.edit_message_text("Заполняем сведения заново.")
            await ask_machine_driver(q.message, context)

    elif action == "machdriver":
        assigned = drivers_for_plate(d["plate"])
        d["driver"] = assigned[int(parts[1])][0]
        await q.edit_message_text(f"Выбран водитель: {d['driver']}")
        if d.get("category") == "dump":
            d["step"] = "object_count"
            await q.message.reply_text(
                "Сколько объектов?",
                reply_markup=buttons(["1", "2", "3", "4"], "objcount"),
            )
        else:
            d["step"] = "start_time"
            await q.message.reply_text("Введите время начала ЧЧ:ММ или «-»:", reply_markup=back_markup())
    elif action == "driverother":
        await q.edit_message_text("Выберите водителя из общего списка.")
        await ask_ref(q.message, context, "drivers", "driver")
    elif action == "drivermanage":
        await q.edit_message_text("Управление закреплёнными водителями.")
        await show_driver_management(q.message, context)
    elif action == "driverdelete":
        assigned = drivers_for_plate(d["plate"])
        index = int(parts[1])
        if index >= len(assigned):
            await q.edit_message_text("Список водителей изменился. Откройте управление ещё раз.")
            return
        driver_name = assigned[index][0]
        ok, result = remove_driver_for_plate(d["plate"], driver_name)
        if ok:
            await q.edit_message_text(
                f"✅ Водитель {result} больше не закреплён за этой техникой."
            )
        else:
            await q.edit_message_text(result)
        await show_driver_management(q.message, context)
    elif action == "driverassignexisting":
        await q.edit_message_text("Выберите водителя из общего списка для закрепления за этой техникой.")
        await ask_ref(q.message, context, "drivers", "assign_machine_driver")
    elif action == "driverback":
        await q.edit_message_text("Возвращаю к выбору водителя.")
        await ask_machine_driver(q.message, context)
    elif action == "driveraddmachine":
        d["step"] = "add_machine_driver"
        await q.edit_message_text(
            f"Введите имя нового водителя для {d['model']} — {d['plate']}:"
        )
    elif action == "ratetype":
        d["rate_type"] = RATE_TYPES[int(parts[1])]
        if d["rate_type"] == "За рейс":
            d["rate"] = "-"
        else:
            d["rate_trip"] = "-"
            d["trips"] = "-"
        await q.edit_message_text(f"Вид ставки: {d['rate_type']}")
        await prompt_special_price(q.message, context)
    elif action == "custprice":
        choice = parts[1]
        if choice == "use":
            price = d.get("saved_customer_price")
            if price is None:
                await q.edit_message_text("Сохранённая цена не найдена. Введите цену вручную.")
                d["step"] = "rate_trip" if d["rate_type"] == "За рейс" else "rate"
                return
            if d["rate_type"] == "За рейс":
                d["rate_trip"] = price
                d["step"] = "trips"
                await q.edit_message_text(f"Использована цена {price:g} ₽. Введите количество рейсов или «-»:")
            else:
                d["rate"] = price
                d["step"] = "note"
                await q.edit_message_text(f"Использована цена {price:g} ₽. Введите примечание или «-»:")
        else:
            d["step"] = "rate_trip" if d["rate_type"] == "За рейс" else "rate"
            await q.edit_message_text(
                "Введите новую ставку за рейс или «-»:"
                if d["rate_type"] == "За рейс"
                else "Введите новую ставку или «-»:"
            )
    elif action == "dumpcustprice":
        choice = parts[1]
        current = d["current"]
        if choice == "use":
            price = current.get("saved_price")
            if price is None:
                d["step"] = "dump_rate"
                await q.edit_message_text("Сохранённая цена не найдена. Введите цену вручную:")
                return
            current["rate_trip"] = price
            d["step"] = "dump_trips"
            await q.edit_message_text(
                f"Использована цена {price:g} ₽. Введите количество рейсов или «-»:"
            )
        else:
            d["step"] = "dump_rate"
            await q.edit_message_text("Введите новую цену для этого объекта или «-»:")
    elif action == "objcount":
        d["object_count"] = int(parts[1]) + 1
        d["object_index"] = 1
        d["objects"] = []
        await q.edit_message_text("Количество объектов выбрано.")
        await ask_ref(q.message, context, "objects", "dump_object")
    elif action == "confirm":
        if parts[1] == "1":
            context.user_data.clear()
            await q.edit_message_text("Отчёт отменён.")
            await q.message.reply_text("Выберите действие:", reply_markup=menu())
            return
        await save_current_report(q, context)
    elif action == "editsheet":
        await show_edit_rows(q, context, parts[1])
    elif action == "editrow":
        d["edit_row"] = int(parts[1])
        d["step"] = "edit_field"
        await show_edit_fields(q, context)
    elif action == "editfield":
        fields = SPECIAL_EDIT_FIELDS if d["edit_sheet"] == "special" else DUMP_EDIT_FIELDS
        idx = int(parts[1])
        if idx >= len(fields):
            await q.edit_message_text("Поле не найдено.")
            return
        label, col = fields[idx]
        d["edit_col"] = col
        d["edit_label"] = label
        d["step"] = "edit_value"
        await q.edit_message_text(f"Введите новое значение для «{label}»:")
    elif action == "refsearch":
        kind = parts[1]
        d["ref_kind"] = kind
        d["step"] = "ref_search_query"
        prompt = {"drivers": "Введите имя или часть имени водителя:", "objects": "Введите название или часть названия объекта:", "customers": "Введите название или часть названия заказчика:"}[kind]
        await q.edit_message_text(prompt)
    elif action == "refresult":
        kind, index = parts[1], int(parts[2])
        results = d.get("ref_search_results", [])
        if index >= len(results):
            await q.edit_message_text("Результаты поиска устарели. Выполните поиск ещё раз.")
            return
        selected = results[index]
        await q.edit_message_text(f"Выбрано: {selected}")
        await after_ref_selected(q.message, context, kind, selected)
    elif action == "refnone":
        kind = parts[1]
        await q.edit_message_text("Выбрано: без заказчика")
        await after_ref_selected(q.message, context, kind, "")
    elif action == "refadd":
        d["add_ref_kind"] = parts[1]
        d["step"] = "add_ref_value"
        await q.edit_message_text(f"Введите новое значение для «{REF_TITLES[parts[1]]}»:")
    elif action == "refs":
        kind = parts[1]
        d["manage_ref_kind"] = kind
        count = len(ref_values(kind))
        await q.edit_message_text(
            f"{REF_TITLES[kind]}. Сохранено записей: {count}.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔍 Найти", callback_data=f"refmanagefind|{kind}")],
                    [InlineKeyboardButton("➕ Добавить", callback_data=f"refmanageadd|{kind}")],
                    [InlineKeyboardButton("🗑 Найти и удалить", callback_data=f"refdelmenu|{kind}")],
                ]
            ),
        )
    elif action == "refmanageadd":
        d["add_ref_kind"] = parts[1]
        d["step"] = "manage_add_ref_value"
        await q.edit_message_text(f"Введите новое значение для «{REF_TITLES[parts[1]]}»:")
    elif action == "refmanagefind":
        kind = parts[1]
        d["manage_ref_kind"] = kind
        d["step"] = "manage_ref_search"
        await q.edit_message_text("Введите часть названия для поиска:")
    elif action == "refdelmenu":
        kind = parts[1]
        d["manage_ref_kind"] = kind
        d["step"] = "delete_ref_search"
        await q.edit_message_text("Введите часть названия записи, которую нужно удалить:")
    elif action == "refdelete":
        kind, index = parts[1], int(parts[2])
        results = d.get("delete_search_results", [])
        if index >= len(results):
            await q.edit_message_text("Результаты поиска устарели. Выполните поиск ещё раз.")
            return
        target = results[index]
        all_values = ref_values(kind)
        real_index = next((i for i, v in enumerate(all_values) if normalize(v) == normalize(target)), -1)
        if real_index < 0:
            await q.edit_message_text("Запись уже отсутствует.")
            return
        deleted = delete_ref(kind, real_index)
        await q.edit_message_text(f"✅ Удалено: {deleted}")
        await q.message.reply_text("Выберите действие:", reply_markup=menu())
        context.user_data.clear()
    elif action == "noop":
        return


async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    step = d.get("step")
    value = update.message.text.strip()
    if not step:
        await update.message.reply_text("Нажмите /start.", reply_markup=menu())
        return

    try:
        if step == "date_manual":
            datetime.strptime(value, "%d.%m.%Y")
            d["work_date"] = value
            await offer_previous_special_or_continue(update.message, context)
        elif step == "add_machine_driver":
            ok, result = add_driver_for_plate(d["model"], d["plate"], value)
            if not ok:
                await update.message.reply_text(result)
                return
            d["driver"] = result
            if d.get("category") == "dump":
                d["step"] = "object_count"
                await update.message.reply_text(
                    f"✅ Водитель добавлен и выбран: {result}\nСколько объектов?",
                    reply_markup=buttons(["1", "2", "3", "4"], "objcount"),
                )
            else:
                d["step"] = "start_time"
                await update.message.reply_text(
                    f"✅ Водитель добавлен и выбран: {result}\nВведите время начала ЧЧ:ММ или «-»:"
                )
        elif step == "start_time":
            if not valid_time(value):
                raise ValueError("Неверное время")
            d["start"] = value
            d["step"] = "end_time"
            await update.message.reply_text("Введите время окончания ЧЧ:ММ или «-»:", reply_markup=back_markup())
        elif step == "end_time":
            if not valid_time(value):
                raise ValueError("Неверное время")
            d["end"] = value
            d["hours"] = work_hours(d["start"], value)
            if d["category"] == "special":
                await ask_ref(update.message, context, "objects", "special_object")
            else:
                d["step"] = "object_count"
                await update.message.reply_text(
                    "Сколько объектов?",
                    reply_markup=buttons(["1", "2", "3", "4"], "objcount"),
                )
        elif step == "rate":
            d["rate"] = number_or_dash(value)
            if d["rate"] != "-":
                set_customer_price(d["customer"], float(d["rate"]))
            d["step"] = "note"
            await update.message.reply_text("Введите примечание или «-»:", reply_markup=back_markup())
        elif step == "rate_trip":
            d["rate_trip"] = number_or_dash(value)
            if d["rate_trip"] != "-":
                set_customer_price(d["customer"], float(d["rate_trip"]))
            d["step"] = "trips"
            await update.message.reply_text("Введите количество рейсов или «-»:", reply_markup=back_markup())
        elif step == "trips":
            d["trips"] = number_or_dash(value)
            d["step"] = "note"
            await update.message.reply_text("Введите примечание или «-»:", reply_markup=back_markup())
        elif step == "dump_rate":
            d["current"]["rate_trip"] = number_or_dash(value)
            if d["current"]["rate_trip"] != "-":
                set_customer_price(
                    d["current"]["customer"],
                    float(d["current"]["rate_trip"]),
                    "dump",
                )
            d["step"] = "dump_trips"
            await update.message.reply_text("Введите количество рейсов или «-»:", reply_markup=back_markup())
        elif step == "dump_trips":
            d["current"]["trips"] = number_or_dash(value)
            d["step"] = "dump_volume"
            await update.message.reply_text("Введите объём кузова, м³, или «-»:")
        elif step == "dump_volume":
            d["current"]["volume"] = number_or_dash(value)
            current = d["current"]
            current["total_volume"] = (
                "-"
                if "-" in (current["trips"], current["volume"])
                else round(float(current["trips"]) * float(current["volume"]), 2)
            )
            d["objects"].append(current)
            if d["object_index"] < d["object_count"]:
                d["object_index"] += 1
                await ask_ref(update.message, context, "objects", "dump_object")
            else:
                d["step"] = "note"
                await update.message.reply_text("Введите примечание или «-»:", reply_markup=back_markup())
        elif step == "ref_search_query":
            kind = d["ref_kind"]
            results = search_ref_values(kind, value)
            d["ref_search_results"] = results
            include_none = bool(d.get("ref_include_none"))
            if not results:
                d["step"] = "ref_choice"
                await update.message.reply_text(
                    "Ничего не найдено. Можно поискать ещё или добавить новую запись.",
                    reply_markup=ref_search_keyboard(kind, include_none=include_none),
                )
            elif len(results) == 1 and normalize(results[0]) == normalize(value):
                await update.message.reply_text(f"Найдено точное совпадение: {results[0]}")
                await after_ref_selected(update.message, context, kind, results[0])
            else:
                d["step"] = "ref_choice"
                await update.message.reply_text(
                    f"Найдено: {len(results)}. Выберите нужное:",
                    reply_markup=ref_results_keyboard(kind, results, include_none=include_none),
                )
        elif step == "manage_ref_search":
            kind = d["manage_ref_kind"]
            results = search_ref_values(kind, value)
            if not results:
                await update.message.reply_text("Ничего не найдено.", reply_markup=menu())
                context.user_data.clear()
            else:
                await update.message.reply_text(
                    "Результаты поиска:\n" + "\n".join(f"• {x}" for x in results),
                    reply_markup=menu(),
                )
                context.user_data.clear()
        elif step == "delete_ref_search":
            kind = d["manage_ref_kind"]
            results = search_ref_values(kind, value)
            d["delete_search_results"] = results
            d["step"] = "delete_ref_choice"
            if not results:
                await update.message.reply_text("Ничего не найдено.", reply_markup=menu())
                context.user_data.clear()
            else:
                rows = [[InlineKeyboardButton(x[:55], callback_data=f"refdelete|{kind}|{i}")] for i, x in enumerate(results)]
                await update.message.reply_text("Выберите запись для удаления:", reply_markup=InlineKeyboardMarkup(rows))
        elif step == "note":
            d["note"] = "" if value == "-" else value
            if d["category"] == "special":
                d["amount"] = calc_special(d)
            else:
                d["total_trips"], d["total_volume"], d["amount"] = calc_dump(d["objects"])
            d["step"] = "confirm"
            await update.message.reply_text(
                summary(d), reply_markup=with_back(buttons(["Сохранить", "Отменить"], "confirm"))
            )
        elif step == "edit_value":
            special, dump, _, _ = initialize_sheets()
            ws = special if d["edit_sheet"] == "special" else dump
            new_value = value.strip()

            # Базовая проверка времени.
            if d["edit_sheet"] == "special" and d["edit_col"] in (8, 9) and not valid_time(new_value):
                raise ValueError("Время нужно вводить ЧЧ:ММ или «-»")

            ws.update_cell(d["edit_row"], d["edit_col"], new_value)
            recalc_edited_report_row(ws, d["edit_sheet"], d["edit_row"])

            await update.message.reply_text(
                f"✅ «{d['edit_label']}» изменено. Расчётные поля обновлены автоматически.",
                reply_markup=menu(),
            )
            context.user_data.clear()
        elif step in {"add_ref_value", "manage_add_ref_value"}:
            kind = d["add_ref_kind"]
            ok, result = add_ref(kind, value)
            if not ok:
                await update.message.reply_text(result)
                return
            if step == "add_ref_value":
                await update.message.reply_text(f"✅ Добавлено: {result}")
                await after_ref_selected(update.message, context, kind, result)
            else:
                await update.message.reply_text(f"✅ Добавлено: {result}", reply_markup=menu())
                context.user_data.clear()
    except Exception as exc:
        await update.message.reply_text(f"Ошибка: {exc}. Попробуйте ещё раз.")



def summary(d):
    base = (
        f"Дата: {d['work_date']}\n"
        f"Техника: {d['name']} | {d['model']} | {d['plate']}\n"
        f"Водитель: {d['driver']}"
    )
    if d["category"] == "special":
        base += (
            f"\nВремя: {d['start']}–{d['end']}"
            f"\nРабочее время: {d['hours']}"
        )
        return (
            base
            + f"\nОбъект: {d['object']}"
            + f"\nЗаказчик: {d['customer'] or '—'}"
            + f"\nВид ставки: {d['rate_type']}"
            + f"\nСтавка: {d.get('rate', '-')}"
            + f"\nСтавка за рейс: {d.get('rate_trip', '-')}"
            + f"\nРейс: {d.get('trips', '-')}"
            + f"\nСумма: {d['amount']}"
        )
    lines = []
    for i, obj in enumerate(d["objects"], 1):
        lines.append(
            f"{i}. {obj['object']} | {obj['customer'] or '—'} | "
            f"ставка {obj['rate_trip']} | рейсы {obj['trips']} | "
            f"кузов {obj['volume']} м³ | объём {obj['total_volume']} м³"
        )
    return (
        base
        + "\n"
        + "\n".join(lines)
        + f"\nВсего рейсов: {d['total_trips']}"
        + f"\nОбщий объём: {d['total_volume']} м³"
        + f"\nСумма: {d['amount']}"
    )


async def save_current_report(q, context):
    d = context.user_data
    special, dump, _, _ = initialize_sheets()
    user = q.from_user
    if d["category"] == "special":
        row = [
            d["work_date"],
            d["name"],
            d["model"],
            d["plate"],
            d["driver"],
            d["customer"],
            d["object"],
            d["start"],
            d["end"],
            d["hours"],
            d["rate_type"],
            d.get("rate", "-"),
            d.get("rate_trip", "-"),
            d.get("trips", "-"),
            d["amount"],
            d["note"],
            datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            user.full_name,
            f"@{user.username}" if user.username else "",
            str(q.message.chat.id),
        ]
        row_num = save_row(special, row)
        special.update_cell(row_num, 10, special_hours_formula(row_num))
        special.update_cell(row_num, 15, special_amount_formula(row_num))
        tab = SHEET_SPECIAL
    else:
        row = [
            d["work_date"],
            d["name"],
            d["model"],
            d["plate"],
            d["driver"],
        ]
        for i in range(4):
            if i < len(d["objects"]):
                obj = d["objects"][i]
                row.extend(
                    [
                        obj["customer"],
                        obj["object"],
                        obj["rate_trip"],
                        obj["trips"],
                        obj["volume"],
                        obj["total_volume"],
                    ]
                )
            else:
                row.extend(["", "", "", "", "", ""])
        row.extend(
            [
                d["total_trips"],
                d["total_volume"],
                d["amount"],
                d["note"],
                datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                user.full_name,
                f"@{user.username}" if user.username else "",
                str(q.message.chat.id),
                build_customer_filter_text(d["objects"]),
            ]
        )
        row_num = save_row(dump, row)
        formulas = dump_row_formulas(row_num)
        for col, formula in formulas.items():
            dump.update_cell(row_num, col, formula)
        tab = SHEET_DUMP
    await q.edit_message_text(f"✅ Сохранено. Вкладка: {tab}. Строка: {row_num}")
    await q.message.reply_text("Выберите действие:", reply_markup=menu())
    context.user_data.clear()


SPECIAL_EDIT_FIELDS = [
    ("Дата работы", 1),
    ("Водитель", 5),
    ("Заказчик", 6),
    ("Объект", 7),
    ("Начало", 8),
    ("Окончание", 9),
    ("Вид ставки", 11),
    ("Ставка, ₽", 12),
    ("Ставка за рейс, ₽", 13),
    ("Рейс", 14),
    ("Примечание", 16),
]

DUMP_EDIT_FIELDS = [
    ("Дата работы", 1),
    ("Водитель", 5),
]
for _i in range(4):
    _base = 6 + _i * 6
    DUMP_EDIT_FIELDS.extend(
        [
            (f"Заказчик {_i+1}", _base),
            (f"Объект {_i+1}", _base + 1),
            (f"Ставка {_i+1}", _base + 2),
            (f"Рейсы {_i+1}", _base + 3),
            (f"Объём кузова {_i+1}", _base + 4),
        ]
    )
DUMP_EDIT_FIELDS.append(("Примечание", 33))


def recalc_edited_report_row(ws, sheet_code: str, row_num: int) -> None:
    """После изменения через бота восстанавливает производные значения."""
    if sheet_code == "special":
        row = ws.row_values(row_num)
        row += [""] * max(0, len(SPECIAL_HEADERS) - len(row))
        # Рабочее время и сумма — формулы Google Sheets.
        # Поэтому изменение Начала/Окончания/Ставки сразу пересчитывает результат.
        ws.update_cell(row_num, 10, special_hours_formula(row_num))
        ws.update_cell(row_num, 15, special_amount_formula(row_num))

        # Если изменена цена — сохраняем её за заказчиком.
        customer = row[5].strip()
        rate_type = row[10].strip()
        if customer:
            price_text = row[12] if rate_type == "За рейс" else row[11]
            if str(price_text).strip() not in ("", "-"):
                try:
                    set_customer_price(
                        customer,
                        float(str(price_text).replace(" ", "").replace(",", "."))
                    )
                except ValueError:
                    pass
    else:
        formulas = dump_row_formulas(row_num)
        for col, formula in formulas.items():
            ws.update_cell(row_num, col, formula)

        # Если через бота изменили ставку Самосвалов, сохраняем её за заказчиком.
        row = ws.row_values(row_num)
        row += [""] * max(0, len(DUMP_HEADERS) - len(row))
        for base in (5, 11, 17, 23):
            customer_name = row[base].strip() if len(row) > base else ""
            price_text = row[base + 2].strip() if len(row) > base + 2 else ""
            if customer_name and price_text not in ("", "-"):
                try:
                    set_customer_price(
                        customer_name,
                        float(price_text.replace(" ", "").replace(",", ".")),
                        "dump",
                    )
                except ValueError:
                    pass

        # Обновляем служебную колонку заказчиков после редактирования.
        row = ws.row_values(row_num)
        row += [""] * max(0, len(DUMP_HEADERS) - len(row))
        customers = []
        seen = set()
        for idx in (5, 11, 17, 23):  # G,M,S,Y
            customer = row[idx].strip() if idx < len(row) else ""
            key = normalize(customer)
            if customer and key not in seen:
                customers.append(customer)
                seen.add(key)
        ws.update_cell(row_num, 38, " | ".join(customers))


async def show_edit_fields(q, context):
    sheet_code = context.user_data["edit_sheet"]
    fields = SPECIAL_EDIT_FIELDS if sheet_code == "special" else DUMP_EDIT_FIELDS
    rows = []
    for idx, (label, _) in enumerate(fields):
        rows.append([InlineKeyboardButton(label, callback_data=f"editfield|{idx}")])
    await q.edit_message_text(
        "Что именно изменить?",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def edit_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data.update(flow="edit", step="edit_sheet")
    await update.effective_message.reply_text(
        "Выберите вкладку:",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Спецтехника", callback_data="editsheet|special")],
                [InlineKeyboardButton("Самосвалы", callback_data="editsheet|dump")],
            ]
        ),
    )


async def show_edit_rows(q, context, sheet_code):
    context.user_data["edit_sheet"] = sheet_code
    special, dump, _, _ = initialize_sheets()
    ws = special if sheet_code == "special" else dump
    rows = ws.get_all_values()
    keyboard = []
    for row_num in range(len(rows), 1, -1):
        row = rows[row_num - 1]
        if row and row[0].strip():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{row[0]} | {row[3] if len(row) > 3 else ''} | "
                        f"{row[4] if len(row) > 4 else ''}"[:60],
                        callback_data=f"editrow|{row_num}",
                    )
                ]
            )
        if len(keyboard) >= 20:
            break
    await q.edit_message_text(
        "Выберите строку:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def build():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("version", version))
    app.add_handler(CommandHandler("filters", filters_command))
    app.add_handler(CommandHandler("health", health_command))
    app.add_handler(CommandHandler("syncdocs", sync_documents_command))
    app.add_handler(MessageHandler(filters.Regex(r"^🚜 Спецтехника$"), begin_special))
    app.add_handler(MessageHandler(filters.Regex(r"^🚛 Самосвалы$"), begin_dump))
    app.add_handler(MessageHandler(filters.Regex(r"^🔎 По заказчику$"), customer_search_begin))
    app.add_handler(MessageHandler(filters.Regex(r"^✏️ Изменить отчет$"), edit_begin))
    app.add_handler(MessageHandler(filters.Regex(r"^⚙️ Справочники$"), refs_begin))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
    return app


if __name__ == "__main__":
    logger.info("Запуск бота %s", BOT_VERSION)
    try:
        initialize_sheets()
    except Exception:
        logger.exception(
            "Google Sheets временно недоступен при запуске. "
            "Telegram-бот всё равно будет запущен."
        )
    build().run_polling(drop_pending_updates=False)

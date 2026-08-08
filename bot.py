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
    MessageHandler,
    filters,
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_VERSION = "5.9.1-customer-search-fixed"
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
    "Объект",
    "Заказчик",
    "Начало",
    "Окончание",
    "Рабочее время, ч",
    "Вид ставки",
    "Ставка, ₽",
    "Ставка за рейс, ₽",
    "Рейс",
    "Сумма, ₽",
    "Статус оплаты",
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
            f"Объект {i}",
            f"Заказчик {i}",
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
        "Сумма, ₽",
        "Статус оплаты",
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
    "Категория",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Страховая компания",
    "Серия и номер полиса",
    "Дата начала",
    "Дата окончания",
    "Осталось дней",
    "Допущенные водители",
    "Ограничение",
    "Статус",
    "Примечание",
]

DIAG_HEADERS = [
    "№",
    "Категория",
    "Наименование техники",
    "Модель",
    "Гос. номер",
    "Номер диагностической карты",
    "Дата оформления",
    "Дата окончания",
    "Осталось дней",
    "Статус",
    "Примечание",
]

REF_HEADERS = ["Водители", "Объекты", "Заказчики"]
REF_TITLES = {"drivers": "Водители", "objects": "Объекты", "customers": "Заказчики"}
DIRECTORY_SHEETS = {"drivers": SHEET_DRIVERS, "objects": SHEET_OBJECTS, "customers": SHEET_CUSTOMERS}
DIRECTORY_HEADERS = {"drivers": ["Водитель"], "objects": ["Объект"], "customers": ["Заказчик"]}

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

def setup_document_sheet(ws, kind: str) -> None:
    if kind == "osago":
        last_col, end_col, days_col, status_col = "N", 9, 10, 13
    else:
        last_col, end_col, days_col, status_col = "K", 8, 9, 10

    # Если формулы уже установлены, повторно сотни ячеек не переписываем.
    dcol = col_letter(days_col)
    scol = col_letter(status_col)
    existing_a2 = ws.acell("A2", value_render_option="FORMULA").value or ""
    existing_days = ws.acell(f"{dcol}2", value_render_option="FORMULA").value or ""
    existing_status = ws.acell(f"{scol}2", value_render_option="FORMULA").value or ""
    formulas_ready = all(str(x).startswith("=") for x in (existing_a2, existing_days, existing_status))
    if formulas_ready:
        return

    try:
        ws.set_basic_filter(f"A1:{last_col}500")
    except Exception:
        logger.exception("Не удалось установить фильтр для %s", ws.title)

    rows = []
    for row in range(2, 502):
        end_letter = col_letter(end_col)
        days_letter = col_letter(days_col)
        rows.append(
            [
                f'=IF(C{row}="","",ROW()-1)',
                f'=IF({end_letter}{row}="","",{end_letter}{row}-TODAY())',
                (
                    f'=IF({end_letter}{row}="","Нет данных",'
                    f'IF({days_letter}{row}<0,"Просрочен",'
                    f'IF({days_letter}{row}<=30,"Заканчивается","Действует")))'
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
        start_col, status_col = "P", "M"
    else:
        start_col, status_col = "M", "J"
    if (ws.acell(start_col + "1").value or "").strip() == "Сводка":
        return
    start_num = gspread.utils.a1_to_rowcol(start_col + "1")[1]
    required_cols = start_num + 1
    if ws.col_count < required_cols:
        ws.add_cols(required_cols - ws.col_count)
    end_col = col_letter(required_cols)
    ws.update(
        f"{start_col}1:{end_col}5",
        [
            ["Сводка", "Количество"],
            ["Всего документов", f'=COUNTIF({status_col}2:{status_col},"<>")'],
            ["Действует", f'=COUNTIF({status_col}2:{status_col},"Действует")'],
            ["Заканчивается", f'=COUNTIF({status_col}2:{status_col},"Заканчивается")'],
            ["Просрочен", f'=COUNTIF({status_col}2:{status_col},"Просрочен")'],
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
        rows = ws.get_all_values()

        # Заполняем служебную колонку для уже существующих отчетов.
        # После удаления колонок времени:
        # G(7), M(13), S(19), Y(25) = Заказчик 1..4.
        if len(rows) > 1:
            values = []
            changed = False
            for row in rows[1:]:
                padded = row + [""] * max(0, helper_col - len(row))
                customers = []
                seen = set()

                for idx in (6, 12, 18, 24):
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

        # Обычный фильтр на всю таблицу тоже оставляем.
        requests = [
            {"clearBasicFilter": {"sheetId": ws.id}},
            {
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": ws.id,
                            "startRowIndex": 0,
                            "endRowIndex": ws.row_count,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(DUMP_HEADERS),
                        }
                    }
                }
            },
        ]

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

        # Один batch-запрос вместо множества отдельных обращений к API.
        ws.spreadsheet.batch_update({"requests": requests})
        logger.info(
            "Созданы индивидуальные фильтры заказчиков: %s",
            len(customers),
        )
    except Exception:
        logger.exception("Не удалось настроить индивидуальные фильтры заказчиков")


def initialize_sheets(force: bool = False):
    global _SHEET_CACHE, _DIRECTORY_SHEETS
    if _SHEET_CACHE is not None and not force:
        return _SHEET_CACHE

    sp = book()
    titles = [ws.title for ws in sp.worksheets()]
    if "Отчеты" in titles and SHEET_SPECIAL not in titles:
        sp.worksheet("Отчеты").update_title(SHEET_SPECIAL)

    special = ensure_sheet(sp, SHEET_SPECIAL, SPECIAL_HEADERS)
    try:
        dump_existing = sp.worksheet(SHEET_DUMP)
        migrate_dump_remove_time_columns(dump_existing)
    except gspread.WorksheetNotFound:
        pass
    dump = ensure_sheet(sp, SHEET_DUMP, DUMP_HEADERS)
    osago = ensure_sheet(sp, SHEET_OSAGO, OSAGO_HEADERS, 600)
    diag = ensure_sheet(sp, SHEET_DIAG, DIAG_HEADERS, 600)
    drivers_ws = ensure_sheet(sp, SHEET_DRIVERS, DIRECTORY_HEADERS["drivers"], 500)
    objects_ws = ensure_sheet(sp, SHEET_OBJECTS, DIRECTORY_HEADERS["objects"], 500)
    customers_ws = ensure_sheet(sp, SHEET_CUSTOMERS, DIRECTORY_HEADERS["customers"], 500)
    setup_dump_customer_filter(dump, customers_ws)
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


async def ask_machine_driver(message, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    assigned = drivers_for_plate(d["plate"])
    rows = []
    for index, (name, primary) in enumerate(assigned):
        label = f"✅ {name}" if primary else name
        rows.append([InlineKeyboardButton(label, callback_data=f"machdriver|{index}")])
    rows.append([InlineKeyboardButton("👷 Выбрать из общего списка", callback_data="driverother|0")])
    rows.append([InlineKeyboardButton("➕ Добавить водителя для этой техники", callback_data="driveraddmachine|0")])
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
        if trips != "-" and volume != "-":
            object_volume = float(trips) * float(volume)
            total_volume += object_volume
            has_v = True

        # Для самосвалов стоимость считается по перевезённому объёму:
        # общий объём по объекту × ставка.
        if object_volume is not None and rate_trip != "-":
            total_amount += object_volume * float(rate_trip)
            has_a = True

    return (
        round(total_trips, 2) if has_t else "-",
        round(total_volume, 2) if has_v else "-",
        round(total_amount, 2) if has_a else "-",
    )


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

        # Каждый объект занимает 6 колонок:
        # Объект, Заказчик, Ставка, Рейсы, Объем кузова, Общий объем.
        for i in range(4):
            base = 5 + i * 6
            obj = padded[base]
            row_customer = padded[base + 1]
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


async def ask_ref(message, context: ContextTypes.DEFAULT_TYPE, kind: str, next_step: str, include_none: bool = False):
    context.user_data["ref_next_step"] = next_step
    context.user_data["ref_kind"] = kind
    context.user_data["ref_include_none"] = include_none
    context.user_data["step"] = "ref_choice"
    label = {"drivers": "водителя", "objects": "объект", "customers": "заказчика"}[kind]
    await message.reply_text(
        f"Выберите {label}: поиск по сохранённым данным или добавление нового.",
        reply_markup=ref_search_keyboard(kind, include_none=include_none),
    )


async def after_ref_selected(message, context: ContextTypes.DEFAULT_TYPE, kind: str, value: str):
    d = context.user_data
    next_step = d.get("ref_next_step")
    if kind == "drivers":
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
            d["step"] = "dump_rate"
            await message.reply_text("Введите ставку за рейс или «-»:")


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("|")
    action = parts[0]
    d = context.user_data

    if action == "machine":
        items = SPECIAL_EQUIPMENT if d["category"] == "special" else DUMP_EQUIPMENT
        d["name"], d["model"], d["plate"] = items[int(parts[1])]
        d["step"] = "date_choice"
        await q.edit_message_text(
            "Укажите дату работы:",
            reply_markup=buttons(["Сегодня", "Другая дата"], "date"),
        )
    elif action == "date":
        if parts[1] == "0":
            d["work_date"] = datetime.now().strftime("%d.%m.%Y")
            await q.edit_message_text("Дата выбрана.")
            await ask_machine_driver(q.message, context)
        else:
            d["step"] = "date_manual"
            await q.edit_message_text("Введите дату ДД.ММ.ГГГГ:")
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
            await q.message.reply_text("Введите время начала ЧЧ:ММ или «-»:")
    elif action == "driverother":
        await q.edit_message_text("Выберите водителя из общего списка.")
        await ask_ref(q.message, context, "drivers", "driver")
    elif action == "driveraddmachine":
        d["step"] = "add_machine_driver"
        await q.edit_message_text(
            f"Введите имя нового водителя для {d['model']} — {d['plate']}:"
        )
    elif action == "ratetype":
        d["rate_type"] = RATE_TYPES[int(parts[1])]
        if d["rate_type"] == "За рейс":
            d["rate"] = "-"
            d["step"] = "rate_trip"
            await q.edit_message_text("Введите ставку за рейс или «-»:")
        else:
            d["rate_trip"] = "-"
            d["trips"] = "-"
            d["step"] = "rate"
            await q.edit_message_text("Введите ставку или «-»:")
    elif action == "objcount":
        d["object_count"] = int(parts[1]) + 1
        d["object_index"] = 1
        d["objects"] = []
        await q.edit_message_text("Количество объектов выбрано.")
        await ask_ref(q.message, context, "objects", "dump_object")
    elif action == "payment":
        d["payment"] = PAYMENT_STATUSES[int(parts[1])]
        d["step"] = "note"
        await q.edit_message_text("Введите примечание или «-»:")
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
        d["step"] = "edit_command"
        await q.edit_message_text(
            "Введите изменение в формате:\nномер_колонки=новое значение\n"
            "Например: 8=09:00\nНомера колонок смотрите в первой строке таблицы."
        )
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
            await ask_machine_driver(update.message, context)
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
            await update.message.reply_text("Введите время окончания ЧЧ:ММ или «-»:")
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
            await ask_payment(update, context)
        elif step == "rate_trip":
            d["rate_trip"] = number_or_dash(value)
            d["step"] = "trips"
            await update.message.reply_text("Введите количество рейсов или «-»:")
        elif step == "trips":
            d["trips"] = number_or_dash(value)
            await ask_payment(update, context)
        elif step == "dump_rate":
            d["current"]["rate_trip"] = number_or_dash(value)
            d["step"] = "dump_trips"
            await update.message.reply_text("Введите количество рейсов или «-»:")
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
                await ask_payment(update, context)
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
                summary(d), reply_markup=buttons(["Сохранить", "Отменить"], "confirm")
            )
        elif step == "edit_command":
            col_s, new_value = value.split("=", 1)
            col = int(col_s)
            special, dump, _, _ = initialize_sheets()
            ws = special if d["edit_sheet"] == "special" else dump
            ws.update_cell(d["edit_row"], col, new_value.strip())
            await update.message.reply_text("✅ Ячейка изменена.", reply_markup=menu())
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


async def ask_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["step"] = "payment"
    await update.effective_message.reply_text(
        "Выберите статус оплаты:",
        reply_markup=buttons(PAYMENT_STATUSES, "payment"),
    )


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
            d["object"],
            d["customer"],
            d["start"],
            d["end"],
            d["hours"],
            d["rate_type"],
            d.get("rate", "-"),
            d.get("rate_trip", "-"),
            d.get("trips", "-"),
            d["amount"],
            d["payment"],
            d["note"],
            datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            user.full_name,
            f"@{user.username}" if user.username else "",
            str(q.message.chat.id),
        ]
        row_num = save_row(special, row)
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
                        obj["object"],
                        obj["customer"],
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
                d["payment"],
                d["note"],
                datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                user.full_name,
                f"@{user.username}" if user.username else "",
                str(q.message.chat.id),
                build_customer_filter_text(d["objects"]),
            ]
        )
        row_num = save_row(dump, row)
        tab = SHEET_DUMP
    await q.edit_message_text(f"✅ Сохранено. Вкладка: {tab}. Строка: {row_num}")
    await q.message.reply_text("Выберите действие:", reply_markup=menu())
    context.user_data.clear()


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
    initialize_sheets()
    build().run_polling(drop_pending_updates=False)

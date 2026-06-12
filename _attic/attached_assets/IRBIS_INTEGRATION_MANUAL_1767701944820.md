# Руководство по интеграции библиотечного RFID-шкафа с ИРБИС64

## Оглавление

1. [Архитектура системы](#1-архитектура-системы)
2. [RFID-считыватели](#2-rfid-считыватели)
3. [Структура данных ИРБИС](#3-структура-данных-ирбис)
4. [Подключение к ИРБИС](#4-подключение-к-ирбис)
5. [Бизнес-процессы](#5-бизнес-процессы)
6. [Примеры кода](#6-примеры-кода)
7. [Конфигурация](#7-конфигурация)
8. [Обработка ошибок](#8-обработка-ошибок)

---

## 1. Архитектура системы

### 1.1 Общая схема

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         БИБЛИОТЕЧНЫЙ RFID-ШКАФ                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │ ACR1281U-C      │     │ ACR1281U-C      │     │ IQRFID-5102     │   │
│  │ (NFC 13.56MHz)  │     │ (NFC 13.56MHz)  │     │ (UHF 860-960MHz)│   │
│  │                 │     │                 │     │                 │   │
│  │ Библиотечные    │     │ ЕКП карты       │     │ Метки книг      │   │
│  │ карты читателей │     │ (Единая карта   │     │ (EPC-96)        │   │
│  │                 │     │  петербуржца)   │     │                 │   │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘   │
│           │                       │                       │             │
│           │    UID (4-7 байт)     │    UID (4-7 байт)     │   EPC-96    │
│           └───────────┬───────────┘                       │             │
│                       │                                   │             │
│                       ▼                                   ▼             │
│           ┌───────────────────────┐           ┌───────────────────────┐ │
│           │   Идентификация       │           │   Идентификация       │ │
│           │   читателя            │           │   книги/экземпляра    │ │
│           └───────────┬───────────┘           └───────────┬───────────┘ │
│                       │                                   │             │
│                       └─────────────┬─────────────────────┘             │
│                                     │                                   │
│                                     ▼                                   │
│                       ┌─────────────────────────┐                       │
│                       │    Сервер управления    │                       │
│                       │    (Python/C#)          │                       │
│                       └─────────────┬───────────┘                       │
│                                     │                                   │
└─────────────────────────────────────┼───────────────────────────────────┘
                                      │
                                      │ TCP/IP (порт 6666)
                                      ▼
                        ┌─────────────────────────┐
                        │      ИРБИС64 Сервер     │
                        │                         │
                        │  ┌─────────┐ ┌───────┐  │
                        │  │  IBIS   │ │  RDR  │  │
                        │  │ (книги) │ │(читат)│  │
                        │  └─────────┘ └───────┘  │
                        └─────────────────────────┘
```

### 1.2 Базы данных ИРБИС

| База данных | Назначение | Ключевые поля |
|-------------|------------|---------------|
| **IBIS** | Каталог книг | 903 (шифр), 910 (экземпляры) |
| **RDR** | Читатели | 30 (идентификатор/UID), 40 (выдачи) |

---

## 2. RFID-считыватели

### 2.1 Считыватели карт читателей (ACR1281U-C)

**Технические характеристики:**
- Частота: 13.56 MHz (NFC/HF)
- Протокол: PC/SC (winscard.dll)
- Поддерживаемые карты: MIFARE, ISO 14443

**Получение UID карты:**

```csharp
// APDU команда для чтения UID
byte[] apduGetUid = new byte[] { 0xFF, 0xCA, 0x00, 0x00, 0x00 };

// Ответ: [UID bytes...] [SW1=0x90] [SW2=0x00]
// Пример: 04 AB CD EF 12 34 56 90 00
//         └─────────────────┘ └────┘
//              UID (7 байт)   Статус OK
```

**Формат UID:**
- 4 байта (MIFARE Classic): `AB:CD:EF:12`
- 7 байт (MIFARE Ultralight/DESFire): `04:AB:CD:EF:12:34:56`

### 2.2 Считыватель меток книг (IQRFID-5102)

**Технические характеристики:**
- Частота: 860-960 MHz (UHF)
- Протокол: EPC Gen2
- Формат данных: EPC-96 (12 байт = 24 hex символа)

**Структура EPC-96:**

```
┌────────────────────────────────────────────────────────────────┐
│                        EPC-96 (96 бит)                         │
├──────────┬──────────┬──────────────────────────────────────────┤
│ Header   │ Filter   │ Partition + Company + Item Reference     │
│ (8 бит)  │ (3 бита) │ (85 бит)                                 │
├──────────┴──────────┴──────────────────────────────────────────┤
│ Пример: 30 08 33 B2 DD F0 14 00 00 00 12 34                   │
│         └─────────────────────────────────────────┘            │
│                    24 hex символа                              │
└────────────────────────────────────────────────────────────────┘
```

**Варианты использования для поиска:**
- Полный EPC: `3008 33B2 DDF0 1400 0000 1234`
- Последние 16 символов: `1400 0000 1234`
- Последние 8 символов: `0000 1234` (инвентарный номер)

### 2.3 Нормализация идентификаторов

Система автоматически пробует множество вариантов одного UID:

```python
def make_uid_variants(uid: str) -> list[str]:
    """Генерация вариантов UID для поиска в ИРБИС"""
    
    # Очистка: убираем пробелы, дефисы, двоеточия
    hex_only = uid.upper().replace(" ", "").replace("-", "").replace(":", "")
    
    variants = []
    
    # 1. Базовый HEX
    variants.append(hex_only)                    # ABCDEF12
    
    # 2. С разделителями
    variants.append(insert_every2(hex_only, ":"))  # AB:CD:EF:12
    variants.append(insert_every2(hex_only, "-"))  # AB-CD-EF-12
    
    # 3. Реверс байтов (для некоторых карт)
    rev_hex = reverse_by_byte(hex_only)
    variants.append(rev_hex)                     # 12EFCDAB
    variants.append(insert_every2(rev_hex, ":"))
    variants.append(insert_every2(rev_hex, "-"))
    
    # 4. Десятичное представление
    dec_value = str(int(hex_only, 16))
    variants.append(dec_value)                   # 2882400018
    variants.append(dec_value.zfill(10))         # 0002882400018
    
    # 5. Десятичное реверса
    rev_dec = str(int(rev_hex, 16))
    variants.append(rev_dec)
    variants.append(rev_dec.zfill(10))
    
    return variants


def insert_every2(hex_str: str, sep: str) -> str:
    """AB:CD:EF:12"""
    return sep.join(hex_str[i:i+2] for i in range(0, len(hex_str), 2))


def reverse_by_byte(hex_str: str) -> str:
    """ABCDEF12 -> 12EFCDAB"""
    bytes_list = [hex_str[i:i+2] for i in range(0, len(hex_str), 2)]
    return "".join(reversed(bytes_list))
```

---

## 3. Структура данных ИРБИС

### 3.1 База читателей (RDR)

#### Поле 30 — Идентификатор читателя (читательский билет / UID карты)

```
Поле 30: ABC123DEF456
         └──────────┘
          UID карты (индексируется как RI=)
```

**Индекс для поиска:** `RI=` (Reader ID)

#### Поле 40 — Запись о выдаче/возврате книги

```
Поле 40 (повторяющееся):
┌─────────────────────────────────────────────────────────────────────┐
│ ^A - Шифр книги (из поля 903 книги)                                │
│ ^B - Инвентарный номер экземпляра (из 910^b книги)                 │
│ ^C - Краткое библиографическое описание                            │
│ ^D - Дата выдачи (YYYYMMDD)                                        │
│ ^E - Дата предполагаемого возврата (YYYYMMDD)                      │
│ ^F - Дата фактического возврата (YYYYMMDD или "******" если выдана)│
│ ^G - База данных каталога (IBIS)                                   │
│ ^H - RFID-метка книги (EPC или UID)                                │
│ ^I - Оператор (логин)                                              │
│ ^K - Место хранения (из 910^d книги)                               │
│ ^R - Место возврата                                                │
│ ^V - Место выдачи (MaskMrg)                                        │
│ ^Z - Уникальный идентификатор записи (GUID)                        │
│ ^1 - Время выдачи (HHMMSS)                                         │
│ ^2 - Время возврата (HHMMSS)                                       │
└─────────────────────────────────────────────────────────────────────┘
```

**Пример записи о выдаче:**
```
40#^A821.161.1^B12345^CПушкин А.С. Евгений Онегин^D20250106^E20250206^F******^GIBIS^H3008DDF014000001234^IMASTER^KАбонемент^V09^Z8e8aceg2af2ge72e78^1143052
```

**Пример записи после возврата:**
```
40#^A821.161.1^B12345^D20250106^E20250206^F20250115^GIBIS^H3008DDF014000001234^IMASTER^KАбонемент^R09^V09^Z8e8aceg2af2ge72e78^1143052^2101530
```

**Индекс для поиска выданных книг:** `HIN=` (по RFID метке книги в поле 40^H)

### 3.2 База книг (IBIS)

#### Поле 903 — Шифр хранения

```
903#821.161.1
```

#### Поле 910 — Экземпляры (повторяющееся)

```
Поле 910 (повторяющееся для каждого экземпляра):
┌─────────────────────────────────────────────────────────────────────┐
│ ^a - Статус экземпляра:                                            │
│      "0" = На месте (доступен)                                     │
│      "1" = Выдан                                                   │
│      "C" = Списан                                                  │
│      "U" = Утерян                                                  │
│ ^b - Инвентарный номер                                             │
│ ^c - Дата поступления (YYYYMMDD)                                   │
│ ^d - Место хранения (сигла)                                        │
│ ^h - RFID-метка (EPC-96 или UID)                                   │
│ ^f - Номер записи выдачи (опционально)                             │
└─────────────────────────────────────────────────────────────────────┘
```

**Пример экземпляра на месте:**
```
910#^a0^b12345^c20200115^dАбонемент^h3008DDF014000001234
```

**Пример выданного экземпляра:**
```
910#^a1^b12345^c20200115^dАбонемент^h3008DDF014000001234
```

**Индексы для поиска книг по RFID:**
- `H=` — по полю 910^h
- `HI=` — альтернативный индекс
- `RF=` / `RFID=` — если настроен отдельный индекс
- `IN=` — по инвентарному номеру (910^b)

### 3.3 Индексы и поисковые выражения

| Что ищем | Индекс | Пример запроса |
|----------|--------|----------------|
| Читатель по UID карты | RI= | `"RI=ABCDEF12"` |
| Читатель по ЕКП | EKP= | `"EKP=123456789"` (если настроен) |
| Книга по RFID метке | H= | `"H=3008DDF014000001234"` |
| Книга по инв. номеру | IN= | `"IN=12345"` |
| Читатель с выданной книгой | HIN= | `"HIN=3008DDF014000001234"` |

---

## 4. Подключение к ИРБИС

### 4.1 Параметры подключения

```python
IRBIS_CONFIG = {
    "host": "127.0.0.1",      # Адрес сервера ИРБИС64
    "port": 6666,             # Порт (стандартный)
    "username": "MASTER",      # Логин
    "password": "MASTERKEY",   # Пароль
    "database": "IBIS",        # База по умолчанию
    "workstation": "C",        # Тип АРМ (C = Каталогизатор)
}
```

### 4.2 Формат команд ИРБИС64

Клиент-серверный протокол ИРБИС64 использует текстовые команды:

```
Запрос:
┌──────────────────────────────────────────────────────────┐
│ <команда>\r\n                                            │
│ <workstation>\r\n                                        │
│ <command_code>\r\n                                       │
│ <client_id>\r\n                                          │
│ <sequence>\r\n                                           │
│ <password>\r\n                                           │
│ <username>\r\n                                           │
│ <параметры...>\r\n                                       │
└──────────────────────────────────────────────────────────┘

Ответ:
┌──────────────────────────────────────────────────────────┐
│ <return_code>\r\n                                        │
│ <данные...>                                              │
└──────────────────────────────────────────────────────────┘
```

### 4.3 Базовый класс подключения (Python)

```python
import socket
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class IrbisConfig:
    host: str = "127.0.0.1"
    port: int = 6666
    username: str = "MASTER"
    password: str = "MASTERKEY"
    database: str = "IBIS"
    workstation: str = "C"


class IrbisClient:
    """Клиент для работы с ИРБИС64"""
    
    def __init__(self, config: IrbisConfig):
        self.config = config
        self.client_id = 100000
        self.sequence = 1
        self.connected = False
    
    def connect(self) -> bool:
        """Подключение к серверу"""
        try:
            # Команда A - регистрация
            response = self._execute_command("A", [
                self.config.username,
                self.config.password,
            ])
            self.connected = response.return_code == 0
            return self.connected
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Отключение от сервера"""
        if self.connected:
            self._execute_command("B", [self.config.username])
            self.connected = False
    
    def search(self, database: str, expression: str) -> List[int]:
        """Поиск записей, возвращает список MFN"""
        response = self._execute_command("K", [
            database,
            expression,
            "0",  # количество записей (0 = все)
            "1",  # первая запись
        ])
        
        if response.return_code < 0:
            return []
        
        # Парсим MFN из ответа
        mfn_list = []
        for line in response.data.split("\r\n"):
            if line.strip().isdigit():
                mfn_list.append(int(line.strip()))
        return mfn_list
    
    def read_record(self, database: str, mfn: int) -> Optional[dict]:
        """Чтение записи по MFN"""
        response = self._execute_command("C", [
            database,
            str(mfn),
        ])
        
        if response.return_code < 0:
            return None
        
        return self._parse_record(response.data)
    
    def search_read(self, database: str, expression: str) -> List[dict]:
        """Поиск и чтение записей одной командой"""
        response = self._execute_command("K", [
            database,
            expression,
            "0",
            "1",
            "@",  # формат = полная запись
        ])
        
        if response.return_code < 0:
            return []
        
        # Парсим записи
        records = []
        for record_text in response.data.split("\x1D"):  # Разделитель записей
            if record_text.strip():
                record = self._parse_record(record_text)
                if record:
                    records.append(record)
        return records
    
    def write_record(self, database: str, record: dict) -> bool:
        """Запись/обновление записи"""
        record_text = self._format_record(record)
        response = self._execute_command("D", [
            database,
            "0",  # блокировка
            "1",  # актуализация
            record_text,
        ])
        return response.return_code >= 0
    
    def format_record(self, database: str, mfn: int, format_str: str) -> str:
        """Форматирование записи"""
        response = self._execute_command("G", [
            database,
            str(mfn),
            format_str,
        ])
        return response.data if response.return_code >= 0 else ""
    
    def _execute_command(self, command: str, params: List[str]) -> 'IrbisResponse':
        """Выполнение команды на сервере"""
        # Формируем запрос
        lines = [
            command,
            self.config.workstation,
            command,
            str(self.client_id),
            str(self.sequence),
            self.config.password,
            self.config.username,
            "",  # пустая строка
            "",
            "",
        ]
        lines.extend(params)
        
        request = "\r\n".join(lines)
        
        # Отправляем
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(30)
            sock.connect((self.config.host, self.config.port))
            
            # Формат: длина + данные
            data = request.encode("utf-8")
            header = f"{len(data)}\r\n".encode("utf-8")
            sock.sendall(header + data)
            
            # Читаем ответ
            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
        
        self.sequence += 1
        
        # Парсим ответ
        response_text = response_data.decode("utf-8", errors="replace")
        return self._parse_response(response_text)
    
    def _parse_response(self, text: str) -> 'IrbisResponse':
        """Парсинг ответа сервера"""
        lines = text.split("\r\n")
        return_code = int(lines[0]) if lines and lines[0].lstrip("-").isdigit() else -1
        data = "\r\n".join(lines[1:]) if len(lines) > 1 else ""
        return IrbisResponse(return_code, data)
    
    def _parse_record(self, text: str) -> Optional[dict]:
        """Парсинг записи в формате ИРБИС"""
        record = {"mfn": 0, "fields": {}}
        
        for line in text.split("\x1E"):  # Разделитель полей
            if "#" in line:
                tag, value = line.split("#", 1)
                tag = tag.strip()
                if tag.isdigit():
                    if tag not in record["fields"]:
                        record["fields"][tag] = []
                    record["fields"][tag].append(value)
            elif line.startswith("0 "):
                # MFN в начале записи
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    record["mfn"] = int(parts[1])
        
        return record if record["fields"] else None
    
    def _format_record(self, record: dict) -> str:
        """Форматирование записи для отправки"""
        lines = [f"0 {record.get('mfn', 0)}#0"]
        
        for tag, values in record.get("fields", {}).items():
            for value in values:
                lines.append(f"{tag}#{value}")
        
        return "\x1E".join(lines)


@dataclass
class IrbisResponse:
    return_code: int
    data: str
```

---

## 5. Бизнес-процессы

### 5.1 Авторизация читателя

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ПРОЦЕСС АВТОРИЗАЦИИ                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Читатель прикладывает карту                                    │
│                    │                                                │
│                    ▼                                                │
│  2. Считыватель читает UID                                         │
│     UID = "04:AB:CD:EF:12:34:56"                                   │
│                    │                                                │
│                    ▼                                                │
│  3. Генерация вариантов UID                                        │
│     - 04ABCDEF123456                                               │
│     - 04:AB:CD:EF:12:34:56                                         │
│     - 563412EFCDAB04 (реверс)                                      │
│     - 1234567890123456 (decimal)                                   │
│                    │                                                │
│                    ▼                                                │
│  4. Поиск в ИРБИС (RDR)                                            │
│     Запрос: "RI={uid_variant}"                                     │
│                    │                                                │
│         ┌─────────┴─────────┐                                      │
│         │                   │                                      │
│     Найден              Не найден                                  │
│         │                   │                                      │
│         ▼                   ▼                                      │
│  5a. Сохранить MFN    5b. Отказ                                    │
│      читателя             "Карта не                                │
│      LastReaderMfn        зарегистрирована"                        │
│         │                                                          │
│         ▼                                                          │
│  6. Авторизация успешна                                            │
│     Показать ФИО читателя                                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Код авторизации:**

```python
class LibraryService:
    def __init__(self, irbis: IrbisClient):
        self.irbis = irbis
        self.readers_db = "RDR"
        self.books_db = "IBIS"
        self.current_reader_mfn = None
        self.current_reader_info = None
    
    def validate_card(self, uid: str) -> tuple[bool, str]:
        """
        Авторизация читателя по UID карты
        
        Returns:
            (success, message) - результат и сообщение
        """
        if not uid or not uid.strip():
            return False, "Пустой UID карты"
        
        # Паттерны поиска (можно расширить для ЕКП)
        search_patterns = [
            '"RI={0}"',      # Стандартный индекс читательского билета
            '"EKP={0}"',     # Индекс ЕКП (если настроен)
        ]
        
        # Пробуем все варианты UID
        for uid_variant in make_uid_variants(uid):
            for pattern in search_patterns:
                expression = pattern.format(uid_variant)
                
                records = self.irbis.search_read(self.readers_db, expression)
                
                if records:
                    record = records[0]
                    self.current_reader_mfn = record["mfn"]
                    self.current_reader_info = self._extract_reader_info(record)
                    
                    return True, f"Добро пожаловать, {self.current_reader_info['name']}!"
        
        self.current_reader_mfn = None
        self.current_reader_info = None
        return False, "Карта не зарегистрирована в системе"
    
    def _extract_reader_info(self, record: dict) -> dict:
        """Извлечение информации о читателе из записи"""
        fields = record.get("fields", {})
        
        # Поле 10 - ФИО (формат может отличаться)
        name_parts = []
        if "10" in fields:
            name_parts = fields["10"][0].split("^") if fields["10"] else []
        
        return {
            "mfn": record["mfn"],
            "name": " ".join(name_parts) if name_parts else "Неизвестный читатель",
            "ticket": fields.get("30", [""])[0],  # Читательский билет
        }
```

### 5.2 Выдача книги (TAKE)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ПРОЦЕСС ВЫДАЧИ КНИГИ                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Предусловие: Читатель авторизован (LastReaderMfn известен)        │
│                                                                     │
│  1. Читатель сканирует книгу                                       │
│     RFID = "3008DDF014000001234"                                   │
│                    │                                                │
│                    ▼                                                │
│  2. Поиск книги в ИРБИС (IBIS)                                     │
│     Запрос: "H={rfid}"                                             │
│     Также пробуем: последние 16 и 8 символов                       │
│                    │                                                │
│         ┌─────────┴─────────┐                                      │
│         │                   │                                      │
│     Найдена             Не найдена                                 │
│         │                   │                                      │
│         ▼                   ▼                                      │
│  3a. Проверка статуса  3b. Ошибка                                  │
│      910^a = "0"?          "Книга не найдена"                      │
│         │                                                          │
│    ┌────┴────┐                                                     │
│    │         │                                                     │
│  "0"       "1"                                                     │
│ (свободна) (выдана)                                                │
│    │         │                                                     │
│    ▼         ▼                                                     │
│  4a.      4b. Ошибка                                               │
│ Продолжить   "Книга уже выдана"                                    │
│    │                                                               │
│    ▼                                                               │
│  5. Добавить поле 40 в запись читателя (RDR)                       │
│     ^A=шифр ^B=инв ^C=описание ^D=дата ^E=срок                     │
│     ^F=****** ^G=IBIS ^H=rfid ^I=оператор ^V=место                 │
│                    │                                                │
│                    ▼                                                │
│  6. Обновить статус книги (IBIS)                                   │
│     910^a = "1" (выдана)                                           │
│                    │                                                │
│                    ▼                                                │
│  7. Выдача завершена                                               │
│     Показать описание книги                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Код выдачи:**

```python
from datetime import datetime, timedelta


def issue_book(self, book_rfid: str) -> tuple[bool, str]:
    """
    Выдача книги читателю
    
    Returns:
        (success, message) - результат и описание книги или ошибка
    """
    if not self.current_reader_mfn:
        return False, "Сначала авторизуйтесь (приложите карту)"
    
    # 1. Нормализация RFID
    rfid = normalize_rfid(book_rfid)
    if not rfid:
        return False, "Некорректная RFID-метка"
    
    # 2. Поиск книги
    book_record = self._find_book_by_rfid(rfid)
    if not book_record:
        return False, "Книга не найдена в каталоге"
    
    # 3. Поиск нужного экземпляра в поле 910
    exemplar = self._find_exemplar_by_rfid(book_record, rfid)
    if not exemplar:
        return False, "Экземпляр с данной RFID-меткой не найден"
    
    # 4. Проверка статуса
    if exemplar.get("status") == "1":
        return False, "Книга уже выдана другому читателю"
    
    # 5. Добавляем запись в поле 40 читателя
    success = self._append_reader_field40(
        reader_mfn=self.current_reader_mfn,
        book_record=book_record,
        exemplar=exemplar,
        rfid=rfid
    )
    if not success:
        return False, "Ошибка записи в карточку читателя"
    
    # 6. Обновляем статус экземпляра на "1" (выдан)
    success = self._update_exemplar_status(book_record, rfid, "1")
    if not success:
        return False, "Ошибка обновления статуса книги"
    
    # 7. Возвращаем описание
    brief = self._format_book_brief(book_record)
    return True, brief


def _find_book_by_rfid(self, rfid: str) -> Optional[dict]:
    """Поиск книги по RFID с пробой разных вариантов"""
    
    # Варианты поиска: полный RFID, последние 16 и 8 символов
    search_variants = [rfid]
    if len(rfid) >= 16:
        search_variants.append(rfid[-16:])
    if len(rfid) >= 8:
        search_variants.append(rfid[-8:])
    
    # Паттерны индексов
    patterns = ['"H={0}"', '"HI={0}"', '"RF={0}"', '"RFID={0}"', '"IN={0}"']
    
    for variant in search_variants:
        for pattern in patterns:
            expression = pattern.format(variant)
            records = self.irbis.search_read(self.books_db, expression)
            if records:
                return records[0]
    
    return None


def _find_exemplar_by_rfid(self, book_record: dict, rfid: str) -> Optional[dict]:
    """Поиск экземпляра (910) по RFID внутри записи книги"""
    
    fields = book_record.get("fields", {})
    field_910_list = fields.get("910", [])
    
    for field_910 in field_910_list:
        subfields = parse_subfields(field_910)
        exemplar_rfid = normalize_rfid(subfields.get("h", ""))
        
        # Сравнение с учётом "хвостового" совпадения
        if exemplar_rfid == rfid or rfid.endswith(exemplar_rfid) or exemplar_rfid.endswith(rfid):
            return {
                "status": subfields.get("a", "0"),
                "inventory": subfields.get("b", ""),
                "location": subfields.get("d", ""),
                "rfid": exemplar_rfid,
                "raw": field_910,
            }
    
    return None


def _append_reader_field40(self, reader_mfn: int, book_record: dict, 
                           exemplar: dict, rfid: str) -> bool:
    """Добавление записи о выдаче в поле 40 читателя"""
    
    # Читаем запись читателя
    reader_record = self.irbis.read_record(self.readers_db, reader_mfn)
    if not reader_record:
        return False
    
    # Формируем данные для поля 40
    now = datetime.now()
    loan_days = 30  # Срок выдачи (можно из конфига)
    
    fields = book_record.get("fields", {})
    shelfmark = fields.get("903", [""])[0]  # Шифр
    brief = self._format_book_brief(book_record)
    
    # Собираем подполя
    field40_value = "".join([
        f"^A{shelfmark}",                                    # Шифр
        f"^B{exemplar['inventory']}",                        # Инв. номер
        f"^C{brief}",                                        # Описание
        f"^D{now.strftime('%Y%m%d')}",                       # Дата выдачи
        f"^E{(now + timedelta(days=loan_days)).strftime('%Y%m%d')}",  # Срок возврата
        f"^F******",                                         # Не возвращена
        f"^G{self.books_db}",                                # БД каталога
        f"^H{rfid}",                                         # RFID метка
        f"^I{self.irbis.config.username}",                   # Оператор
        f"^K{exemplar['location']}",                         # Место хранения
        f"^V09",                                             # Место выдачи
        f"^1{now.strftime('%H%M%S')}",                       # Время выдачи
        f"^Z{generate_guid()}",                              # Уникальный ID
    ])
    
    # Добавляем поле 40
    if "40" not in reader_record["fields"]:
        reader_record["fields"]["40"] = []
    reader_record["fields"]["40"].append(field40_value)
    
    # Сохраняем
    return self.irbis.write_record(self.readers_db, reader_record)


def _update_exemplar_status(self, book_record: dict, rfid: str, new_status: str) -> bool:
    """Обновление статуса экземпляра (910^a)"""
    
    fields = book_record.get("fields", {})
    field_910_list = fields.get("910", [])
    
    updated = False
    for i, field_910 in enumerate(field_910_list):
        subfields = parse_subfields(field_910)
        exemplar_rfid = normalize_rfid(subfields.get("h", ""))
        
        if exemplar_rfid == rfid or rfid.endswith(exemplar_rfid) or exemplar_rfid.endswith(rfid):
            # Обновляем статус
            subfields["a"] = new_status
            field_910_list[i] = format_subfields(subfields)
            updated = True
            break
    
    if not updated:
        return False
    
    book_record["fields"]["910"] = field_910_list
    return self.irbis.write_record(self.books_db, book_record)
```

### 5.3 Возврат книги (GIVE)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ПРОЦЕСС ВОЗВРАТА КНИГИ                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ВАЖНО: Возврат ТРЕБУЕТ авторизации читателя!                      │
│  Принимаем только книги, записанные на текущего читателя.          │
│                                                                     │
│  Предусловие: Читатель авторизован (LastReaderMfn известен)        │
│                                                                     │
│  1. Читатель прикладывает карту (авторизация)                      │
│                    │                                                │
│                    ▼                                                │
│  2. Книга помещается в окно возврата                               │
│     RFID = "3008DDF014000001234"                                   │
│                    │                                                │
│                    ▼                                                │
│  3. Проверка: книга записана на ЭТОГО читателя?                    │
│     Ищем в записи текущего читателя:                               │
│     поле 40^H = rfid И 40^F = "******"                             │
│                    │                                                │
│         ┌─────────┴─────────┐                                      │
│         │                   │                                      │
│     Найдена             Не найдена                                 │
│         │                   │                                      │
│         ▼                   ▼                                      │
│  4a. Продолжить       4b. Ошибка                                   │
│      возврат              "Книга не записана                       │
│         │                  на вас" или                             │
│         │                  "Книга уже возвращена"                  │
│         │                                                          │
│         ▼                                                          │
│  5. Закрыть поле 40 (в записи читателя):                           │
│     - Удалить ^C (описание)                                        │
│     - Установить ^F = текущая дата                                 │
│     - Добавить ^2 = время возврата                                 │
│     - Добавить ^R = место возврата                                 │
│                    │                                                │
│                    ▼                                                │
│  6. Обновить статус книги (IBIS)                                   │
│     910^a = "0" (на месте)                                         │
│                    │                                                │
│                    ▼                                                │
│  7. Возврат завершён                                               │
│     Показать описание книги                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Код возврата:**

```python
def return_book(self, book_rfid: str) -> tuple[bool, str]:
    """
    Возврат книги (ТРЕБУЕТ авторизации читателя!)
    Принимает только книги, записанные на текущего читателя.
    
    Returns:
        (success, message) - результат и описание книги или ошибка
    """
    # 1. Проверка авторизации
    if not self.current_reader_mfn:
        return False, "Сначала авторизуйтесь (приложите карту)"
    
    # 2. Нормализация RFID
    rfid = normalize_rfid(book_rfid)
    if not rfid:
        return False, "Некорректная RFID-метка"
    
    # 3. Читаем запись ТЕКУЩЕГО читателя
    reader_record = self.irbis.read_record(self.readers_db, self.current_reader_mfn)
    if not reader_record:
        return False, "Ошибка чтения записи читателя"
    
    # 4. Ищем книгу в выдачах ЭТОГО читателя (поле 40)
    field40_index = self._find_open_loan_field40(reader_record, rfid)
    
    if field40_index is None:
        # Книга не найдена у этого читателя - проверим, выдана ли она вообще
        expression = f'"HIN={rfid}"'
        other_readers = self.irbis.search_read(self.readers_db, expression)
        
        if other_readers:
            return False, "Эта книга записана на другого читателя"
        else:
            return False, "Книга не числится выданной или уже возвращена"
    
    # 5. Закрываем поле 40
    success = self._complete_reader_field40(reader_record, field40_index)
    if not success:
        return False, "Ошибка обновления записи читателя"
    
    # 6. Обновляем статус книги на "0" (на месте)
    book_record = self._find_book_by_rfid(rfid)
    if book_record:
        self._update_exemplar_status(book_record, rfid, "0")
    
    # 7. Возвращаем описание
    brief = self._format_book_brief(book_record) if book_record else "Книга"
    return True, f"Возвращена: {brief}"


def get_reader_active_loans(self) -> list[dict]:
    """
    Получение списка книг, которые читатель может вернуть.
    Используется для отображения на экране перед возвратом.
    """
    if not self.current_reader_mfn:
        return []
    
    reader_record = self.irbis.read_record(self.readers_db, self.current_reader_mfn)
    if not reader_record:
        return []
    
    active_loans = []
    fields = reader_record.get("fields", {})
    
    for field40 in fields.get("40", []):
        subfields = parse_subfields(field40)
        
        # Только активные выдачи (^F = "******")
        if subfields.get("F") == "******":
            active_loans.append({
                "rfid": subfields.get("H", ""),
                "title": subfields.get("C", ""),
                "shelfmark": subfields.get("A", ""),
                "inventory": subfields.get("B", ""),
                "issue_date": subfields.get("D", ""),
                "due_date": subfields.get("E", ""),
            })
    
    return active_loans


def _find_open_loan_field40(self, reader_record: dict, rfid: str) -> Optional[int]:
    """Поиск открытой записи о выдаче (40^F = '******') у конкретного читателя"""
    
    fields = reader_record.get("fields", {})
    field40_list = fields.get("40", [])
    
    for i, field40 in enumerate(field40_list):
        subfields = parse_subfields(field40)
        
        # Проверяем RFID (^H) и что книга не возвращена (^F = "******")
        loan_rfid = normalize_rfid(subfields.get("H", ""))
        return_date = subfields.get("F", "")
        
        # Сравнение с учётом возможного "хвостового" совпадения
        rfid_match = (
            loan_rfid == rfid or 
            rfid.endswith(loan_rfid) or 
            loan_rfid.endswith(rfid)
        )
        
        if rfid_match and return_date == "******":
            return i
    
    return None


def _complete_reader_field40(self, reader_record: dict, field40_index: int) -> bool:
    """Закрытие записи о выдаче при возврате"""
    
    fields = reader_record.get("fields", {})
    field40_list = fields.get("40", [])
    
    if field40_index >= len(field40_list):
        return False
    
    field40 = field40_list[field40_index]
    subfields = parse_subfields(field40)
    
    now = datetime.now()
    
    # Модификации:
    # 1. Удаляем описание (^C) - освобождаем место
    if "C" in subfields:
        del subfields["C"]
    
    # 2. Устанавливаем дату возврата (^F)
    subfields["F"] = now.strftime("%Y%m%d")
    
    # 3. Добавляем время возврата (^2)
    subfields["2"] = now.strftime("%H%M%S")
    
    # 4. Добавляем место возврата (^R)
    subfields["R"] = "09"  # Код места возврата
    
    # 5. Обновляем оператора (^I)
    subfields["I"] = self.irbis.config.username
    
    # Собираем обратно
    field40_list[field40_index] = format_subfields(subfields)
    reader_record["fields"]["40"] = field40_list
    
    return self.irbis.write_record(self.readers_db, reader_record)
```

### 5.4 Загрузка книг в шкаф (LOAD)

```
┌─────────────────────────────────────────────────────────────────────┐
│           ПРОЦЕСС ЗАГРУЗКИ КНИГ БИБЛИОТЕКАРЕМ                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Предусловие: Библиотекарь авторизован служебной картой            │
│                                                                     │
│  1. Библиотекарь открывает шкаф                                    │
│     (сервисный режим)                                              │
│                    │                                                │
│                    ▼                                                │
│  2. Сканирование книг в ячейке                                     │
│     RFID[] = ["3008...1234", "3008...5678", ...]                   │
│                    │                                                │
│                    ▼                                                │
│  3. Для каждой книги:                                              │
│     a) Найти в ИРБИС (IBIS)                                        │
│     b) Проверить статус 910^a                                      │
│     c) Если "0" - книга готова к выдаче                            │
│     d) Если "1" - книга всё ещё числится выданной                  │
│        (возможно, забыли оформить возврат)                         │
│                    │                                                │
│                    ▼                                                │
│  4. Регистрация в локальной БД шкафа:                              │
│     - Ячейка (row, col, depth)                                     │
│     - RFID метка                                                   │
│     - Время загрузки                                               │
│     - Статус: "loaded"                                             │
│                    │                                                │
│                    ▼                                                │
│  5. Книги доступны для выдачи                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Код загрузки:**

```python
def load_books_to_cabinet(self, cell_position: tuple, rfid_list: list[str]) -> list[dict]:
    """
    Загрузка книг в ячейку шкафа
    
    Args:
        cell_position: (row, col, depth) - позиция ячейки
        rfid_list: список RFID меток книг
    
    Returns:
        Список результатов для каждой книги
    """
    results = []
    
    for rfid in rfid_list:
        rfid = normalize_rfid(rfid)
        
        result = {
            "rfid": rfid,
            "cell": cell_position,
            "status": "unknown",
            "title": "",
            "warning": None,
        }
        
        # Поиск книги
        book_record = self._find_book_by_rfid(rfid)
        
        if not book_record:
            result["status"] = "not_found"
            result["warning"] = "Книга не найдена в каталоге"
            results.append(result)
            continue
        
        result["title"] = self._format_book_brief(book_record)
        
        # Проверка статуса экземпляра
        exemplar = self._find_exemplar_by_rfid(book_record, rfid)
        
        if exemplar:
            if exemplar["status"] == "1":
                result["status"] = "issued"
                result["warning"] = "Книга числится выданной! Требуется оформить возврат."
            elif exemplar["status"] == "0":
                result["status"] = "available"
            else:
                result["status"] = exemplar["status"]
                result["warning"] = f"Особый статус: {exemplar['status']}"
        else:
            result["status"] = "no_exemplar"
            result["warning"] = "Экземпляр с данной RFID не найден в записи"
        
        results.append(result)
    
    return results


def verify_cabinet_inventory(self, expected_books: list[dict]) -> dict:
    """
    Сверка инвентаря шкафа с ИРБИС
    
    Args:
        expected_books: [{rfid, cell}, ...] - книги, которые должны быть в шкафу
    
    Returns:
        {
            "total": int,
            "available": int,
            "issued": int,
            "missing": int,
            "problems": [...]
        }
    """
    stats = {
        "total": len(expected_books),
        "available": 0,
        "issued": 0,
        "not_found": 0,
        "problems": [],
    }
    
    for book_info in expected_books:
        rfid = normalize_rfid(book_info["rfid"])
        cell = book_info.get("cell")
        
        book_record = self._find_book_by_rfid(rfid)
        
        if not book_record:
            stats["not_found"] += 1
            stats["problems"].append({
                "rfid": rfid,
                "cell": cell,
                "issue": "Книга не найдена в каталоге"
            })
            continue
        
        exemplar = self._find_exemplar_by_rfid(book_record, rfid)
        
        if exemplar and exemplar["status"] == "0":
            stats["available"] += 1
        elif exemplar and exemplar["status"] == "1":
            stats["issued"] += 1
            stats["problems"].append({
                "rfid": rfid,
                "cell": cell,
                "title": self._format_book_brief(book_record),
                "issue": "Книга в шкафу, но числится выданной в ИРБИС"
            })
        else:
            stats["problems"].append({
                "rfid": rfid,
                "cell": cell,
                "issue": f"Неизвестный статус: {exemplar.get('status') if exemplar else 'N/A'}"
            })
    
    return stats
```

### 5.5 Забор возвращённых книг (UNLOAD)

```
┌─────────────────────────────────────────────────────────────────────┐
│           ПРОЦЕСС ЗАБОРА КНИГ БИБЛИОТЕКАРЕМ                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Предусловие: Библиотекарь авторизован служебной картой            │
│                                                                     │
│  1. Система показывает список возвращённых книг                    │
│     (книги в ячейке приёмника или помеченные как returned)         │
│                    │                                                │
│                    ▼                                                │
│  2. Библиотекарь открывает ячейку приёмника                        │
│                    │                                                │
│                    ▼                                                │
│  3. Сканирование изъятых книг                                      │
│     (подтверждение, что книги забраны)                             │
│                    │                                                │
│                    ▼                                                │
│  4. Для каждой книги:                                              │
│     a) Проверить статус в ИРБИС (должен быть "0")                  │
│     b) Если "1" - автоматически оформить возврат                   │
│     c) Обновить локальную БД шкафа                                 │
│                    │                                                │
│                    ▼                                                │
│  5. Удаление из инвентаря шкафа                                    │
│     status = "removed"                                             │
│                    │                                                │
│                    ▼                                                │
│  6. Книги готовы к размещению на полках                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Код забора:**

```python
def unload_returned_books(self, rfid_list: list[str]) -> list[dict]:
    """
    Забор возвращённых книг из шкафа
    
    Args:
        rfid_list: список RFID меток забираемых книг
    
    Returns:
        Список результатов для каждой книги
    """
    results = []
    
    for rfid in rfid_list:
        rfid = normalize_rfid(rfid)
        
        result = {
            "rfid": rfid,
            "status": "ok",
            "title": "",
            "action": None,
        }
        
        # Поиск книги
        book_record = self._find_book_by_rfid(rfid)
        
        if not book_record:
            result["status"] = "not_found"
            result["action"] = "Требуется ручная проверка"
            results.append(result)
            continue
        
        result["title"] = self._format_book_brief(book_record)
        
        # Проверка статуса
        exemplar = self._find_exemplar_by_rfid(book_record, rfid)
        
        if exemplar and exemplar["status"] == "1":
            # Книга всё ещё числится выданной - автоматический возврат
            success, msg = self.return_book(rfid)
            if success:
                result["action"] = "Автоматически оформлен возврат"
            else:
                result["status"] = "error"
                result["action"] = f"Ошибка авто-возврата: {msg}"
        elif exemplar and exemplar["status"] == "0":
            result["action"] = "Книга корректно возвращена"
        else:
            result["status"] = "warning"
            result["action"] = f"Особый статус: {exemplar.get('status') if exemplar else 'N/A'}"
        
        results.append(result)
    
    return results
```

---

## 6. Примеры кода

### 6.1 Вспомогательные функции

```python
import re
import uuid
from typing import Optional


def normalize_rfid(rfid: str) -> Optional[str]:
    """Нормализация RFID/UID в единый формат (HEX без разделителей)"""
    if not rfid:
        return None
    
    # Убираем пробелы, дефисы, двоеточия
    rfid = rfid.strip().upper()
    rfid = re.sub(r'[\s\-:]+', '', rfid)
    
    # Убираем префикс 0x
    if rfid.startswith("0X"):
        rfid = rfid[2:]
    
    # Оставляем только hex-символы
    rfid = ''.join(c for c in rfid if c in '0123456789ABCDEF')
    
    return rfid if rfid else None


def parse_subfields(field_value: str) -> dict:
    """
    Парсинг подполей ИРБИС
    
    Пример: "^Avalue1^Bvalue2^C" -> {"A": "value1", "B": "value2", "C": ""}
    """
    result = {}
    
    if not field_value:
        return result
    
    # Разбиваем по ^
    parts = field_value.split("^")
    
    for part in parts:
        if not part:
            continue
        
        code = part[0].upper()
        value = part[1:] if len(part) > 1 else ""
        result[code] = value
    
    return result


def format_subfields(subfields: dict) -> str:
    """
    Форматирование подполей обратно в строку ИРБИС
    
    {"A": "value1", "B": "value2"} -> "^Avalue1^Bvalue2"
    """
    parts = []
    
    for code, value in subfields.items():
        parts.append(f"^{code}{value}")
    
    return "".join(parts)


def generate_guid() -> str:
    """Генерация уникального идентификатора (для поля 40^Z)"""
    return uuid.uuid4().hex


def make_uid_variants(uid: str) -> list[str]:
    """Генерация вариантов UID для поиска"""
    hex_only = normalize_rfid(uid)
    if not hex_only:
        return [uid] if uid else []
    
    variants = [hex_only]
    
    # С разделителями
    if len(hex_only) >= 4:
        variants.append(':'.join(hex_only[i:i+2] for i in range(0, len(hex_only), 2)))
        variants.append('-'.join(hex_only[i:i+2] for i in range(0, len(hex_only), 2)))
    
    # Реверс байтов
    bytes_list = [hex_only[i:i+2] for i in range(0, len(hex_only), 2)]
    rev_hex = ''.join(reversed(bytes_list))
    if rev_hex != hex_only:
        variants.append(rev_hex)
        variants.append(':'.join(rev_hex[i:i+2] for i in range(0, len(rev_hex), 2)))
    
    # Десятичное представление
    try:
        dec_value = str(int(hex_only, 16))
        variants.append(dec_value)
        variants.append(dec_value.zfill(10))
        
        rev_dec = str(int(rev_hex, 16))
        if rev_dec != dec_value:
            variants.append(rev_dec)
            variants.append(rev_dec.zfill(10))
    except ValueError:
        pass
    
    return variants
```

### 6.2 Полный пример сервиса

```python
# library_service.py

from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from irbis_client import IrbisClient, IrbisConfig


class LibraryService:
    """Сервис для работы с библиотечным шкафом и ИРБИС"""
    
    def __init__(self, config: IrbisConfig = None):
        self.config = config or IrbisConfig()
        self.irbis = IrbisClient(self.config)
        
        self.readers_db = "RDR"
        self.books_db = "IBIS"
        self.loan_days = 30
        self.location_code = "09"  # Код места (шкаф)
        
        self.current_reader_mfn: Optional[int] = None
        self.current_reader_info: Optional[dict] = None
    
    def connect(self) -> bool:
        """Подключение к ИРБИС"""
        return self.irbis.connect()
    
    def disconnect(self):
        """Отключение от ИРБИС"""
        self.irbis.disconnect()
    
    # === Авторизация ===
    
    def authenticate(self, card_uid: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Авторизация по карте
        
        Returns:
            (success, message, reader_info)
        """
        # Сброс предыдущей сессии
        self.current_reader_mfn = None
        self.current_reader_info = None
        
        if not card_uid:
            return False, "Пустой UID карты", None
        
        # Паттерны поиска
        patterns = ['"RI={0}"', '"EKP={0}"']
        
        for uid_variant in make_uid_variants(card_uid):
            for pattern in patterns:
                expr = pattern.format(uid_variant)
                records = self.irbis.search_read(self.readers_db, expr)
                
                if records:
                    record = records[0]
                    self.current_reader_mfn = record["mfn"]
                    self.current_reader_info = self._parse_reader(record)
                    
                    name = self.current_reader_info.get("name", "Читатель")
                    return True, f"Добро пожаловать, {name}!", self.current_reader_info
        
        return False, "Карта не зарегистрирована", None
    
    def logout(self):
        """Выход из сессии"""
        self.current_reader_mfn = None
        self.current_reader_info = None
    
    # === Выдача ===
    
    def issue_book(self, book_rfid: str) -> Tuple[bool, str]:
        """Выдача книги текущему читателю"""
        if not self.current_reader_mfn:
            return False, "Требуется авторизация"
        
        rfid = normalize_rfid(book_rfid)
        if not rfid:
            return False, "Некорректная RFID-метка"
        
        # Поиск книги
        book = self._find_book(rfid)
        if not book:
            return False, "Книга не найдена"
        
        # Поиск экземпляра
        exemplar = self._find_exemplar(book, rfid)
        if not exemplar:
            return False, "Экземпляр не найден"
        
        if exemplar["status"] == "1":
            return False, "Книга уже выдана"
        
        # Запись в карточку читателя
        if not self._add_loan_record(book, exemplar, rfid):
            return False, "Ошибка записи выдачи"
        
        # Обновление статуса книги
        if not self._set_exemplar_status(book, rfid, "1"):
            return False, "Ошибка обновления статуса"
        
        title = self._get_book_title(book)
        return True, f"Выдано: {title}"
    
    # === Возврат ===
    
    def return_book(self, book_rfid: str) -> Tuple[bool, str]:
        """Возврат книги (ТРЕБУЕТ авторизации!)"""
        if not self.current_reader_mfn:
            return False, "Требуется авторизация"
        
        rfid = normalize_rfid(book_rfid)
        if not rfid:
            return False, "Некорректная RFID-метка"
        
        # Читаем запись ТЕКУЩЕГО читателя
        reader = self.irbis.read_record(self.readers_db, self.current_reader_mfn)
        if not reader:
            return False, "Ошибка чтения записи"
        
        # Ищем книгу в выдачах ЭТОГО читателя
        loan_index = self._find_loan(reader, rfid)
        if loan_index is None:
            # Проверим, не записана ли книга на другого
            expr = f'"HIN={rfid}"'
            others = self.irbis.search_read(self.readers_db, expr)
            if others:
                return False, "Книга записана на другого читателя"
            return False, "Книга не числится на вас"
        
        # Закрытие записи о выдаче
        if not self._close_loan_record(reader, loan_index):
            return False, "Ошибка закрытия выдачи"
        
        # Обновление статуса книги
        book = self._find_book(rfid)
        if book:
            self._set_exemplar_status(book, rfid, "0")
            title = self._get_book_title(book)
            return True, f"Возвращено: {title}"
        
        return True, "Книга возвращена"
    
    def get_my_books(self) -> List[dict]:
        """Список книг текущего читателя (для возврата)"""
        if not self.current_reader_mfn:
            return []
        
        reader = self.irbis.read_record(self.readers_db, self.current_reader_mfn)
        if not reader:
            return []
        
        books = []
        for f40 in reader.get("fields", {}).get("40", []):
            sf = parse_subfields(f40)
            if sf.get("F") == "******":  # Активные выдачи
                books.append({
                    "rfid": sf.get("H", ""),
                    "title": sf.get("C", ""),
                    "shelfmark": sf.get("A", ""),
                    "inventory": sf.get("B", ""),
                    "issue_date": sf.get("D", ""),
                    "due_date": sf.get("E", ""),
                })
        return books
    
    # === Информация ===
    
    def get_book_info(self, book_rfid: str) -> Optional[dict]:
        """Получение информации о книге"""
        rfid = normalize_rfid(book_rfid)
        if not rfid:
            return None
        
        book = self._find_book(rfid)
        if not book:
            return None
        
        exemplar = self._find_exemplar(book, rfid)
        
        return {
            "mfn": book["mfn"],
            "title": self._get_book_title(book),
            "shelfmark": book.get("fields", {}).get("903", [""])[0],
            "status": exemplar["status"] if exemplar else "unknown",
            "status_text": {
                "0": "На месте",
                "1": "Выдана",
                "C": "Списана",
                "U": "Утеряна"
            }.get(exemplar["status"], "Неизвестно") if exemplar else "Неизвестно",
            "inventory": exemplar["inventory"] if exemplar else "",
            "location": exemplar["location"] if exemplar else "",
        }
    
    def get_reader_loans(self, reader_mfn: int = None) -> List[dict]:
        """Получение списка выданных книг читателя"""
        mfn = reader_mfn or self.current_reader_mfn
        if not mfn:
            return []
        
        reader = self.irbis.read_record(self.readers_db, mfn)
        if not reader:
            return []
        
        loans = []
        for field40 in reader.get("fields", {}).get("40", []):
            sf = parse_subfields(field40)
            
            # Только активные выдачи (^F = "******")
            if sf.get("F") == "******":
                loans.append({
                    "shelfmark": sf.get("A", ""),
                    "inventory": sf.get("B", ""),
                    "title": sf.get("C", ""),
                    "issue_date": sf.get("D", ""),
                    "due_date": sf.get("E", ""),
                    "rfid": sf.get("H", ""),
                })
        
        return loans
    
    # === Приватные методы ===
    
    def _find_book(self, rfid: str) -> Optional[dict]:
        """Поиск книги по RFID"""
        variants = [rfid]
        if len(rfid) >= 16:
            variants.append(rfid[-16:])
        if len(rfid) >= 8:
            variants.append(rfid[-8:])
        
        patterns = ['"H={0}"', '"HI={0}"', '"RF={0}"', '"IN={0}"']
        
        for v in variants:
            for p in patterns:
                records = self.irbis.search_read(self.books_db, p.format(v))
                if records:
                    return records[0]
        return None
    
    def _find_exemplar(self, book: dict, rfid: str) -> Optional[dict]:
        """Поиск экземпляра по RFID"""
        for f910 in book.get("fields", {}).get("910", []):
            sf = parse_subfields(f910)
            ex_rfid = normalize_rfid(sf.get("h", ""))
            
            if ex_rfid == rfid or rfid.endswith(ex_rfid) or ex_rfid.endswith(rfid):
                return {
                    "status": sf.get("a", "0"),
                    "inventory": sf.get("b", ""),
                    "location": sf.get("d", ""),
                    "rfid": ex_rfid,
                }
        return None
    
    def _parse_reader(self, record: dict) -> dict:
        """Парсинг записи читателя"""
        fields = record.get("fields", {})
        name_field = fields.get("10", [""])[0]
        
        return {
            "mfn": record["mfn"],
            "name": name_field.replace("^", " ").strip(),
            "ticket": fields.get("30", [""])[0],
        }
    
    def _get_book_title(self, book: dict) -> str:
        """Получение названия книги"""
        fields = book.get("fields", {})
        title = fields.get("200", [""])[0]  # Заглавие
        if "^" in title:
            parts = parse_subfields(title)
            title = parts.get("A", title)
        return title or "[Без названия]"
    
    def _add_loan_record(self, book: dict, exemplar: dict, rfid: str) -> bool:
        """Добавление записи о выдаче"""
        reader = self.irbis.read_record(self.readers_db, self.current_reader_mfn)
        if not reader:
            return False
        
        now = datetime.now()
        fields = book.get("fields", {})
        
        field40 = "".join([
            f"^A{fields.get('903', [''])[0]}",
            f"^B{exemplar['inventory']}",
            f"^C{self._get_book_title(book)}",
            f"^D{now.strftime('%Y%m%d')}",
            f"^E{(now + timedelta(days=self.loan_days)).strftime('%Y%m%d')}",
            "^F******",
            f"^G{self.books_db}",
            f"^H{rfid}",
            f"^I{self.config.username}",
            f"^K{exemplar['location']}",
            f"^V{self.location_code}",
            f"^1{now.strftime('%H%M%S')}",
            f"^Z{generate_guid()}",
        ])
        
        if "40" not in reader["fields"]:
            reader["fields"]["40"] = []
        reader["fields"]["40"].append(field40)
        
        return self.irbis.write_record(self.readers_db, reader)
    
    def _find_loan(self, reader: dict, rfid: str) -> Optional[int]:
        """Поиск активной выдачи по RFID у читателя"""
        for i, f40 in enumerate(reader.get("fields", {}).get("40", [])):
            sf = parse_subfields(f40)
            loan_rfid = normalize_rfid(sf.get("H", ""))
            
            rfid_match = (loan_rfid == rfid or 
                         rfid.endswith(loan_rfid) or 
                         loan_rfid.endswith(rfid))
            
            if rfid_match and sf.get("F") == "******":
                return i
        return None
    
    def _close_loan_record(self, reader: dict, loan_index: int) -> bool:
        """Закрытие записи о выдаче"""
        field40_list = reader.get("fields", {}).get("40", [])
        
        if loan_index >= len(field40_list):
            return False
        
        sf = parse_subfields(field40_list[loan_index])
        now = datetime.now()
        
        if "C" in sf:
            del sf["C"]
        sf["F"] = now.strftime("%Y%m%d")
        sf["2"] = now.strftime("%H%M%S")
        sf["R"] = self.location_code
        sf["I"] = self.config.username
        
        field40_list[loan_index] = format_subfields(sf)
        reader["fields"]["40"] = field40_list
        
        return self.irbis.write_record(self.readers_db, reader)
    
    def _set_exemplar_status(self, book: dict, rfid: str, status: str) -> bool:
        """Установка статуса экземпляра"""
        field910_list = book.get("fields", {}).get("910", [])
        
        for i, f910 in enumerate(field910_list):
            sf = parse_subfields(f910)
            ex_rfid = normalize_rfid(sf.get("h", ""))
            
            if ex_rfid == rfid or rfid.endswith(ex_rfid) or ex_rfid.endswith(rfid):
                sf["a"] = status
                field910_list[i] = format_subfields(sf)
                book["fields"]["910"] = field910_list
                return self.irbis.write_record(self.books_db, book)
        
        return False
```

---

## 7. Конфигурация

### 7.1 Файл конфигурации (config.ini)

```ini
[IRBIS]
Host = 127.0.0.1
Port = 6666
Username = MASTER
Password = MASTERKEY
BooksDb = IBIS
ReadersDb = RDR
Workstation = C

[Loans]
LoanDays = 30
LocationCode = 09

[Search]
; Паттерны поиска читателя по UID (через точку с запятой)
ReaderSearchPatterns = "RI={0}";"EKP={0}"

; Паттерны поиска книги по RFID
BookSearchPatterns = "H={0}";"HI={0}";"RF={0}";"IN={0}"

; Паттерн поиска читателя по RFID выданной книги
LoanSearchPattern = "HIN={0}"

[RFID]
; Попытки вариантов UID (hex, reverse, decimal)
TryUidVariants = true

; Попытки "хвостовых" совпадений для EPC-96
TryTailMatch = true
TailLengths = 16,8
```

### 7.2 Индексы ИРБИС (для администратора)

Необходимые индексы в базе **RDR** (читатели):

```
RI - индекс по полю 30 (читательский билет / UID карты)
EKP - индекс по полю XX (ЕКП, если используется отдельное поле)
HIN - индекс по подполю 40^H (RFID выданной книги)
```

Необходимые индексы в базе **IBIS** (книги):

```
H - индекс по подполю 910^h (RFID метка экземпляра)
IN - индекс по подполю 910^b (инвентарный номер)
```

---

## 8. Обработка ошибок

### 8.1 Коды ошибок ИРБИС

| Код | Описание |
|-----|----------|
| 0 | Успех |
| -1 | Сервер недоступен |
| -2 | Неверный пароль |
| -3 | База данных недоступна |
| -4 | Запись не найдена |
| -140 | Запись удалена |
| -202 | Ошибка поиска |
| -300 | Ошибка блокировки |

### 8.2 Типичные ошибки и решения

| Ситуация | Причина | Решение |
|----------|---------|---------|
| Карта не найдена | UID не в базе | Проверить регистрацию читателя |
| Книга не найдена | RFID не в каталоге | Проверить привязку RFID к экземпляру |
| Книга уже выдана | 910^a = "1" | Сначала оформить возврат |
| Ошибка записи | Блокировка записи | Повторить попытку |
| Таймаут | Сервер перегружен | Увеличить timeout, повторить |

### 8.3 Логирование

```python
import logging
from datetime import datetime

# Настройка логгера
logging.basicConfig(
    filename='irbis_operations.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def log_operation(operation: str, params: dict, result: str):
    """Логирование операции"""
    logging.info(f"{operation}: params={params}, result={result}")

# Пример использования
log_operation(
    "ISSUE",
    {"reader_mfn": 123, "book_rfid": "3008DDF0...", "user": "MASTER"},
    "SUCCESS"
)
```

---

## Приложение А: Справочник полей

### Поле 910 (экземпляры) - полный список подполей

| Код | Название | Описание |
|-----|----------|----------|
| ^a | Статус | 0=на месте, 1=выдан, C=списан, U=утерян |
| ^b | Инв. номер | Инвентарный номер экземпляра |
| ^c | Дата поступления | YYYYMMDD |
| ^d | Место хранения | Сигла (код хранилища) |
| ^e | Цена | Цена в рублях |
| ^f | Номер выдачи | Ссылка на запись выдачи |
| ^h | RFID | RFID-метка экземпляра |
| ^i | Штрих-код | Штрих-код экземпляра |
| ^k | Канал поступления | Код канала |
| ^p | Вид издания | Книга, журнал и т.д. |
| ^u | Шифр | Полочный шифр |
| ^w | Дата выдачи | YYYYMMDD (для выданных) |
| ^y | Срок возврата | YYYYMMDD (для выданных) |

### Поле 40 (выдачи) - полный список подполей

| Код | Название | Описание |
|-----|----------|----------|
| ^A | Шифр | Шифр книги (из 903) |
| ^B | Инв. номер | Инвентарный номер |
| ^C | Описание | Краткое библиографическое описание |
| ^D | Дата выдачи | YYYYMMDD |
| ^E | Срок возврата | YYYYMMDD |
| ^F | Дата возврата | YYYYMMDD или "******" (не возвращена) |
| ^G | БД каталога | IBIS |
| ^H | RFID | RFID-метка книги |
| ^I | Оператор | Логин оператора |
| ^K | Место хранения | Код места (из 910^d) |
| ^R | Место возврата | Код места возврата |
| ^V | Место выдачи | Код места выдачи |
| ^Z | GUID | Уникальный идентификатор записи |
| ^1 | Время выдачи | HHMMSS |
| ^2 | Время возврата | HHMMSS |

---

## Приложение Б: Диаграмма состояний книги

```
                    ┌─────────────────┐
                    │   В КАТАЛОГЕ    │
                    │  (нет в шкафу)  │
                    └────────┬────────┘
                             │
                             │ LOAD (загрузка в шкаф)
                             ▼
┌────────────────────────────────────────────────────┐
│                     В ШКАФУ                        │
│                                                    │
│    ┌──────────┐     ISSUE      ┌──────────┐       │
│    │ ДОСТУПНА │ ─────────────► │  ВЫДАНА  │       │
│    │ (910^a=0)│  (+ авториз.)  │ (910^a=1)│       │
│    └────┬─────┘ ◄───────────── └────┬─────┘       │
│         │      RETURN (+ авториз.)  │             │
│         │      (только своя книга!) │             │
│         │                           │             │
│         │                           │ (читатель   │
│         │                           │  уносит)    │
│         │                           │             │
└─────────┼───────────────────────────┼─────────────┘
          │                           │
          │ UNLOAD                    │ RETURN (+ авториз.)
          │ (забор библиотекарем)     │ (в окно возврата)
          ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│  НА ПОЛКЕ       │         │  В ПРИЁМНИКЕ    │
│  (вне шкафа)    │         │  ШКАФА          │
└─────────────────┘         └────────┬────────┘
                                     │
                                     │ UNLOAD
                                     ▼
                            ┌─────────────────┐
                            │  НА ПОЛКЕ       │
                            │  (вне шкафа)    │
                            └─────────────────┘
```

**Важно:** Все операции с книгами (ISSUE, RETURN) требуют авторизации читателя!
- При RETURN система проверяет, что книга записана именно на этого читателя
- Нельзя вернуть чужую книгу

---

**Версия документа:** 1.0  
**Дата:** 2025-01-06  
**Автор:** Система документирования

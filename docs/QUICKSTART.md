# BookCabinet — Быстрый старт

## 🔧 Среда
- **Разработка:** Windows 11, PowerShell / Windows Terminal
- **Целевая система:** Raspberry Pi 3, ~/bookcabinet/
- **Репозиторий:** Rivega42/- (git pull для обновления)
- **Референс ИРБИС:** github.com/valinerosgordov/RFIDShkafWithIRBIS

## 📡 Подключение к RPi
```powershell
ssh admin42@10.10.31.12   # или по имени: admin42@Shkaf
```

## 🚀 Запуск системы
```bash
cd ~/bookcabinet
git pull                              # обновить код
sudo systemctl restart bookcabinet    # перезапустить сервис
sudo systemctl status bookcabinet     # проверить статус
journalctl -u bookcabinet -f          # логи в реальном времени
```

## 🔌 RFID-считыватели
| Устройство | Частота | Назначение | Статус |
|------------|---------|------------|--------|
| ACR1281U-C | 13.56 MHz | ЕКП (NFC) | ✅ Работает |
| IQRFID-5102 | UHF 900 MHz | Книжные метки / билеты | ⚠️ Макс 3-5см (аппаратно) |
| RRU9816 | UHF 900 MHz | Книжные метки | ✅ Работает ~20см |

## 🎚️ Датчики TCST2103
- **Тип:** Оптопары без внешних резисторов
- **Логика:** ≥95% HIGH = сработал, <95% = свободен
- **Подтяжка:** PUD_UP (встроенная RPi)
- **Тест:** `python3 tools/test_sensors.py`

## ⚡ Критичные нюансы
1. **БП:** минимум 5V/2.5A, иначе WiFi не стартует
2. **Датчики TCST2103:** логика через threshold 95%, без резисторов
3. **Замки:** Open=язычок ОПУЩЕН, Close=язычок ПОДНЯТ (инверсия!)
4. **IQRFID-5102:** мощность фиксирована аппаратно, команды 0x76/0x77 не работают
5. **Конфигурация GPIO:** в файле `config.py`, после изменений — `sudo systemctl restart bookcabinet`
6. **Текущий хоминг XY:** HOME = LEFT + BOTTOM, безопасные скорости `FAST=800`, `SLOW=300`, операторский entrypoint — `python3 tools/homing_pigpio.py`, каноническая реализация — `tools/corexy_motion_v2.py`

## 📁 Ключевые файлы
- `bookcabinet/config.py` — конфигурация GPIO пинов
- `bookcabinet/hardware/sensors.py` — драйвер датчиков TCST2103
- `bookcabinet/hardware/iqrfid5102_driver.py` — драйвер IQRFID-5102
- `bookcabinet/hardware/rru9816_driver.py` — драйвер RRU9816
- `tools/test_sensors.py` — тест датчиков
- `CLAUDE.md` — канонический входной файл для Claude Code по проекту
- `docs/TODO.md` — текущие задачи
- `docs/DEVLOG.md` — журнал решённых проблем

## 🐛 Если что-то не работает
1. WiFi нет → проверь `vcgencmd get_throttled` (должно быть 0x0)
2. RFID молчит → проверь порт: `ls /dev/ttyUSB*`
3. GPIO не работает → проверь config.py и `sudo systemctl restart bookcabinet`
4. Датчики моргают → это норма, threshold 95% фильтрует

## 📚 Документация
- `docs/TODO.md` — текущие задачи
- `docs/DEVLOG.md` — история решённых проблем
- `docs/HARDWARE.md` — инвентарь оборудования

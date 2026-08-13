# my_website_18_07

## Настройка формы

Форма обслуживается Python-сервисом `backend/telegram_form.py`, доступным только
через Nginx по адресу `/api/contact`. Настоящие значения хранятся на сервере в
закрытом файле `/etc/ivashina62-form.env`:

- `TELEGRAM_BOT_TOKEN` — новый токен, полученный у BotFather;
- `TELEGRAM_CHAT_ID` — идентификатор чата для заявок.

Не добавляйте настоящий токен в файлы сайта, GitHub или JavaScript. Файл
`.env.example` содержит только названия необходимых переменных.

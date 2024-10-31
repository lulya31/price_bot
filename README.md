Запуск Скрипта

1) Убедитесь, что у вас установлены все необходимые библиотеки:
**pip3 install requests nest_asyncio python-telegram-bot python-dotenv supabase**

2) Создайте файл .env в корневой директории проекта и добавьте туда свои переменные окружения:

API_KEY=your_telegram_bot_api_key
COINMARKETCAP_API_KEY=your_coinmarketcap_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key


3) Запустите скрипт:

**python3 price_bot.py**
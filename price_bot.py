import requests
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
import asyncio
import logging
from supabase import create_client, Client

# Allow nested event loops
nest_asyncio.apply()

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual API keys
API_KEY = '7990863541:AAG_hH8KwYJWemfeKh1_4a80ZBRrGSD6p8k'
COINMARKETCAP_API_KEY = '0a514240-c93b-4809-8497-f877cca910fd'
SUPABASE_URL = 'https://vidsukivzzxhlbmecziy.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpZHN1a2l2enp4aGxibWVjeml5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mjk0OTU2MDAsImV4cCI6MjA0NTA3MTYwMH0.Mq5UPFZc4rxt3kHjrL1LuDN7Ls-5azPJmRs9mSTZMUg'

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Dictionary for tracking tokens and their threshold values
price_trackers = {}
previous_prices = {}
is_stopped = {}  # Track whether each chat has stopped receiving updates

lock = asyncio.Lock()  # Create a lock for managing access

# List of major cryptocurrencies
major_cryptos = {
    "1": "BTC",
    "1027": "ETH",
    "825": "USDT",
    "1839": "BNB",
    "5426": "SOL",
    "52": "XRP",
    "3408": "USDC",
    "74": "DOGE"
}

def build_keyboard():
    """Builds the keyboard with all buttons including commands."""
    keyboard = [
        [InlineKeyboardButton("Отслеживать токен", callback_data='track')],
        [InlineKeyboardButton("Стоп", callback_data='stop')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    is_stopped[update.effective_chat.id] = False

    info_message = "Информация берется с сайта https://coinmarketcap.com/"
    await update.message.reply_text(info_message)

    await update.message.reply_text('Выберите действие:', reply_markup=build_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Доступные команды:\n"
        "/track <изменение_цены> - Отслеживать изменение цены токена\n"
        "/help - Показать это сообщение\n"
        "/stop - Остановить бота"
    )
    await update.message.reply_text(help_text, reply_markup=build_keyboard())

async def show_tokens(query) -> None:
    keyboard = [[InlineKeyboardButton(token, callback_data=token_id) for token_id, token in major_cryptos.items()]]
    keyboard.append([InlineKeyboardButton("Другой токен", callback_data='other_token')])
    await query.message.reply_text("Выберите токен для отслеживания:", reply_markup=InlineKeyboardMarkup(keyboard))

async def track_token(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await show_tokens(query)

async def handle_token_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    token_id = query.data  # Получаем выбранный ID токена
    current_price = get_token_price(token_id)

    if current_price is not None:
        price_trackers[update.effective_chat.id] = (token_id, None)
        await query.edit_message_text(f"Вы выбрали токен {major_cryptos[token_id]} с ID {token_id}.\nТекущая цена: {current_price:.2f} USD.\nВведите изменение цены в %.\n Формат ввода: /track 0.01")
    else:
        await query.edit_message_text("Не удалось получить текущую цену токена.")

async def receive_price_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) == 2:
        try:
            token_id = context.args[0]
            price_change = float(context.args[1])

            price_trackers[update.effective_chat.id] = (token_id, price_change)

            current_price = get_token_price(token_id)

            if current_price is not None:
                await update.message.reply_text(f'Начато отслеживание изменения цены на {price_change}%. Текущая цена {current_price:.2f} USD.')
                logger.info(f"Начато отслеживание изменения цены на {price_change}%. Текущая цена {current_price:.2f} USD.")
            else:
                await update.message.reply_text('Не удалось получить текущую цену токена.')

        except ValueError:
            await update.message.reply_text('Пожалуйста, введите корректное значение изменения цены.')
        return

    if update.effective_chat.id not in price_trackers:
        await update.message.reply_text('Сначала выберите токен с помощью команды /track.')
        return

    if len(context.args) != 1:
        await update.message.reply_text('Пожалуйста, введите изменение цены в формате /track <изменение_цены>.')
        return

    try:
        price_change = float(context.args[0])
        token_id = price_trackers[update.effective_chat.id][0]

        price_trackers[update.effective_chat.id] = (token_id, price_change)

        current_price = get_token_price(token_id)

        if current_price is not None:
            await update.message.reply_text(f'Начато отслеживание изменения цены на {price_change}%. Текущая цена {current_price:.2f} USD.')
            logger.info(f"Начато отслеживание изменения цены на {price_change}%. Текущая цена {current_price:.2f} USD.")
        else:
            await update.message.reply_text('Не удалось получить текущую цену токена.')

    except ValueError:
        await update.message.reply_text('Пожалуйста, введите корректное значение изменения цены.')

def get_token_price(token_id: str) -> float:
    url = 'https://pro-api.coinmarketcap.com/v2/tools/price-conversion'
    params = {"amount": 1, "id": token_id, "convert": "USD"}
    headers = {'X-CMC_PRO_API_KEY': COINMARKETCAP_API_KEY}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        if 'status' in data and data['status']['error_code'] == 0:
            return data['data']['quote']['USD']['price']

    return None

async def check_prices(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with lock:
        for chat_id in list(price_trackers.keys()):
            if is_stopped.get(chat_id, False):
                logger.info(f"Chat {chat_id} is stopped. Skipping price check.")
                continue

            token_id, price_change = price_trackers[chat_id]
            current_price = get_token_price(token_id)

            if current_price is not None and price_change is not None:
                previous_price = previous_prices.get(chat_id)
                previous_prices[chat_id] = current_price

                if previous_price is not None:
                    price_difference = ((current_price - previous_price) / previous_price) * 100

                    if abs(price_difference) >= abs(price_change):
                        token_name = major_cryptos.get(token_id, token_id)
                        await context.bot.send_message(chat_id=chat_id,
                                                        text=f'Цена токена {token_name} с ID {token_id} изменилась до {current_price:.2f} USD. Изменение: {price_difference:.2f}%.', reply_markup=build_keyboard())

                        user = await context.bot.get_chat(chat_id)
                        nickname = user.username if user.username else user.first_name
                        starting_price = previous_price
                        change_of_price = price_change

                        data = {
                            "nickname": nickname,
                            "cryptocurrency": token_name,
                            "starting_price": starting_price,
                            "change_of_price": change_of_price,
                            "price_after_change": current_price
                        }

                        try:
                            response = supabase.table('bot_data').insert(data).execute()
                            if response.get('status_code') == 201:
                                logger.info(f"Data inserted successfully for chat_id {chat_id}")
                            else:
                                logger.error(f"Failed to insert data for chat_id {chat_id}: {response.get('error')}")
                        except Exception as e:
                            logger.error(f"Exception occurred while inserting data for chat_id {chat_id}: {e}")

async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

   # Handle button clicks based on callback data
    if query.data == 'track':
       await track_token(update, context)
    
    elif query.data in major_cryptos.keys():
       await handle_token_selection(update, context)
    
    elif query.data == 'other_token':
       await query.edit_message_text(
           "Пожалуйста, введите ID токена и желаемое изменение цены в формате:\n/track <id_токена> <изменение_цены>\n\nНапример:\n/track 1 0.01"
       )

    elif query.data == 'stop':
       is_stopped[update.effective_chat.id] = True
       await query.edit_message_text("Бот остановлен. Вы можете запустить его снова. Напишите команду /start.")

async def main() -> None:
   application = ApplicationBuilder().token(API_KEY).build()

   application.add_handler(CommandHandler("start", start))
   application.add_handler(CommandHandler("help", help_command))
   
   application.add_handler(CommandHandler("track", receive_price_change))
   application.add_handler(CallbackQueryHandler(handle_button_click))

   job_queue = application.job_queue
   job_queue.run_repeating(check_prices, interval=10)

   await application.run_polling()

if __name__ == '__main__':
   asyncio.get_event_loop().run_until_complete(main())
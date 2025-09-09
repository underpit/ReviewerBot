import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for the conversation handler
PRODUCT, RATING, REVIEW, CATEGORY = range(4)

# Replace with your bot token and channel ID
import json ; bot_config = json.load(open("bot_config.json")) 
CHANNEL_ID = bot_config["channel_id"]
BOT_TOKEN = bot_config["telegram_bot_token"]

def escape_html(text: str) -> str:
    """Escapes special characters for HTML parsing."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the review collection process."""
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this bot in a private chat.")
        return ConversationHandler.END

    await update.message.reply_text(
        "Что вы хотите оценить?"
    )
    return PRODUCT

async def product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the product name and asks for rating."""
    context.user_data["product"] = update.message.text
    await update.message.reply_text(
        "Дайте оценку от 0 до 5."
    )
    return RATING

async def rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the rating and asks for review text."""
    text = update.message.text
    try:
        rating = int(text)
        if not 0 <= rating <= 5:
            await update.message.reply_text("Дайте оценку от 0 до 5.")
            return RATING
        context.user_data["rating"] = rating
        await update.message.reply_text("Поделитесь впечатлениями о товаре или услуге.")
        return REVIEW
    except ValueError:
        await update.message.reply_text("Введите число от 0 до 5.")
        return RATING

async def review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the review text and asks for category selection."""
    context.user_data["review"] = update.message.text

    # Inline keyboard for category selection
    keyboard = [
        [
            InlineKeyboardButton("Чай", callback_data="чай"),
            InlineKeyboardButton("Доставка", callback_data="доставка"),
            InlineKeyboardButton("Сервис", callback_data="сервис"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Пожалуйста выберите категорию вашего отзыва:", reply_markup=reply_markup
    )
    return CATEGORY

async def category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles category selection, formats the review, and posts to the channel."""
    query = update.callback_query
    await query.answer()
    selected_category = query.data
    context.user_data["category"] = selected_category

    # Escape user inputs for HTML
    product = escape_html(context.user_data["product"])
    review_text = escape_html(context.user_data["review"])
    rating = context.user_data["rating"]
    category_tag = f"отзыв_{selected_category}"

    # Format the review using HTML
    message = (
        f"<b>Товар или услуга</b>: {product}\n"
        f"<b>Рэйтинг</b>: {'⭐' * rating}\n"
        f"<b>Отзыв</b>: {review_text}\n\n"
        f"#отзыв #{category_tag}"
    )

    # Log the message for debugging
    logger.info(f"Attempting to send message: {message}")

    # Post to the channel
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
        await query.edit_message_text("Спасибо! Ваш отзыв опубликован в канале.")
    except Exception as e:
        logger.error(f"Error posting to channel: {e}")
        await query.edit_message_text("Извините, произошла ошибка при публикации вашего отзыва.")
        # Log the problematic message for further inspection
        logger.error(f"Problematic message content: {message}")

    # Clear user data
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the review process."""
    await update.message.reply_text("Отправка отзыва была отменена.")
    context.user_data.clear()
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for review collection
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, product)],
            RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, rating)],
            REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, review)],
            CATEGORY: [CallbackQueryHandler(category)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
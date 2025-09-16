import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from tea import (
    tea_product, tea_photo, tea_photo_reprompt, tea_rating, tea_likes, tea_review_text
)
from service import (
    service_likes, service_likes_handler, service_rating_handler, service_review_text
)
from delivery import (
    delivery_likes, delivery_likes_handler, delivery_rating_handler, delivery_review_text
)
from form import (
    format_tea_review, format_service_review, format_delivery_review
)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# All states defined here to avoid circular imports
CATEGORY = 0
MORE_REVIEWS = 1

# Tea states
TEA_PRODUCT = 2
TEA_PHOTO = 3
TEA_RATING = 4
TEA_LIKES = 5
TEA_REVIEW_TEXT = 6

# Service states (new flow)
SERVICE_LIKES = 7
SERVICE_RATING = 8
SERVICE_REVIEW_TEXT = 9

# Delivery states (new flow)
DELIVERY_LIKES = 10
DELIVERY_RATING = 11
DELIVERY_REVIEW_TEXT = 12
# Common preview state
PREVIEW = 13
# Edit states
EDIT_MENU = 14
EDIT_RATING = 15
EDIT_LIKES = 16
EDIT_PRODUCT = 17
EDIT_REVIEW = 18

# Replace with your bot token and channel ID
import json ; bot_config = json.load(open("bot_config.json")) 
CHANNEL_ID = bot_config["channel_id"]
BOT_TOKEN = bot_config["telegram_bot_token"]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command, shows button to start review."""
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this bot in a private chat.")
        return

    keyboard = ReplyKeyboardMarkup([["Оставить отзыв"]], resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("Приветствую! Нажмите на кнопку «ОСТАВИТЬ ОТЗЫВ» ниже ", reply_markup=keyboard)

async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the review process by asking for category."""
    if update.message.chat.type != "private":
        await update.message.reply_text("Please use this bot in a private chat.")
        return ConversationHandler.END

    # Initialize reviews list
    context.user_data['reviews'] = []

    keyboard = [
        [
            InlineKeyboardButton("ЧАЙ", callback_data="чай"),
            InlineKeyboardButton("СЕРВИС", callback_data="сервис"),
            InlineKeyboardButton("ДОСТАВКА", callback_data="доставка"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("На что пишем отзыв?", reply_markup=reply_markup)
    return CATEGORY

async def category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles category selection and routes to category-specific starting state."""
    query = update.callback_query
    await query.answer()
    selected_category = query.data
    context.user_data['current_category'] = selected_category

    if selected_category == 'чай':
        await query.edit_message_text("Выбранная категория: ЧАЙ	\n\nВведите название продукта:")
        return TEA_PRODUCT
    elif selected_category == 'сервис':
        await query.edit_message_text("Выбранная категория: Сервис")
        # Explicitly start service flow by calling initial likes function
        await service_likes(query, context)
        return SERVICE_LIKES
    elif selected_category == 'доставка':
        await query.edit_message_text("Выбранная категория: Доставка")
        # Explicitly start delivery flow by calling initial likes function
        await delivery_likes(query, context)
        return DELIVERY_LIKES
    
async def preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles preview buttons (confirm or edit)."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'confirm':
        pending_data = context.user_data.pop('pending_data', None)
        if pending_data:
            context.user_data['reviews'].append(pending_data)
        context.user_data.pop('pending_review', None)  # Clean up old
        await query.edit_message_text("Отзыв подтвержден!")

        # Proceed to more reviews
        keyboard = [
            [
                InlineKeyboardButton("Да", callback_data="more_yes"),
                InlineKeyboardButton("Нет", callback_data="more_no"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text("Спасибо за ваш отзыв. Хотите оценить доставку или сервис?", reply_markup=reply_markup)
        return MORE_REVIEWS
    elif data == 'edit':
        # Show edit menu based on category
        category = context.user_data.get('current_category', '')
        keyboard = []
        if category == 'чай':
            keyboard = [
                [InlineKeyboardButton("Название чая", callback_data="edit_product")],
                [InlineKeyboardButton("Оценка", callback_data="edit_rating")],
                [InlineKeyboardButton("Органолептика", callback_data="edit_likes")],
                [InlineKeyboardButton("Отзыв", callback_data="edit_review")],
            ]
        else:  # Service/Delivery (no product)
            keyboard = [
                [InlineKeyboardButton("Оценка", callback_data="edit_rating")],
                [InlineKeyboardButton("Лучшие моменты", callback_data="edit_likes")],
                [InlineKeyboardButton("Отзыв", callback_data="edit_review")],
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Что вы хотели изменить?", reply_markup=reply_markup)
        return EDIT_MENU
async def edit_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles edit menu selection."""
    query = update.callback_query
    await query.answer()
    data = query.data
    category = context.user_data.get('current_category', '')

    if data == 'edit_product':
        # Only for tea
        await query.edit_message_text("Введите название продукта заново.")
        return EDIT_PRODUCT
    elif data == 'edit_rating':
        # Show rating buttons again
        keyboard = [
            [
                InlineKeyboardButton("1 ", callback_data="rate_1"),
                InlineKeyboardButton("2 ", callback_data="rate_2"),
                InlineKeyboardButton("3 ", callback_data="rate_3"),
                InlineKeyboardButton("4 ", callback_data="rate_4"),
                InlineKeyboardButton("5 ", callback_data="rate_5"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите рейтинг заново.", reply_markup=reply_markup)
        return EDIT_RATING
    elif data == 'edit_likes':
    # Set editing flag
        context.user_data['editing'] = True
        # Restore current_likes from pending_data
        pending_data = context.user_data.get('pending_data', {})
        context.user_data['current_likes'] = set(pending_data.get('likes', []))  # Restore likes
        # Call category likes with full update
        if category == 'чай':
            await tea_likes(update, context)  # Pass update
            return TEA_LIKES
        elif category == 'сервис':
            await service_likes_handler(update, context)  # Pass update
            return SERVICE_LIKES
        elif category == 'доставка':
            await delivery_likes_handler(update, context)  # Pass update
            return DELIVERY_LIKES
    elif data == 'edit_review':
        await query.edit_message_text("Напишите отзыв заново.")
        return EDIT_REVIEW
    elif data == 'edit_review':
        await query.edit_message_text("Напишите отзыв заново (для доставки).")  # MARK: Clear prompt for delivery
        return EDIT_REVIEW

    return PREVIEW

async def edit_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles editing product name (Tea only)."""
    context.user_data['current_product'] = update.message.text  # Update pending
    await update.message.reply_text("Название продукта обновлено. Возвращаемся к предпросмотру.")

    # Rebuild preview
    category = context.user_data.get('current_category', '')
    pending_data = context.user_data.get('pending_data', {})
    pending_data['product'] = context.user_data['current_product']
    context.user_data['pending_data'] = pending_data

    if category == 'чай':
        formatted = format_tea_review(pending_data)
    # ... (similar for other categories if needed)

    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(f"Вот ваш комментарий, проверьте перед отправкой:\n\n{formatted}", reply_markup=reply_markup, parse_mode="HTML")
    return PREVIEW

async def edit_review_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles editing review text (common)."""
    new_review = update.message.text
    pending_data = context.user_data.get('pending_data', {})
    pending_data['review_text'] = new_review
    context.user_data['pending_data'] = pending_data  # Save back
    await update.message.reply_text("Отзыв обновлен. Возвращаемся к предпросмотру.")

    # Rebuild preview
    category = context.user_data.get('current_category', '')
    if category == 'чай':
        formatted = format_tea_review(pending_data)
    elif category == 'сервис':
        formatted = format_service_review(pending_data)
    elif category == 'доставка':
        formatted = format_delivery_review(pending_data)
    else:
        formatted = "Preview error."

    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(f"Вот ваш комментарий, проверьте перед отправкой:\n\n{formatted}", reply_markup=reply_markup, parse_mode="HTML")
    logger.info(f"Edit review completed for {category}, new text: {new_review[:50]}...")  # MARK: Add logging to confirm handler fires
    return PREVIEW

async def edit_likes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles editing likes (reuses category likes)."""
    query = update.callback_query
    await query.answer()
    category = context.user_data.get('current_category', '')
    if category == 'чай':
        await tea_likes(query, context)
        return TEA_LIKES
    elif category == 'сервис':
        await service_likes_handler(update, context)
        return SERVICE_LIKES
    elif category == 'доставка':
        await delivery_likes_handler(update, context)
        return DELIVERY_LIKES
    return PREVIEW

async def edit_rating_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles re-rating after edit."""
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split('_')[1])
    context.user_data['current_rating'] = rating  # Update pending data

    # Back to preview
    await query.edit_message_text(f"Рейтинг обновлен: {rating} ({'⭐' * rating})")

    # Rebuild and show preview (reuse logic from review_text)
    category = context.user_data.get('current_category', '')
    pending_data = context.user_data.get('pending_data', {})  # Assume stored
    pending_data['rating'] = rating
    context.user_data['pending_data'] = pending_data

    if category == 'чай':
        formatted = format_tea_review(pending_data)
    elif category == 'сервис':
        formatted = format_service_review(pending_data)
    elif category == 'доставка':
        formatted = format_delivery_review(pending_data)
    else:
        formatted = "Preview error."

    keyboard = [
        [
            InlineKeyboardButton("Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("Изменить", callback_data="edit"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(f"Вот ваш комментарий, проверьте перед отправкой:\n\n{formatted}", reply_markup=reply_markup, parce_mode="HTML")
    return PREVIEW

async def more_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles whether to add more reviews."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'more_yes':
        await query.edit_message_text("Хорошо! Вы можете оставить еще один отзыв.")
        # Back to category selection
        keyboard = [
            [
                InlineKeyboardButton("ЧАЙ", callback_data="чай"),
                InlineKeyboardButton("СЕРВИС", callback_data="сервис"),
                InlineKeyboardButton("ДОСТАВКА", callback_data="доставка"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("На что пишем отзыв?", reply_markup=reply_markup)
        return CATEGORY
    elif data == 'more_no':
        try:
            await query.edit_message_text("Спасибо! Отправляем все отзывы в канал.")
            # Post all reviews
            await post_reviews(update, context)

            # Thank you message
            thank_msg = "Спасибо за искренний отзыв! Все отзывы публикуются в нашем канале @chayniy_ohotnik"
            await query.message.reply_text(thank_msg)

            # Separate promo message from JSON
            promo_text = ""
            try:
                with open('promo.json', 'r', encoding='utf-8') as f:
                    promo = json.load(f)
                    promo_text = f"{promo.get('text', '')} Промокод: {promo.get('code', '')}"
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Promo JSON error: {e}")

            if promo_text:
                await query.message.reply_text(promo_text)
        except Exception as e:
            logger.error(f"Ошибка в отправке отзыва {e}")
            await query.message.reply_text("Извините, произошла ошибка при публикации отзывов. Пожалуйста, попробуйте позже.")
        finally:
            # Clear data
            context.user_data.clear()
        return ConversationHandler.END

async def post_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Posts all collected reviews to the channel using category-specific formatting."""
    reviews = context.user_data.get('reviews', [])
    for review in reviews:
        category = review['category']
        photo = review.get('photo')

        # Get formatted message based on category
        if category == 'чай':
            message = format_tea_review(review)
        elif category == 'сервис':
            message = format_service_review(review)
        elif category == 'доставка':
            message = format_delivery_review(review)
        else:
            # Fallback
            message = "Неизвестная отзыва."

        try:
            if photo:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=message, parse_mode="HTML")
            else:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Error posting review for {category}: {e}")
            # User-friendly error
            if hasattr(update, 'callback_query'):
                await update.callback_query.message.reply_text("Извините, произошла ошибка при публикации одного из отзывов.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the review process."""
    await update.message.reply_text("Отзыв отменен.")
    context.user_data.clear()
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).connect_timeout(30).pool_timeout(30).build()

    # Handler for /start
    application.add_handler(CommandHandler("start", start_command))

    # Conversation handler for review collection
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("Оставить отзыв"), start_review)],
        states={
            CATEGORY: [CallbackQueryHandler(category)],
            # Tea states
            TEA_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tea_product)],
            TEA_PHOTO: [
                MessageHandler(filters.PHOTO, tea_photo),
                MessageHandler(filters.ALL & ~filters.PHOTO & ~filters.COMMAND, tea_photo_reprompt),  # Reprompt for non-photo
            ],
            TEA_RATING: [CallbackQueryHandler(tea_rating, pattern="^rate_")],
            TEA_LIKES: [CallbackQueryHandler(tea_likes, pattern="^likes_")],
            TEA_REVIEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tea_review_text)],
            # Service states (new flow)
            SERVICE_LIKES: [CallbackQueryHandler(service_likes_handler, pattern="^likes_")],
            SERVICE_RATING: [CallbackQueryHandler(service_rating_handler, pattern="^rate_")],
            SERVICE_REVIEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, service_review_text)],
            # Delivery states (new flow)
            DELIVERY_LIKES: [CallbackQueryHandler(delivery_likes_handler, pattern="^likes_")],
            DELIVERY_RATING: [CallbackQueryHandler(delivery_rating_handler, pattern="^rate_")],
            DELIVERY_REVIEW_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delivery_review_text)],
            # Common more reviews
            PREVIEW: [CallbackQueryHandler(preview_handler, pattern="^(confirm|edit)$")],
            EDIT_MENU: [CallbackQueryHandler(edit_menu_handler, pattern="^edit_")],
            EDIT_RATING: [CallbackQueryHandler(edit_rating_handler, pattern="^rate_")],
            EDIT_LIKES: [CallbackQueryHandler(edit_likes_handler, pattern="^likes_")],  # Reuse likes handlers
            EDIT_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_handler)],
            EDIT_REVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_review_handler)],
            # Add EDIT_LIKES, EDIT_PRODUCT, EDIT_REVIEW if needed, but reuse existing likes/product/review states for simplicity
            MORE_REVIEWS: [CallbackQueryHandler(more_reviews, pattern="^more_")],        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    # Start the bot
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
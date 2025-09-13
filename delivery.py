from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler


async def delivery_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the product name and asks for photo (Delivery category)."""
    context.user_data['current_product'] = update.message.text

    keyboard = [[InlineKeyboardButton("Skip", callback_data="skip_photo")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Please add a photo (or skip):", reply_markup=reply_markup)
    return DELIVERY_PHOTO

async def delivery_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the photo and shows rating buttons (Delivery category)."""
    photo_file = update.message.photo[-1].file_id
    context.user_data['current_photo'] = photo_file

    await update.message.reply_text("Photo received!")

    # Show rating buttons
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="rate_1"),
            InlineKeyboardButton("2", callback_data="rate_2"),
            InlineKeyboardButton("3", callback_data="rate_3"),
            InlineKeyboardButton("4", callback_data="rate_4"),
            InlineKeyboardButton("5", callback_data="rate_5"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Select your rating:", reply_markup=reply_markup)
    return DELIVERY_RATING

async def delivery_skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skips the photo step and shows rating buttons (Delivery category)."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Photo skipped.")

    # Show rating buttons
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="rate_1"),
            InlineKeyboardButton("2", callback_data="rate_2"),
            InlineKeyboardButton("3", callback_data="rate_3"),
            InlineKeyboardButton("4", callback_data="rate_4"),
            InlineKeyboardButton("5", callback_data="rate_5"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text("Select your rating:", reply_markup=reply_markup)
    return DELIVERY_RATING

async def delivery_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles rating selection (Delivery category)."""
    query = update.callback_query
    await query.answer()
    rating = int(query.data.split('_')[1])
    context.user_data['current_rating'] = rating

    await query.edit_message_text(f"Rating selected: {rating} ({'⭐' * rating})")

    await query.message.reply_text("Please share your thoughts about the product.")
    return DELIVERY_REVIEW_TEXT

async def delivery_review_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the review text and appends the review to the list (Delivery category)."""
    context.user_data['current_review_text'] = update.message.text

    # Append current review to reviews list
    review = {
        'category': context.user_data['current_category'],
        'product': context.user_data.get('current_product', ''),
        'photo': context.user_data.get('current_photo', None),
        'rating': context.user_data['current_rating'],
        'likes': [],  # No likes for delivery
        'review_text': context.user_data['current_review_text'],
    }
    context.user_data['reviews'].append(review)

    # Clear current data
    context.user_data.pop('current_product', None)
    context.user_data.pop('current_photo', None)
    context.user_data.pop('current_rating', None)
    context.user_data.pop('current_review_text', None)

    # Ask if want to add more
    keyboard = [
        [
            InlineKeyboardButton("Да", callback_data="more_yes"),
            InlineKeyboardButton("Нет", callback_data="more_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Спасибо за ваш отзыв. Хотите оценить доставку или сервис?", reply_markup=reply_markup)
    return 1

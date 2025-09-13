def escape_html(text: str) -> str:
    """Escapes special characters for HTML parsing."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def format_tea_review(review_data: dict) -> str:
    """Formats review for Tea category (includes Product)."""
    category = review_data['category']
    product = escape_html(review_data.get('product', ''))
    rating = review_data['rating']
    likes_list = review_data['likes']
    review_text = escape_html(review_data['review_text'])
    category_tag = f"отзыв_{category}"

    # Handle likes for Tea
    if set(likes_list) == {'taste', 'aroma', 'feeling'}:
        likes = "All (Taste, Aroma, Feeling)"
    else:
        likes = ', '.join([l.capitalize() for l in likes_list]) if likes_list else 'None'

    message = (
        f"📝 <b>New Review</b>\n\n"
        f"<b>Category</b>: {category.capitalize()}\n"
        f"<b>Product</b>: {product}\n"  # Only here for Tea
        f"<b>Rating</b>: {'⭐' * rating}\n"
        f"<b>Likes</b>: {likes}\n"
        f"<b>Review</b>: {review_text}\n\n"
        f"#отзыв #{category_tag}"
    )
    return message

def format_service_review(review_data: dict) -> str:
    """Formats review for Service category (no Product line)."""
    category = review_data['category']
    rating = review_data['rating']
    likes_list = review_data['likes']
    review_text = escape_html(review_data['review_text'])
    category_tag = f"отзыв_{category}"

    # Handle likes for Service (Russian)
    if set(likes_list) == {'quality', 'speed', 'professionalism'}:
        likes = "All (Качество сервиса, Скорость обслуживания, Профессионализм)"
    else:
        likes_map = {'quality': 'Качество сервиса', 'speed': 'Скорость обслуживания', 'professionalism': 'Профессионализм'}
        likes = ', '.join([likes_map.get(l, l.capitalize()) for l in likes_list]) if likes_list else 'None'

    message = (
        f"📝 <b>New Review</b>\n\n"
        f"<b>Category</b>: {category.capitalize()}\n"
        f"<b>Rating</b>: {'⭐' * rating}\n"
        f"<b>Likes</b>: {likes}\n"
        f"<b>Review</b>: {review_text}\n\n"
        f"#отзыв #{category_tag}"
    )
    # No <b>Product</b> line here!
    return message

def format_delivery_review(review_data: dict) -> str:
    """Formats review for Delivery category (no Product; customizable)."""
    category = review_data['category']
    rating = review_data['rating']
    # No likes for delivery (add if needed later)
    review_text = escape_html(review_data['review_text'])
    category_tag = f"отзыв_{category}"

    message = (
        f"📝 <b>New Review</b>\n\n"
        f"<b>Category</b>: {category.capitalize()}\n"
        f"<b>Rating</b>: {'⭐' * rating}\n"
        f"<b>Review</b>: {review_text}\n\n"
        f"#отзыв #{category_tag}"
    )
    # No <b>Product</b> line here!
    return message
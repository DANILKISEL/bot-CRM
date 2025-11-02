import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from models import db, TelegramUser, Conversation, Message
from flask import current_app
import os
from datetime import datetime

# Initialize bot
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8344888636:AAEF1zFnel32w9-y-DRRsv5Nu4dPNA-10Ss')
bot = telebot.TeleBot(BOT_TOKEN)


def create_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('🆘 Get Help'))
    keyboard.add(KeyboardButton('📞 Contact Agent'))
    keyboard.add(KeyboardButton('ℹ️ Status'))
    return keyboard


@bot.message_handler(commands=['start'])
def start_command(message):
    # Register or get Telegram user
    tg_user = TelegramUser.query.filter_by(telegram_id=message.from_user.id).first()
    if not tg_user:
        tg_user = TelegramUser(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        db.session.add(tg_user)
        db.session.commit()

    welcome_text = """
🤖 Welcome to CRM Support Bot!

I'm here to help you with:
• Customer support
• Product information
• Technical assistance

Use the buttons below to navigate, or just type your question!
    """

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=create_keyboard()
    )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    tg_user = TelegramUser.query.filter_by(telegram_id=message.from_user.id).first()
    if not tg_user:
        return

    # Get or create conversation
    conversation = Conversation.query.filter_by(
        telegram_user_id=tg_user.id,
        status='open'
    ).first()

    if not conversation:
        conversation = Conversation(telegram_user_id=tg_user.id)
        db.session.add(conversation)
        db.session.commit()

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        sender_type='user',
        sender_id=tg_user.id,
        content=message.text
    )
    db.session.add(user_message)
    db.session.commit()

    # Process AI response
    ai_response = generate_ai_response(message.text, conversation.id)

    if ai_response:
        # Save AI response
        ai_message = Message(
            conversation_id=conversation.id,
            sender_type='ai',
            sender_id=None,
            content=ai_response,
            is_ai_response=True
        )
        db.session.add(ai_message)
        db.session.commit()

        # Send AI response to user
        bot.send_message(message.chat.id, ai_response)

    # Notify agents about new message
    notify_agents(conversation.id, message.text, tg_user)


def generate_ai_response(user_message, conversation_id):
    """Generate AI response based on user message"""
    # Simple rule-based responses - replace with your AI model
    user_message_lower = user_message.lower()

    if 'hello' in user_message_lower or 'hi' in user_message_lower:
        return "Hello! I'm an AI assistant. How can I help you today?"

    elif 'help' in user_message_lower:
        return "I'm here to assist you! Please describe your issue and I'll connect you with a human agent if needed."

    elif 'price' in user_message_lower or 'cost' in user_message_lower:
        return "Our pricing varies based on your needs. I can connect you with a sales agent for detailed pricing information."

    elif 'thank' in user_message_lower:
        return "You're welcome! Is there anything else I can help you with?"

    else:
        return "Thank you for your message. I've forwarded it to our support team. An agent will respond shortly. In the meantime, is there any other information I can provide?"


def notify_agents(conversation_id, message, tg_user):
    """Notify agents about new user message"""
    # This would typically integrate with your notification system
    # For now, we'll just log it
    print(f"New message from user {tg_user.first_name}: {message}")
    print(f"Conversation ID: {conversation_id}")


def broadcast_to_agents(telegram_user_id, message, is_agent=False):
    """Send message from agent to Telegram user"""
    tg_user = TelegramUser.query.get(telegram_user_id)
    if tg_user:
        try:
            if is_agent:
                prefix = "👨‍💼 Agent: "
            else:
                prefix = "🤖 AI: "

            bot.send_message(tg_user.telegram_id, f"{prefix}{message}")
        except Exception as e:
            print(f"Error sending message to user {tg_user.telegram_id}: {e}")


def start_bot():
    """Start the Telegram bot"""
    print("Starting Telegram bot...")
    bot.polling(none_stop=True)


if __name__ == '__main__':
    start_bot()
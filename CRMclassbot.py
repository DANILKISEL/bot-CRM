import telebot
import logging
import re
from datetime import datetime
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger("CRM CLASS BOT")

class CRMTelegramBot:
    def __init__(self, app, db, telegram_bot_token, TelegramUser, Conversation, Message):
        self.app = app
        self.db = db
        self.bot = telebot.TeleBot(telegram_bot_token)
        self.TelegramUser = TelegramUser
        self.Conversation = Conversation
        self.Message = Message

        # User session storage for contract process
        self.user_sessions = {}

        self.setup_handlers()

    def setup_handlers(self):
        """Setup all message handlers for the single bot"""
        # Command handlers
        self.bot.message_handler(commands=['start', 'help'])(self.start_handler)
        self.bot.message_handler(commands=['contract'])(self.contract_handler)
        self.bot.message_handler(commands=['pricing'])(self.pricing_handler)

        # Message handlers
        self.bot.message_handler(func=lambda message: self.check_contract_session(message))(
            self.contract_message_handler)
        self.bot.message_handler(func=lambda message: True)(self.general_message_handler)

        # Callback handlers
        self.bot.callback_query_handler(func=lambda call: call.data.startswith('contract_'))(
            self.contract_callback_handler)

    def check_contract_session(self, message):
        """Check if user is in contract session"""
        return message.from_user.id in self.user_sessions

    def with_app_context(self, func):
        """Decorator to ensure function runs within app context"""

        def wrapper(*args, **kwargs):
            with self.app.app_context():
                return func(*args, **kwargs)

        return wrapper

    def get_or_create_telegram_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Get existing Telegram user or create new one"""
        try:
            telegram_user = self.TelegramUser.query.filter_by(telegram_id=user_id).first()
            if telegram_user:
                # Update user info if changed
                if (telegram_user.username != username or
                        telegram_user.first_name != first_name or
                        telegram_user.last_name != last_name):
                    telegram_user.username = username
                    telegram_user.first_name = first_name
                    telegram_user.last_name = last_name
                    telegram_user.updated_at = datetime.utcnow()
                    self.db.session.commit()
                return telegram_user
            else:
                # Create new user
                telegram_user = self.TelegramUser(
                    telegram_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                self.db.session.add(telegram_user)
                self.db.session.commit()
                return telegram_user
        except Exception as e:
            logger.error(f"Error getting/creating Telegram user: {e}")
            self.db.session.rollback()
            return None

    def get_or_create_conversation(self, telegram_user_id, conversation_type="general"):
        """Get existing conversation or create new one"""
        try:
            if conversation_type == "contract":
                # For contract conversations, create a new one
                telegram_user = self.TelegramUser.query.get(telegram_user_id)
                if not telegram_user:
                    logger.error(f"Telegram user {telegram_user_id} not found")
                    return None

                conversation = self.Conversation(
                    telegram_user_id=telegram_user_id,
                    title=f"Договор: {telegram_user.first_name}",
                    status='contract_process'
                )
                self.db.session.add(conversation)
                self.db.session.commit()
                return conversation
            else:
                # For general conversations, find existing open one
                conversation = self.Conversation.query.filter_by(
                    telegram_user_id=telegram_user_id
                ).filter(
                    self.Conversation.status.in_(['open', 'assigned', 'contract_process'])
                ).order_by(self.Conversation.updated_at.desc()).first()

                if not conversation:
                    telegram_user = self.TelegramUser.query.get(telegram_user_id)
                    if not telegram_user:
                        logger.error(f"Telegram user {telegram_user_id} not found")
                        return None

                    conversation = self.Conversation(
                        telegram_user_id=telegram_user_id,
                        title=f"Чат с {telegram_user.first_name}",
                        status='open'
                    )
                    self.db.session.add(conversation)
                    self.db.session.commit()

                return conversation

        except Exception as e:
            logger.error(f"Error in get_or_create_conversation: {str(e)}")
            self.db.session.rollback()
            return None

    def save_message(self, conversation, content, sender_type="user", sender_id=None, is_ai_response=False):
        """Save message to database"""
        try:
            message = self.Message(
                conversation_id=conversation.id,
                sender_type=sender_type,
                sender_id=sender_id,
                content=content,
                is_ai_response=is_ai_response,
                timestamp=datetime.utcnow(),
                read_by_agent=False
            )
            self.db.session.add(message)

            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow()

            self.db.session.commit()
            return message
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            self.db.session.rollback()
            return None

    def start_handler(self, message):
        """Handle /start and /help commands"""
        with self.app.app_context():
            user = message.from_user

            # Get or create Telegram user
            telegram_user = self.get_or_create_telegram_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            if not telegram_user:
                self.bot.reply_to(message, "❌ Ошибка создания пользователя. Пожалуйста, попробуйте снова.")
                return

            welcome_text = """
🤖 Добро пожаловать в CRM Support Bot!

Доступные команды:
/start - Показать это приветственное сообщение
/help - Получить информацию о помощи
/contract - Начать процесс заключения договора
/pricing - Показать прайс-лист

Мы здесь, чтобы помочь вам! Просто отправьте нам сообщение, и мы ответим в ближайшее время.


Сделано с помощью [bot-CRM](https://github.com/DANILKISEl/bot-CRM)
            """

            # Create general conversation if doesn't exist
            conversation = self.get_or_create_conversation(telegram_user.id, "general")
            if conversation:
                self.save_message(conversation, welcome_text, sender_type="bot", is_ai_response=True)

            self.bot.reply_to(message, welcome_text)

    def contract_handler(self, message):
        """Handle /contract command - start contract agreement process"""
        with self.app.app_context():
            user = message.from_user

            # Get or create Telegram user
            telegram_user = self.get_or_create_telegram_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            if not telegram_user:
                self.bot.reply_to(message, "❌ Ошибка создания пользователя. Пожалуйста, попробуйте снова.")
                return

            # Create contract conversation
            conversation = self.get_or_create_conversation(telegram_user.id, "contract")
            if not conversation:
                self.bot.reply_to(message, "❌ Ошибка создания процесса договора. Пожалуйста, попробуйте снова.")
                return

            # Initialize user session for contract process
            self.user_sessions[user.id] = {
                'conversation_id': conversation.id,
                'step': 'waiting_full_name',
                'full_name': None,
                'passport': None
            }

            # Save start message
            self.save_message(conversation, "Пользователь начал процесс договора")

            welcome_text = """
🤝 **Добро пожаловать!**

Вы начинаете процесс заключения соглашения с нашей командой Zefir.

Пожалуйста, введите ваше ФИО полностью:
            """

            # Save bot message
            self.save_message(conversation, welcome_text, sender_type="bot", is_ai_response=True)

            self.bot.reply_to(message, welcome_text, parse_mode='Markdown')

    def pricing_handler(self, message):
        """Handle /pricing command - show pricing cards"""
        with self.app.app_context():
            user = message.from_user

            # Get or create Telegram user
            telegram_user = self.get_or_create_telegram_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            if not telegram_user:
                self.bot.reply_to(message, "❌ Ошибка создания пользователя. Пожалуйста, попробуйте снова.")
                return

            # Get or create conversation
            conversation = self.get_or_create_conversation(telegram_user.id, "general")
            if conversation:
                self.save_message(conversation, "Пользователь запросил информацию о ценах", sender_type="user")

            pricing_text = """
💼 **Прайс-лист услуг Zefir-IT**

**Мелкие задачи и правки:**
• Исправление ошибок на сайте (до 1 ч) - 500 – 1 000 ₽
• Настройка форм обратной связи, почты (1 ч) - 800 – 1 500 ₽
• Подключение счётчиков (1 ч) - 500 – 1 000 ₽
• Настройка адаптивности (2–3 ч) - 1 500 – 3 000 ₽
• Установка SSL/домена/хостинга (0,5–1 день) - 1 000 – 2 000 ₽

**Создание и доработка сайтов:**
• Доработка сайта (1–3 ч) - 1 000 – 3 000 ₽
• Вёрстка лендинга (1–2 дня) - 3 000 – 7 000 ₽
• Сайт «под ключ» (2–4 дня) - 5 000 – 15 000 ₽
• Интернет-магазин (5–7 дней) - 15 000 – 30 000 ₽
• Многостраничный сайт (1–2 недели) - 25 000 – 50 000 ₽
• SEO-оптимизация (1–3 дня) - 2 000 – 5 000 ₽
• Подключение CMS (1–2 дня) - 3 000 – 8 000 ₽
• Миграция сайта (1 день) - 2 000 – 4 000 ₽

**Telegram-боты:**
• Бот с базовой логикой (1–2 дня) - 5 000 – 15 000 ₽
• Бот для заявок/заказов (2–3 дня) - 10 000 – 20 000 ₽
• Интеграция с Google Sheets, CRM (3–5 дней) - 15 000 – 30 000 ₽
• Бот с авторизацией и оплатой (4–6 дней) - 20 000 – 40 000 ₽
• Кастомная админ-панель (1 неделя) - 25 000 – 45 000 ₽

**Интеграции и автоматизация:**
• Интеграция сайта с CRM (3–5 дней) - 15 000 – 35 000 ₽
• Интеграция с платёжными системами (3–5 дней) - 20 000 – 40 000 ₽
• Автоматизация бизнес-процессов (5–7 дней) - 20 000 – 50 000 ₽
• Настройка Webhook, REST API (2–4 дня) - 10 000 – 25 000 ₽

**Дополнительные услуги:**
• Настройка Excel/Google Sheets (1–2 дня) - 2 000 – 6 000 ₽
• Разработка мини-приложений (2–5 дней) - 8 000 – 25 000 ₽
• Подключение ChatGPT/нейросетей (3–5 дней) - 15 000 – 40 000 ₽
• Аналитика и визуализация данных (2–4 дня) - 10 000 – 25 000 ₽
• Поддержка проекта (ежемесячно) - от 3 000 ₽ / мес

💡 *Цены являются ориентировочными. Точная стоимость рассчитывается индивидуально под каждый проект.*

Для обсуждения вашего проекта или получения консультации, просто напишите нам сообщение!
            """

            # Save pricing message to conversation
            if conversation:
                self.save_message(conversation, pricing_text, sender_type="bot", is_ai_response=True)

            # Send without keyboard (remove buttons)
            self.bot.reply_to(
                message,
                pricing_text,
                parse_mode='Markdown'
            )

    def contract_message_handler(self, message):
        """Handle messages during contract process"""
        with self.app.app_context():
            user = message.from_user
            user_message = message.text

            if user.id not in self.user_sessions:
                self.bot.reply_to(message, "Пожалуйста, начните процесс договора с /contract")
                return

            session = self.user_sessions[user.id]
            conversation_id = session.get('conversation_id')

            conversation = self.Conversation.query.get(conversation_id)
            if not conversation:
                self.bot.reply_to(message, "❌ Ошибка сессии. Пожалуйста, начните заново с /contract")
                return

            # Save user message
            self.save_message(conversation, user_message, sender_type="user")

            current_step = session.get('step')

            if current_step == 'waiting_full_name':
                self.process_full_name(message, user_message, session, conversation)
            elif current_step == 'waiting_passport':
                self.process_passport(message, user_message, session, conversation)

    def general_message_handler(self, message):
        """Handle general messages (not in contract process)"""
        with self.app.app_context():
            user = message.from_user

            # Get or create Telegram user
            telegram_user = self.get_or_create_telegram_user(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )

            if not telegram_user:
                self.bot.reply_to(message, "❌ Ошибка обработки сообщения. Пожалуйста, попробуйте /start")
                return

            # Get or create general conversation
            conversation = self.get_or_create_conversation(telegram_user.id, "general")
            if not conversation:
                self.bot.reply_to(message, "❌ Ошибка создания диалога. Пожалуйста, попробуйте снова.")
                return

            # Save user message
            self.save_message(conversation, message.text, sender_type="user")

            # Generate AI response
            ai_response = self.generate_ai_response(message.text, conversation.id)

            if ai_response:
                # Save AI response
                self.save_message(conversation, ai_response, sender_type="ai", is_ai_response=True)

                # Send response to user
                self.bot.reply_to(message, ai_response)

            # Notify agents
            self.notify_agents(conversation.id, message.text, telegram_user)

    def generate_ai_response(self, user_message, conversation_id):
        """Generate AI response for general messages"""
        try:
            user_message_lower = user_message.lower()

            if any(word in user_message_lower for word in ['привет', 'здравствуй', 'добрый', 'hello', 'hi', 'hey']):
                return "Привет! Я AI-ассистент. Чем могу помочь вам сегодня?"

            elif any(word in user_message_lower for word in ['помощь', 'help', 'помоги']):
                return "Я здесь, чтобы помочь вам! Опишите вашу проблему, и я свяжу вас с человеческим агентом, если это потребуется."

            elif any(word in user_message_lower for word in ['цена', 'стоимость', 'сколько стоит', 'прайс']):
                return "Наши цены варьируются в зависимости от ваших потребностей. Полный прайс-лист доступен по команде /pricing"

            elif any(word in user_message_lower for word in ['спасибо', 'благодарю']):
                return "Пожалуйста! Могу ли я помочь вам с чем-то ещё?"

            elif any(word in user_message_lower for word in ['пока', 'до свидания']):
                return "До свидания! Не стесняйтесь обращаться, если вам потребуется дополнительная помощь."

            else:
                return "Спасибо за ваше сообщение. Я переправил его нашей службе поддержки. Агент ответит вам в ближайшее время. Могу ли я предоставить какую-либо другую информацию?"

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "Я понимаю, что вы ищете помощь. Наша команда свяжется с вами в ближайшее время."

    def notify_agents(self, conversation_id, message, tg_user):
        """Notify agents about new message"""
        try:
            logger.info(f"New message from {tg_user.first_name}: {message}")
            print(f"🔔 Диалог #{conversation_id}: {tg_user.first_name} - {message}")
        except Exception as e:
            logger.error(f"Error notifying agents: {e}")

    def process_full_name(self, message, full_name: str, session: dict, conversation):
        """Process and validate full name for contract"""
        with self.app.app_context():
            if len(full_name.split()) < 2:
                error_msg = "❌ Пожалуйста, введите ФИО полностью (как минимум имя и фамилию):"
                self.save_message(conversation, error_msg, sender_type="bot", is_ai_response=True)
                self.bot.reply_to(message, error_msg)
                return

            session['full_name'] = full_name
            session['step'] = 'waiting_passport'

            conversation.title = f"Договор: {full_name}"
            self.db.session.commit()

            next_step_text = """
Теперь введите серию и номер вашего паспорта (через пробел):
Например: `4510 123456`
            """

            self.save_message(conversation, next_step_text, sender_type="bot", is_ai_response=True)
            self.bot.reply_to(message, next_step_text, parse_mode='Markdown')

    def process_passport(self, message, passport: str, session: dict, conversation):
        """Process and validate passport data for contract"""
        with self.app.app_context():
            passport_pattern = r'^\d{4}\s\d{6}$'

            if not re.match(passport_pattern, passport):
                error_msg = "❌ Неверный формат паспорта. Пожалуйста, введите серию и номер через пробел (например: `4510 123456`):"
                self.save_message(conversation, error_msg, sender_type="bot", is_ai_response=True)
                self.bot.reply_to(message, error_msg, parse_mode='Markdown')
                return

            session['passport'] = passport
            session['step'] = 'waiting_agreement'

            full_name = session['full_name']

            confirmation_text = f"""
Спасибо, {full_name}!

Перед началом работы ознакомьтесь с нашей публичной офертой:

**Договор:**  
[https://zefir-it.ru/contract.html](https://zefir-it.ru/contract.html)  

**Соглашение об обработке данных:**  
[https://zefir-it.ru/privacy.html](https://zefir-it.ru/privacy.html)  

Нажимая кнопку ниже, вы подтверждаете согласие с условиями.

Сделано с помощью [bot-CRM](https://github.com/DANILKISEl/bot-CRM)
            """

            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("✅ Согласен", callback_data="contract_agree_terms"))

            self.save_message(conversation, confirmation_text, sender_type="bot", is_ai_response=True)
            self.bot.reply_to(
                message,
                confirmation_text,
                reply_markup=keyboard,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )

    def contract_callback_handler(self, call):
        """Handle contract agreement callback"""
        with self.app.app_context():
            user = call.from_user
            data = call.data

            if user.id not in self.user_sessions:
                self.bot.answer_callback_query(call.id, "Сессия истекла. Начните с /contract")
                return

            session = self.user_sessions[user.id]
            conversation_id = session.get('conversation_id')

            conversation = self.Conversation.query.get(conversation_id)
            if not conversation:
                self.bot.answer_callback_query(call.id, "Диалог не найден. Начните с /contract")
                return

            if data == "contract_agree_terms":
                self.process_contract_agreement(call, session, conversation, user)

            self.bot.answer_callback_query(call.id)

    def process_contract_agreement(self, call, session: dict, conversation, user):
        """Process contract agreement completion"""
        with self.app.app_context():
            full_name = session.get('full_name')
            passport = session.get('passport')

            if not full_name or not passport:
                self.bot.edit_message_text(
                    "❌ Данные не найдены. Пожалуйста, начните заново с /contract",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id
                )
                return

            # Update conversation status to completed
            conversation.status = 'completed'
            conversation.closed_at = datetime.utcnow()
            self.db.session.commit()

            success_text = f"""
✅ **Спасибо! Вы приняли условия оферты.**

✅ **Договор успешно заключён.**

С уважением, команда Zeffr 🚀

**Ваши данные:**
• ФИО: {full_name}
• Паспорт: {passport}
• Дата заключения: {self.get_current_date()}

Договор вступил в силу. Добро пожаловать в команду!

Сделано с помощью [bot-CRM](https://github.com/DANILKISEl/bot-CRM)
            """

            # Save success message
            self.save_message(conversation, success_text, sender_type="bot", is_ai_response=True)

            # Remove keyboard and show final message
            self.bot.edit_message_text(
                success_text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode='Markdown',
                reply_markup=None
            )

            # Log contract completion
            logger.info(f"Contract completed - User: {full_name}, Passport: {passport}, Telegram ID: {user.id}")

            # Clean up session
            if user.id in self.user_sessions:
                del self.user_sessions[user.id]

    def get_current_date(self):
        """Get current date in Russian format"""
        months = {
            1: "января", 2: "февраля", 3: "марта", 4: "апреля",
            5: "мая", 6: "июня", 7: "июля", 8: "августа",
            9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
        }
        now = datetime.now()
        return f"{now.day} {months[now.month]} {now.year} года"

    def run(self):
        """Run the single bot"""
        logger.info("CRM Telegram Bot запускается...")
        try:
            self.bot.infinity_polling()
        except Exception as e:
            logger.error(f"Ошибка в CRM боте: {e}")
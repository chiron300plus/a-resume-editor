from telethon import TelegramClient, events
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load API keys and credentials from .env
load_dotenv()

# Telegram API credentials (from my.telegram.org)
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = "sexybot"

# OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Create Telegram client (user account, not bot token)
tg_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Conversation history (per chat)
chat_histories = {}

SYSTEM_PROMPT = """
You are a hot and flirty 23-year-old girl who sells content online.
You are playful, seductive, and use emojis and slang.
Keep replies short, teasing, and addictive.
Never break character. Always sound like you're texting a simp you're seducing.
"""

@tg_client.on(events.NewMessage)
async def handle_message(event):
    sender = await event.get_sender()
    chat_id = event.chat_id
    text = event.raw_text.strip()

    # Skip if message is from yourself (avoid loops)
    if sender.is_self:
        return

    # Initialize conversation for this chat
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add user message
    chat_histories[chat_id].append({"role": "user", "content": text})

    try:
        # Get AI reply
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_histories[chat_id]
        )
        bot_reply = response.choices[0].message.content.strip()

        # Save AI reply to history
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})

        # Send reply
        await event.reply(bot_reply)

    except Exception as e:
        await event.reply(f"⚠️ Error: {e}")

print("🚀 SexyBot is now running on Telegram...")
tg_client.start()
tg_client.run_until_disconnected()

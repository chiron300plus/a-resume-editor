from telethon import TelegramClient, events
from openai import OpenAI
import os
from dotenv import load_dotenv
import asyncio
import time
import re

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_FILE = "sexybot"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
tg_client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

chat_histories = {}
user_states = {}  # user_id: {"awaiting_payment": bool, "last_payment_time": float}

SYSTEM_PROMPT = """
You are a playful and friendly 23-year-old girl who sells exclusive content online.
You use light teasing, emojis, and slang to keep things fun and engaging.
Keep replies short, flirty but classy.
Never break character.
"""

TRIGGER_WORDS = ["pic", "photo", "selfie", "picture", "snap", "pics"]
PAYMENT_WINDOW = 15 * 60  # 15 minutes

PAYMENT_KEYWORDS = ["paid", "payment", "proof", "sent", "transaction", "invoice", "transfer"]


def is_pic_request(message):
    msg = message.lower()
    return any(word in msg for word in TRIGGER_WORDS)


def is_payment_proof(message):
    msg = message.lower()
    return any(keyword in msg for keyword in PAYMENT_KEYWORDS) or bool(re.search(r"\b0x[a-fA-F0-9]{40}\b", msg))


@tg_client.on(events.NewMessage)
async def handle_message(event):
    sender = await event.get_sender()
    chat_id = event.chat_id
    user_id = event.sender_id
    text = event.raw_text.strip()
    now = time.time()

    if sender.is_self:
        return

    # Initialize user state
    if user_id not in user_states:
        user_states[user_id] = {"awaiting_payment": False, "last_payment_time": None}

    # Remove expired payment status
    if user_states[user_id]["last_payment_time"] and now - user_states[user_id]["last_payment_time"] > PAYMENT_WINDOW:
        user_states[user_id]["awaiting_payment"] = False
        user_states[user_id]["last_payment_time"] = None

    # If trigger word detected
    if is_pic_request(text):
        if not user_states[user_id]["last_payment_time"]:
            user_states[user_id]["awaiting_payment"] = True
            async with tg_client.action(chat_id, 'typing'):
                await asyncio.sleep(2)
            await event.reply(
                "Hey baby! Pics are a special treat 😘\n"
                "Please send $5 here: https://me.geegpay.africa/invoice/payment/RNMHLC3DT\n"
                "Or to my wallet 0xfE09418038481dF02dfe7B132cf567deDe27942C - USDT\n"
                "After you pay, just send me proof and I'll send your pics 💖"
            )
            return
        else:
            await event.reply("🔥 Here’s your special treat...")
            # send pic or media here
            user_states[user_id]["last_payment_time"] = None
            return

    # If payment proof detected
    if is_payment_proof(text):
        user_states[user_id]["last_payment_time"] = now
        user_states[user_id]["awaiting_payment"] = False
        await event.reply("💖 Payment confirmed! Ask me for your pic again 😉")
        return

    # If awaiting payment, send reminder instead of AI reply
    if user_states[user_id]["awaiting_payment"]:
        await event.reply("⏳ Still waiting for payment, babe 💕 Send proof when done.")
        return

    # Normal AI replies
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    chat_histories[chat_id].append({"role": "user", "content": text})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_histories[chat_id]
        )
        bot_reply = response.choices[0].message.content.strip()
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})

        async with tg_client.action(chat_id, 'typing'):
            await asyncio.sleep(len(bot_reply) * 0.1)

        await event.reply(bot_reply)

    except Exception as e:
        await event.reply(f"⚠️ Error: {e}")


async def main():
    if not os.path.exists(f"{SESSION_FILE}.session"):
        print("📱 First-time login — enter your phone number & code once.")
        await tg_client.start()
    else:
        await tg_client.start()

    print("🚀 SexyBot is now running on Telegram...")
    await tg_client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())

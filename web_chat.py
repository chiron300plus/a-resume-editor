import json
from telethon import TelegramClient, events
from openai import OpenAI
import os
from dotenv import load_dotenv
import asyncio
import time
import re
import random

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_FILE = "sexybot"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
tg_client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

STATE_FILE = "user_states.json"

chat_histories = {}
user_states = {}  # user_id: {"awaiting_payment": bool, "last_payment_time": float, "last_reminder": float}

SYSTEM_PROMPT = """
You are a playful and friendly 23-year-old girl who sells exclusive content online.
You use light teasing, emojis, and slang to keep things fun and engaging.
Keep replies short, flirty but classy.
Never break character.
"""

TRIGGER_WORDS = ["pic", "photo", "selfie", "picture", "snap", "pics"]
PAYMENT_WINDOW = 15 * 60  # 15 minutes to consider payment valid
COOLDOWN = 60 * 60  # 1 hour cooldown between payment reminders

PAYMENT_KEYWORDS = ["paid", "payment", "proof", "sent", "transaction", "invoice", "transfer"]

PAYMENT_LINK = "https://me.geegpay.africa/invoice/payment/RNMHLC3DT"
WALLET_ADDRESS = "0xfE09418038481dF02dfe7B132cf567deDe27942C - USDT"
TIP_KEYWORDS = [
    "tip", "tips", "donate", "donation", "gift", "spoil", "spoil you", 
    "send money", "give money", "buy you", "how much", "payment", "support"
]
TIP_OFFER_RESPONSES = [
    "You're making me smile so much 🥰 If you ever want to spoil me with a tip, I won’t say no 💖",
    "I love chatting with you 😘 If you wanna send a tip, I’ll make it worth your while 😉",
    "If you keep being this sweet, I might just have to send you something extra special. Tips always make my day 💌",
    "A little tip from you could get you a *very* naughty surprise 😏",
    "You’re fun to talk to 💕 Wanna keep me smiling? Here’s your chance to tip me 💖"
]
TIP_ACCEPT_RESPONSES = [
    "Aww, you’re too sweet! 💕 You can send me a tip here: [YOUR_PAYMENT_LINK]",
    "Ooo yes baby 😏 Spoil me here: [YOUR_PAYMENT_LINK] — and I’ll spoil you back 😘",
    "That’s so kind 😍 You can tip me here: [YOUR_PAYMENT_LINK]",
    "You just made my day 😘 Send it here: [YOUR_PAYMENT_LINK]",
    "Mmm… spoil me and I’ll make it worth every penny 😈 [YOUR_PAYMENT_LINK]"
]


def save_states():
    with open(STATE_FILE, "w") as f:
        json.dump(user_states, f)


def load_states():
    global user_states
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            user_states = json.load(f)
            # keys are strings, convert to int
            user_states = {int(k): v for k, v in user_states.items()}
    else:
        user_states = {}


def is_pic_request(message):
    msg = message.lower()
    return any(word in msg for word in TRIGGER_WORDS)


def is_payment_proof(message):
    msg = message.lower()
    return any(keyword in msg for keyword in PAYMENT_KEYWORDS) or bool(re.search(r"\b0x[a-fA-F0-9]{40}\b", msg))

import random

def handle_tip_logic(user_message):
    lower_msg = user_message.lower()

    # If user talks about tipping/gifting
    if any(keyword in lower_msg for keyword in TIP_KEYWORDS):
        return random.choice(TIP_ACCEPT_RESPONSES)

    # Randomly offer tips during normal chat
    if random.random() < 0.05:  # 5% of messages
        return random.choice(TIP_OFFER_RESPONSES)

    return None  # Let AI handle the rest


@tg_client.on(events.NewMessage(outgoing=True))
async def handle_outgoing_message(event):
    # You sent a pic/video to a user - unlock them immediately
    if event.photo or event.video:
        user_id = event.chat_id
        if user_id in user_states and user_states[user_id].get("awaiting_payment", False):
            user_states[user_id]["awaiting_payment"] = False
            user_states[user_id]["last_payment_time"] = time.time()
            save_states()
            await tg_client.send_message(user_id, "💖 Enjoy, babe! You’re unlocked now 😉")


@tg_client.on(events.NewMessage)
async def handle_message(event):
    sender = await event.get_sender()
    chat_id = event.chat_id
    user_id = event.sender_id
    text = event.raw_text.strip()
    now = time.time()

    if sender.is_self:
        return

    if user_id not in user_states:
        user_states[user_id] = {
            "awaiting_payment": False,
            "last_payment_time": None,
            "last_reminder": None,
        }

    state = user_states[user_id]

    # Clear expired payment (after PAYMENT_WINDOW)
    if state["last_payment_time"] and now - state["last_payment_time"] > PAYMENT_WINDOW:
        state["last_payment_time"] = None

    # If user sent payment proof text
    if is_payment_proof(text):
        state["awaiting_payment"] = False
        state["last_payment_time"] = now
        save_states()
        await event.reply("💖 Payment confirmed! Ask me for your pic again 😉")
        return

    # If user is awaiting payment and sends a trigger word, remind them (with cooldown)
    if state["awaiting_payment"] and is_pic_request(text):
        if not state["last_reminder"] or now - state["last_reminder"] > COOLDOWN:
            state["last_reminder"] = now
            save_states()
            async with tg_client.action(chat_id, "typing"):
                await asyncio.sleep(2)
            await event.reply(
                f"⏳ Still waiting for payment, babe 💕 Send proof when done.\n"
                f"Payment link: {PAYMENT_LINK}\n"
                f"Or wallet: {WALLET_ADDRESS}"
            )
        return

    # If they ask for pics (trigger word) and not paid or awaiting payment
    if is_pic_request(text):
        if not state["last_payment_time"]:
            state["awaiting_payment"] = True
            state["last_reminder"] = now
            save_states()
            async with tg_client.action(chat_id, "typing"):
                await asyncio.sleep(2)
            await event.reply(
                f"Hey baby! Pics are a special treat 😘\n"
                f"Please send $5 here: {PAYMENT_LINK}\n"
                f"Or to my wallet {WALLET_ADDRESS}\n"
                f"After you pay, just send me proof and I'll send your pics 💖"
            )
            return
        else:
            # User is paid and within PAYMENT_WINDOW, reset to allow pay per pic again
            state["last_payment_time"] = None
            save_states()
            await event.reply("🔥 Here’s your special treat...")
            # TODO: send actual pic/media here
            return

    # Normal AI replies
    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    chat_histories[chat_id].append({"role": "user", "content": text})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_histories[chat_id],
        )
        bot_reply = response.choices[0].message.content.strip()
        chat_histories[chat_id].append({"role": "assistant", "content": bot_reply})

        async with tg_client.action(chat_id, "typing"):
            await asyncio.sleep(len(bot_reply) * 0.1)

        await event.reply(bot_reply)

    except Exception as e:
        await event.reply(f"⚠️ Error: {e}")


async def main():
    load_states()
    if not os.path.exists(f"{SESSION_FILE}.session"):
        print("📱 First-time login — enter your phone number & code once.")
        await tg_client.start()
    else:
        await tg_client.start()

    print("🚀 SexyBot is now running on Telegram...")
    await tg_client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())


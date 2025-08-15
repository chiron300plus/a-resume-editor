import json, os, asyncio, time, re, random
from telethon import TelegramClient, events
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_FILE = "sexybot"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
tg_client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

STATE_FILE = "user_states.json"
chat_histories = {}
user_states = {}

SYSTEM_PROMPT = """You are a playful and friendly 23-year-old girl who sells exclusive content online.
Use teasing, emojis, and slang to keep things fun and engaging.
Keep replies short, flirty, but classy. Never break character."""

TRIGGER_WORDS = ["pic", "photo", "selfie", "picture", "snap", "pics"]
PAYMENT_WINDOW = 15 * 60
COOLDOWN = 60 * 60
GPT_COOLDOWN = 30  # seconds between GPT calls per user

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
    "If you keep being this sweet, I might just have to send you something extra special 💌",
    "A little tip from you could get you a *very* naughty surprise 😏",
    "You’re fun to talk to 💕 Wanna keep me smiling? Tip me 💖"
]
TIP_ACCEPT_RESPONSES = [
    f"Aww, you’re too sweet! 💕 Tip me here: {PAYMENT_LINK}",
    f"Ooo yes baby 😏 Spoil me here: {PAYMENT_LINK}",
    f"That’s so kind 😍 You can tip me here: {PAYMENT_LINK}",
    f"You just made my day 😘 Send it here: {PAYMENT_LINK}",
    f"Mmm… spoil me and I’ll make it worth every penny 😈 {PAYMENT_LINK}"
]

MAX_HISTORY_MESSAGES = 5
MAX_INPUT_CHARS = 500

def trim_history(chat_id):
    if chat_id in chat_histories:
        system_prompt = chat_histories[chat_id][0]
        chat_histories[chat_id] = [system_prompt] + chat_histories[chat_id][-MAX_HISTORY_MESSAGES:]

def save_states():
    with open(STATE_FILE, "w") as f:
        json.dump(user_states, f)

def load_states():
    global user_states
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            user_states = json.load(f)
            user_states = {int(k): v for k, v in user_states.items()}

def is_pic_request(msg):
    return any(w in msg.lower() for w in TRIGGER_WORDS)

def is_payment_proof(msg):
    m = msg.lower()
    return any(k in m for k in PAYMENT_KEYWORDS) or bool(re.search(r"\b0x[a-fA-F0-9]{40}\b", m))

def handle_tip_logic(msg):
    m = msg.lower()
    if any(k in m for k in TIP_KEYWORDS):
        return random.choice(TIP_ACCEPT_RESPONSES)
    if random.random() < 0.05:
        return random.choice(TIP_OFFER_RESPONSES)
    return None

@tg_client.on(events.NewMessage(outgoing=True))
async def handle_outgoing(event):
    if event.photo or event.video:
        uid = event.chat_id
        if uid in user_states and user_states[uid].get("awaiting_payment"):
            user_states[uid]["awaiting_payment"] = False
            user_states[uid]["last_payment_time"] = time.time()
            save_states()
            await tg_client.send_message(uid, "💖 Enjoy, babe! You’re unlocked now 😉")

@tg_client.on(events.NewMessage)
async def handle_incoming(event):
    sender = await event.get_sender()
    if sender.is_self:
        return

    uid = event.sender_id
    cid = event.chat_id
    text = event.raw_text.strip()[:MAX_INPUT_CHARS]
    now = time.time()

    if uid not in user_states:
        user_states[uid] = {"awaiting_payment": False, "last_payment_time": None, "last_reminder": None, "last_gpt": 0}

    state = user_states[uid]

    if state["last_payment_time"] and now - state["last_payment_time"] > PAYMENT_WINDOW:
        state["last_payment_time"] = None

    if is_payment_proof(text):
        state["awaiting_payment"] = False
        state["last_payment_time"] = now
        save_states()
        return await event.reply("💖 Payment confirmed! Ask me for your pic again 😉")

    if state["awaiting_payment"] and is_pic_request(text):
        if not state["last_reminder"] or now - state["last_reminder"] > COOLDOWN:
            state["last_reminder"] = now
            save_states()
            await event.reply(f"⏳ Still waiting for payment 💕\nLink: {PAYMENT_LINK}\nWallet: {WALLET_ADDRESS}")
        return

    if is_pic_request(text):
        if not state["last_payment_time"]:
            state["awaiting_payment"] = True
            state["last_reminder"] = now
            save_states()
            return await event.reply(f"Hey baby 😘 Pics are $5.\nPay here: {PAYMENT_LINK}\nWallet: {WALLET_ADDRESS}")
        else:
            state["last_payment_time"] = None
            save_states()
            return await event.reply("🔥 Here’s your special treat...")

    tip_reply = handle_tip_logic(text)
    if tip_reply:
        return await event.reply(tip_reply)

    # GPT cooldown
    if now - state["last_gpt"] < GPT_COOLDOWN:
        return

    if cid not in chat_histories:
        chat_histories[cid] = [{"role": "system", "content": SYSTEM_PROMPT}]
    chat_histories[cid].append({"role": "user", "content": text})
    trim_history(cid)

    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=chat_histories[cid],
            max_tokens=100,
        )
        bot_reply = resp.choices[0].message.content.strip()
        chat_histories[cid].append({"role": "assistant", "content": bot_reply})
        trim_history(cid)
        state["last_gpt"] = now
        save_states()
        await event.reply(bot_reply)
    except Exception as e:
        await event.reply(f"⚠️ Error: {e}")

async def main():
    load_states()
    await tg_client.start()
    print("🚀 SexyBot running...")
    await tg_client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())

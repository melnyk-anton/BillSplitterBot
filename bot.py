import os
import asyncio
import asyncpg
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------- Env ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
USER1_ID = int(os.getenv("USER1_ID"))
USER2_ID = int(os.getenv("USER2_ID"))
PORT = os.getenv("PORT", 10000)

USERS = {USER1_ID: "anthony", USER2_ID: "dimon"}

# ---------------- Database ----------------
async def init_db():
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    await conn.close()


async def add_expense(user_id: int, amount: float, description: str):
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    await conn.execute(
        "INSERT INTO expenses(user_id, amount, description) VALUES($1, $2, $3)",
        user_id, amount, description,
    )
    await conn.close()


async def get_balances():
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    rows = await conn.fetch("SELECT user_id, SUM(amount) as total FROM expenses GROUP BY user_id")
    await conn.close()

    balances = {USER1_ID: 0.0, USER2_ID: 0.0}
    for row in rows:
        balances[row["user_id"]] = float(row["total"] or 0.0)
    return balances


async def get_history(limit: int = 10):
    conn = await asyncpg.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME
    )
    rows = await conn.fetch(
        "SELECT user_id, amount, description, created_at FROM expenses ORDER BY created_at DESC LIMIT $1",
        limit,
    )
    await conn.close()
    return rows

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in USERS:
        await update.message.reply_text("❌ Sorry, you are not authorized to use this bot.")
        return

    await update.message.reply_text(
        "👋 Welcome to Bill Splitter Bot!\n\n"
        "💰 Use /add <amount> <description> to log an expense.\n"
        "Example: /add 20.5 groceries\n"
        "📊 Use /balance to see current balances.\n"
        "📝 Use /history to see last 10 transactions."
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in USERS:
        await update.message.reply_text("❌ Unauthorized.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /add <amount> <description>")
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Amount must be a number.")
        return

    description = " ".join(context.args[1:])
    await add_expense(uid, amount, description)
    await update.message.reply_text(f"✅ Added {amount:.2f} for {description}.")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in USERS:
        await update.message.reply_text("❌ Unauthorized.")
        return

    balances = await get_balances()
    name1, name2 = USERS[USER1_ID], USERS[USER2_ID]
    b1, b2 = balances[USER1_ID], balances[USER2_ID]

    msg = f"📊 *Balances:*\n{name1}: {b1:.2f} 💵\n{name2}: {b2:.2f} 💵\n"
    diff = (b1 - b2) // 2
    if diff > 0:
        msg += f"💡 {name2} owes {name1} {abs(diff):.2f} 💸"
    elif diff < 0:
        msg += f"💡 {name1} owes {name2} {abs(diff):.2f} 💸"
    else:
        msg += "🤝 You are even!"

    await update.message.reply_text(msg)


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in USERS:
        await update.message.reply_text("❌ Unauthorized.")
        return

    rows = await get_history(10)
    if not rows:
        await update.message.reply_text("📝 No transactions yet.")
        return

    msg = "📝 *Last 10 transactions:*\n"
    for row in rows:
        user_name = USERS.get(row["user_id"], "Unknown")
        msg += f"{row['created_at'].strftime('%Y-%m-%d %H:%M')} - {user_name} spent {row['amount']:.2f} 💵 on {row['description']}\n"

    await update.message.reply_text(msg)


# ---------------- Main ----------------
def main():
    # Initialize DB first
    asyncio.run(init_db())

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("history", history))

    # Run polling (blocking call, manages asyncio internally)
    app.run_polling()


if __name__ == "__main__":
    main()

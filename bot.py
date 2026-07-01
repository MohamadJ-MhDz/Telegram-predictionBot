import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from database import (
    init_db,
    register_user,
    get_todays_matches,
    save_prediction,
    get_leaderboard,
    get_match,
    get_user_predictions,
    get_all_users,
    check_user_has_prediction,
    get_connection,
    calculate_all_scores,
    get_unnotified_finished_matches,
    mark_match_as_post_notified,
    get_user_prediction_for_match,
)
from api import fetch_and_save_worldcup_matches  # ایمپورت تابع دریافت نتایج از ای‌پی‌آی

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def format_match_time(utc_time_str):
    try:
        dt_utc = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
        dt_iran = dt_utc + timedelta(hours=3, minutes=30)
        return dt_iran.strftime("%H:%M")
    except Exception:
        return "نامشخص"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(
        telegram_id=user.id, username=user.username, first_name=user.first_name
    )

    welcome_text = (
        f"سلام {user.first_name} عزیز! به بات پیش‌بینی مسابقات خوش آمدی. 🏆\n\n"
        "در این بات می‌توانید پیش‌بینی‌های خود را برای مسابقات فوتبال ثبت کنید و امتیاز کسب کنید. همچنین می‌توانید جدول رده‌بندی لیگ پیش‌بینی را مشاهده کنید.\n\n"
        "شما می‌توانید با استفاده از دستورات زیر پیش‌بینی‌های خود را ثبت و مدیریت کنید:\n\n"
        "📅 برنامه بازی‌های امروز: /todays_matches\n"
        "⚽️ ثبت یا ویرایش پیش‌بینی: /predict\n"
        "📊 پیش‌بینی‌های من: /my_predictions\n"
        "🏆 جدول رده‌بندی لیگ: /leaderboard"
    )
    await update.message.reply_text(welcome_text)


async def todays_matches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = get_todays_matches()
    if not matches:
        await update.message.reply_text(
            "⚽️ در حال حاضر مسابقه آینده‌ای برای امروز بارگذاری نشده یا بازی‌ها شروع شده‌اند."
        )
        return

    text = "📅 <b>برنامه بازی‌های آینده امروز:</b>\n\n"
    for match in matches:
        iran_time = format_match_time(match["match_time"])
        text += f"⚽️ {match['home_team']} - {match['away_team']} (ساعت {iran_time})\n"
    text += "\n💡 <i>برای پیش‌بینی این مسابقات، دستور /predict را بزنید.</i>"
    await update.message.reply_text(text, parse_mode="HTML")


async def predict_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = get_todays_matches()

    if not matches:
        await update.message.reply_text(
            "⚽️ در حال حاضر بازی قابل پیش‌بینی برای امروز وجود ندارد یا بازی‌ها شروع شده‌اند."
        )
        return

    keyboard = []
    for match in matches:
        iran_time = format_match_time(match["match_time"])
        btn_text = f"{match['home_team']} - {match['away_team']} (ساعت {iran_time})"
        callback_data = f"match_{match['match_id']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])

    reply_markup = InlineKeyboardMarkup(keyboard)

    # متن راهنمای امتیازدهی به همراه درخواست انتخاب بازی
    info_text = (
        "🎯 <b>نحوه محاسبه امتیازات:</b>\n"
        "🟢 <b>۳ امتیاز:</b> پیش‌بینی کاملاً دقیق نتیجه مسابقه\n"
        "🟡 <b>۱ امتیاز:</b> حدس درستِ برنده یا مساوی (اما با نتیجه متفاوت)\n"
        "🔴 <b>۰ امتیاز:</b> پیش‌بینی کاملاً اشتباه\n\n"
        "👇 <b>لطفاً مسابقه مورد نظر خود را برای پیش‌بینی انتخاب کنید:</b>"
    )

    await update.message.reply_text(
        info_text, reply_markup=reply_markup, parse_mode="HTML"
    )


async def my_predictions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    preds = get_user_predictions(telegram_id)
    if not preds:
        await update.message.reply_text(
            "📝 شما هنوز هیچ پیش‌بینی‌ای در سیستم ثبت نکرده‌اید!\nبا منوی /predict شروع کنید."
        )
        return

    text = "📊 <b>تاریخچه پیش‌بینی‌های شما:</b>\n\n"
    for p in preds:
        status_emoji = "⏳ شروع نشده" if p["status"] != "FINISHED" else "🏁 پایان یافته"
        points_text = (
            f" (امتیاز کسب شده: {p['points_earned']})"
            if p["points_earned"] is not None
            else ""
        )
        text += f"⚽️ {p['home_team']} {p['predicted_home']} - {p['predicted_away']} {p['away_team']}\n"
        text += f"وضعیت: {status_emoji}{points_text}\n"
        if p["status"] != "FINISHED":
            text += "💡 <i>برای تغییر این پیش‌بینی، مجدداً دستور /predict را بزنید.</i>\n"
        text += "-------------------------\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    leaders = get_leaderboard()
    if not leaders:
        await update.message.reply_text("هنوز هیچ امتیازی در لیگ ثبت نشده است! 🤷‍♂️")
        return

    text = "🏆 <b>جدول رده‌بندی لیگ پیش‌بینی</b> 🏆\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for index, user in enumerate(leaders):
        score = user["total_score"] if user["total_score"] is not None else 0
        medal = medals[index] if index < 3 else f"{index + 1}."
        text += f"{medal} {user['first_name']} : {score} امتیاز\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def match_click_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    match_id = int(query.data.split("_")[1])
    context.user_data["current_match_id"] = match_id

    match_info = get_match(match_id)
    team1 = match_info["home_team"]
    team2 = match_info["away_team"]

    match_time = datetime.fromisoformat(match_info["match_time"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) >= match_time:
        await query.message.reply_text(
            "❌ متأسفانه این بازی شروع شده و دیگر امکان پیش‌بینی وجود ندارد!"
        )
        return

    help_message = (
        f"شما مسابقه ⚽️ {team1} - {team2} ⚽️ را انتخاب کردید.\n\n"
        f"لطفاً نتیجه را وارد کنید (مقدار جدید جایگزین پیش‌بینی قبلی خواهد شد):\n\n"
        f"👈 عدد اول برای {team1}\n"
        f"👈 عدد دوم برای {team2}\n\n"
        f"مثال: 2-1"
    )
    await query.message.reply_text(help_message)


async def receive_prediction_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "current_match_id" not in context.user_data:
        return

    text = update.message.text.strip()
    match_id = context.user_data["current_match_id"]
    telegram_id = update.effective_user.id

    if "-" not in text:
        await update.message.reply_text(
            "❌ فرمت اشتباه است. لطفاً نتیجه را با خط تیره وارد کنید. مانند: 2-1"
        )
        return

    try:
        team1_pred, team2_pred = map(int, text.split("-"))
        match_info = get_match(match_id)
        team1, team2 = match_info["home_team"], match_info["away_team"]

        success, message = save_prediction(
            telegram_id, match_id, team1_pred, team2_pred
        )

        if success:
            success_message = (
                f"✅ پیش‌بینی شما با موفقیت ثبت/ویرایش شد:\n\n"
                f"⚽️ {team1}  {team1_pred} - {team2_pred}  {team2}"
            )
            await update.message.reply_text(success_message)
            del context.user_data["current_match_id"]
        else:
            await update.message.reply_text(message)

    except ValueError:
        await update.message.reply_text(
            "❌ لطفاً فقط از اعداد انگلیسی و فرمت معتبر استفاده کنید. مانند: 3-0"
        )


# 📡 تسک هوشمند و یکپارچه مدیریت نوتیفیکیشن‌ها و آپدیت خودکار نتایج
async def notification_background_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    user_ids = get_all_users()

    # الف) آپدیت خودکار نتایج بازی‌های امروز از API (هر ۱۰ دقیقه یک‌بار برای صرفه‌جویی در ریکوئست‌ها)
    if "last_api_fetch" not in context.bot_data or (
        now - context.bot_data["last_api_fetch"]
    ) > timedelta(minutes=10):
        try:
            today_str = now.strftime("%Y-%m-%d")
            # گرفتن بازی‌های امروز و همچنین مسابقات دیروز جهت اعمال نتایج نهایی
            yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

            fetch_and_save_worldcup_matches(yesterday_str)
            fetch_and_save_worldcup_matches(today_str)

            context.bot_data["last_api_fetch"] = now
            print(f"🔄 دیتابیس نتایج به صورت خودکار در پس‌زمینه آپدیت شد.")
        except Exception as e:
            print(f"خطا در به‌روزرسانی خودکار دیتابیس: {e}")

    # ب) ارسال نوتیفیکیشن قبل از شروع مسابقات (۳۰ دقیقه قبل بازی)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM matches WHERE pre_notified = 0 AND status IN ('TIMED', 'SCHEDULED', 'NS')"
    )
    pre_matches = cursor.fetchall()

    for match in pre_matches:
        match_time = datetime.fromisoformat(match["match_time"].replace("Z", "+00:00"))
        if timedelta(minutes=0) <= (match_time - now) <= timedelta(minutes=30):
            match_id = match["match_id"]
            for uid in user_ids:
                has_pred = check_user_has_prediction(uid, match_id)
                if has_pred:
                    msg = f"⏳ <b>آخرین فرصت ویرایش!</b>\n\nمسابقه بین ⚽️ {match['home_team']} - {match['away_team']} تا کمتر از ۳۰ دقیقه دیگر آغاز خواهد شد. اگر می‌خواهید ثبت خود را تغییر دهید، سریع‌تر اقدام کنید!"
                else:
                    msg = f"🚨 <b>شما این بازی را پیش‌بینی نکرده‌اید!</b>\n\nکمتر از ۳۰ دقیقه تا شروع مسابقه حساس ⚽️ {match['home_team']} - {match['away_team']} زمان باقیست. سریعاً با دستور /predict نتیجه را حدس بزنید!"
                try:
                    await context.bot.send_message(
                        chat_id=uid, text=msg, parse_mode="HTML"
                    )
                except Exception:
                    pass

            param = "%s" if os.getenv("DATABASE_URL") else "?"
            cursor.execute(
                f"UPDATE matches SET pre_notified = 1 WHERE match_id = {param}",
                (match_id,),
            )
    if hasattr(conn, "commit"):
        conn.commit()
    conn.close()

    # ج) ارسال نوتیفیکیشن پایان بازی و جزئیات امتیاز به صورت هوشمند
    finished_matches = get_unnotified_finished_matches()
    for match in finished_matches:
        match_id = match["match_id"]
        t1, t2 = match["home_team"], match["away_team"]
        s1, s2 = match["home_score"], match["away_score"]

        for uid in user_ids:
            pred = get_user_prediction_for_match(uid, match_id)

            base_msg = f"🏁 <b>پایان مسابقه! نتیجه نهایی ثبت شد.</b>\n\n⚽️ {t1}  {s1} - {s2}  {t2}\n\n"
            if pred:
                p1, p2 = pred["predicted_home"], pred["predicted_away"]
                # محاسبه در لحظه امتیاز برای نمایش فوری در نوتیفیکیشن
                earned = 0
                if p1 == s1 and p2 == s2:
                    earned = 3
                elif (
                    (p1 > p2 and s1 > s2)
                    or (p1 < p2 and s1 < s2)
                    or (p1 == p2 and s1 == s2)
                ):
                    earned = 1

                emoji = (
                    "🔥 فوق‌العاده! امتیاز کامل"
                    if earned == 3
                    else ("✅ امتیاز برد/باخت" if earned == 1 else "❌ بدون امتیاز")
                )
                base_msg += (
                    f"📝 پیش‌بینی شما: ({p1}-{p2})\n🎯 وضعیت: {emoji} (+{earned} امتیاز)"
                )
            else:
                base_msg += (
                    "📝 شما این مسابقه را پیش‌بینی نکرده بودید و امتیازی کسب نکردید."
                )

            try:
                await context.bot.send_message(
                    chat_id=uid, text=base_msg, parse_mode="HTML"
                )
            except Exception:
                pass

        mark_match_as_post_notified(match_id)


def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    job_queue = application.job_queue
    # اجرای تسک پس‌زمینه هر ۶۰ ثانیه برای بررسی دقیق زمان‌ها
    job_queue.run_repeating(notification_background_job, interval=60, first=10)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("todays_matches", todays_matches_command))
    application.add_handler(CommandHandler("predict", predict_command))
    application.add_handler(CommandHandler("my_predictions", my_predictions_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))

    application.add_handler(
        CallbackQueryHandler(match_click_handler, pattern="^match_")
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_prediction_text)
    )

    print("بات تلگرام با سیستم نوتیفیکیشن همه‌جانبه لایو شد...")
    application.run_polling()


if __name__ == "__main__":
    main()

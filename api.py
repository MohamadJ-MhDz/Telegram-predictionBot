import os
import requests
from dotenv import load_dotenv

# ایمپورت کردن توابع دیتابیس به صورت یکجا و تمیز
from database import save_matches, calculate_all_scores

load_dotenv()
API_KEY = os.getenv("FOOTBALL_DATA_TOKEN")


def fetch_and_save_worldcup_matches(date_str="2026-06-30"):
    url = "https://api.football-data.org/v4/competitions/WC/matches"

    querystring = {"dateFrom": date_str, "dateTo": date_str}
    headers = {"X-Auth-Token": API_KEY}

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        data = response.json()

        matches = data.get("matches", [])

        if not matches:
            print(f"هیچ بازی برای جام جهانی در تاریخ {date_str} یافت نشد.")
            return []

        print(f"تعداد {len(matches)} بازی از سرور دریافت شد. در حال پردازش...\n")

        world_cup_matches = []
        for match in matches:
            match_id = match["id"]
            home_team = match["homeTeam"]["name"]
            away_team = match["awayTeam"]["name"]
            status = match["status"]
            match_time = match["utcDate"]

            # استخراج ایمن نتایج (جلوگیری از ارور در صورت شروع نشدن بازی)
            score_data = match.get("score", {}).get("fullTime", {})
            home_score = score_data.get("home") if score_data else None
            away_score = score_data.get("away") if score_data else None

            print(f"آیدی: {match_id} | ⚽️ {home_team} vs {away_team} | وضعیت: {status}")

            world_cup_matches.append(
                {
                    "match_id": match_id,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_time": match_time,
                    "home_score": home_score,
                    "away_score": away_score,
                    "status": status,
                }
            )

        # ۱. ذخیره مستقیم لیست پردازش شده در دیتابیس SQLite
        save_matches(world_cup_matches)

        # ۲. محاسبه اتوماتیک امتیازات بعد از دریافت نتایج جدید
        calculate_all_scores()
        print("✅ محاسبه امتیازات با موفقیت انجام شد.")

        return world_cup_matches

    except requests.exceptions.HTTPError as http_err:
        print(f"❌ خطای HTTP: {http_err} - توکن نامعتبر است یا محدودیت درخواست سرور.")
    except Exception as e:
        print(f"❌ خطا در پردازش اطلاعات: {e}")
        return []


if __name__ == "__main__":
    if not API_KEY:
        print("خطا: کلید FOOTBALL_DATA_TOKEN در فایل .env یافت نشد.")
    else:
        from datetime import datetime

        # گرفتن تاریخ امروز سیستم به فرمت YYYY-MM-DD
        today_str = datetime.now().strftime("%Y-%m-%d")

        print(
            f"🚀 در حال ارتباط با football-data.org برای تاریخ امروز ({today_str})..."
        )

        # اجرا برای تاریخ پویا و خودکار امروز
        fetch_and_save_worldcup_matches(today_str)

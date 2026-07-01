import os
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timezone

DB_NAME = "predictor.db"


def get_connection():
    """اتصال هوشمند: اگر متغیر سرور بود به PostgreSQL و اگر لوکال بود به SQLite وصل می‌شود"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        return conn


def init_db():
    """ساخت جداول دیتابیس با ستون‌های جدید ردیابی نوتیفیکیشن"""
    conn = get_connection()
    cursor = conn.cursor()

    # جدول کاربران
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            total_score INTEGER DEFAULT 0
        )
    """
    )

    # جدول مسابقات (اضافه شدن ستون‌های ردیابی نوتیف پیش از بازی و پس از بازی)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            match_id INTEGER PRIMARY KEY,
            home_team TEXT,
            away_team TEXT,
            match_time TEXT,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT DEFAULT 'NS',
            pre_notified INTEGER DEFAULT 0,
            post_notified INTEGER DEFAULT 0
        )
    """
    )

    # جدول پیش‌بینی‌ها
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT,
            match_id INTEGER,
            predicted_home INTEGER,
            predicted_away INTEGER,
            points_earned INTEGER,
            FOREIGN KEY (telegram_id) REFERENCES users (telegram_id),
            FOREIGN KEY (match_id) REFERENCES matches (match_id)
        )
    """
    )

    # ساخت ایندکس یونیک برای پیش‌بینی‌ها (اگر در لایت موجود نبود)
    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_match ON predictions(telegram_id, match_id)"
        )
    except Exception:
        pass

    if hasattr(conn, "commit"):
        conn.commit()
    conn.close()


def register_user(telegram_id, username, first_name):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO NOTHING
        """.replace(
                "?", "%s" if os.getenv("DATABASE_URL") else "?"
            ),
            (telegram_id, username, first_name),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def save_matches(matches_list):
    conn = get_connection()
    cursor = conn.cursor()
    param = "%s" if os.getenv("DATABASE_URL") else "?"

    for match in matches_list:
        if os.getenv("DATABASE_URL"):
            cursor.execute(
                """
                INSERT INTO matches (match_id, home_team, away_team, match_time, home_score, away_score, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(match_id) DO UPDATE SET
                    status=EXCLUDED.status,
                    home_score=EXCLUDED.home_score,
                    away_score=EXCLUDED.away_score
            """,
                (
                    match["match_id"],
                    match["home_team"],
                    match["away_team"],
                    match["match_time"],
                    match.get("home_score"),
                    match.get("away_score"),
                    match["status"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO matches (match_id, home_team, away_team, match_time, home_score, away_score, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id) DO UPDATE SET
                    status=excluded.status,
                    home_score=excluded.home_score,
                    away_score=excluded.away_score
            """,
                (
                    match["match_id"],
                    match["home_team"],
                    match["away_team"],
                    match["match_time"],
                    match.get("home_score"),
                    match.get("away_score"),
                    match["status"],
                ),
            )

    conn.commit()
    conn.close()


def get_todays_matches():
    conn = get_connection()
    cursor = conn.cursor()
    now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    cursor.execute(
        f"""
        SELECT * FROM matches 
        WHERE status IN ('TIMED', 'SCHEDULED', 'NS') AND match_time > ?
    """.replace(
            "?", "%s" if os.getenv("DATABASE_URL") else "?"
        ),
        (now_utc,),
    )
    matches = cursor.fetchall()
    conn.close()
    return matches


def save_prediction(telegram_id, match_id, predicted_home, predicted_away):
    """ثبت یا ویرایش پیش‌بینی همراه با قفل ضد تقلب (Anti-Cheat)"""
    conn = get_connection()
    cursor = conn.cursor()
    param = "%s" if os.getenv("DATABASE_URL") else "?"

    try:
        # بررسی زمان بازی: اگر بازی شروع شده باشد اجازه ثبت نمی‌دهد
        cursor.execute(
            f"SELECT match_time FROM matches WHERE match_id = {param}", (match_id,)
        )
        match = cursor.fetchone()
        if not match:
            return False, "مسابقه یافت نشد."

        match_time = datetime.fromisoformat(match["match_time"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) >= match_time:
            return False, "❌ متأسفانه بازی شروع شده و زمان پیش‌بینی به پایان رسیده است!"

        cursor.execute(
            """
            INSERT INTO predictions (telegram_id, match_id, predicted_home, predicted_away)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id, match_id) DO UPDATE SET
                predicted_home=EXCLUDED.predicted_home,
                predicted_away=EXCLUDED.predicted_away
        """.replace(
                "?", "%s" if os.getenv("DATABASE_URL") else "?"
            ),
            (telegram_id, match_id, predicted_home, predicted_away),
        )
        conn.commit()
        return True, "موفق"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()


def get_match(match_id):
    conn = get_connection()
    cursor = conn.cursor()
    param = "%s" if os.getenv("DATABASE_URL") else "?"
    cursor.execute(f"SELECT * FROM matches WHERE match_id = {param}", (match_id,))
    match = cursor.fetchone()
    conn.close()
    return match


def get_user_predictions(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()
    param = "%s" if os.getenv("DATABASE_URL") else "?"
    cursor.execute(
        f"""
        SELECT m.home_team, m.away_team, m.status, m.match_time,
               p.predicted_home, p.predicted_away, p.points_earned
        FROM predictions p
        JOIN matches m ON p.match_id = m.match_id
        WHERE p.telegram_id = {param}
    """,
        (telegram_id,),
    )
    predictions = cursor.fetchall()
    conn.close()
    return predictions


def get_leaderboard():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT first_name, total_score FROM users ORDER BY total_score DESC LIMIT 10"
    )
    leaders = cursor.fetchall()
    conn.close()
    return leaders


def calculate_all_scores():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT p.id, p.telegram_id, p.predicted_home, p.predicted_away, m.home_score, m.away_score
        FROM predictions p
        JOIN matches m ON p.match_id = m.match_id
        WHERE m.status = 'FINISHED' AND p.points_earned IS NULL
    """
    )
    pending_predictions = cursor.fetchall()

    for pred in pending_predictions:
        points = 0
        p_home, p_away = pred["predicted_home"], pred["predicted_away"]
        m_home, m_away = pred["home_score"], pred["away_score"]

        if p_home == m_home and p_away == m_away:
            points = 3
        elif (
            (p_home > p_away and m_home > m_away)
            or (p_home < p_away and m_home < m_away)
            or (p_home == p_away and m_home == m_away)
        ):
            points = 1

        cursor.execute(
            "UPDATE predictions SET points_earned = ? WHERE id = ?".replace(
                "?", "%s" if os.getenv("DATABASE_URL") else "?"
            ),
            (points, pred["id"]),
        )
        cursor.execute(
            """
            UPDATE users SET total_score = (SELECT COALESCE(SUM(points_earned), 0) FROM predictions WHERE telegram_id = ?) WHERE telegram_id = ?
        """.replace(
                "?", "%s" if os.getenv("DATABASE_URL") else "?"
            ),
            (pred["telegram_id"], pred["telegram_id"]),
        )

    conn.commit()
    conn.close()


def get_all_users():
    """دریافت لیست تمام کاربران برای ارسال نوتیفیکیشن عمومی"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users")
    users = cursor.fetchall()
    conn.close()
    return [u["telegram_id"] for u in users]


def check_user_has_prediction(telegram_id, match_id):
    """بررسی اینکه آیا کاربر این بازی خاص را پیش‌بینی کرده یا خیر"""
    conn = get_connection()
    cursor = conn.cursor()
    param = "%s" if os.getenv("DATABASE_URL") else "?"
    cursor.execute(
        f"SELECT id FROM predictions WHERE telegram_id = {param} AND match_id = {param}",
        (telegram_id, match_id),
    )
    pred = cursor.fetchone()
    conn.close()
    return pred is not None


def get_unnotified_finished_matches():
    """پیدا کردن بازی‌هایی که تموم شدن ولی هنوز نوتیف پایان بازی‌شون فرستاده نشده"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM matches WHERE status = 'FINISHED' AND post_notified = 0"
    )
    matches = cursor.fetchall()
    conn.close()
    return matches


def mark_match_as_post_notified(match_id):
    """تغییر وضعیت نوتیف پایان بازی به فرستاده شده"""
    conn = get_connection()
    cursor = conn.cursor()
    param = "%s" if os.getenv("DATABASE_URL") else "?"
    cursor.execute(
        f"UPDATE matches SET post_notified = 1 WHERE match_id = {param}", (match_id,)
    )
    if hasattr(conn, "commit"):
        conn.commit()
    conn.close()


def get_user_prediction_for_match(telegram_id, match_id):
    """گرفتن پیش‌بینی یک کاربر خاص برای یک بازی خاص"""
    conn = get_connection()
    cursor = conn.cursor()
    param = "%s" if os.getenv("DATABASE_URL") else "?"
    cursor.execute(
        f"SELECT * FROM predictions WHERE telegram_id = {param} AND match_id = {param}",
        (telegram_id, match_id),
    )
    pred = cursor.fetchone()
    conn.close()
    return pred

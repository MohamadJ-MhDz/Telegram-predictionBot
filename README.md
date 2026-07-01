# 🏆 Football Prediction Telegram Bot

A smart, fully automated Telegram bot that allows users to predict football match scores, compete on a leaderboard, and receive real-time notifications for upcoming matches and final results. 

This bot is designed with a seamless User Experience (UX), featuring an anti-cheat system and background automation to keep data fresh without manual intervention.

## ✨ Features

*   **🔮 Intuitive Predictions**: Users can easily view upcoming matches and submit their score predictions via interactive inline keyboards (glass buttons).
*   **🛡️ Anti-Cheat System**: Predictions are strictly locked the exact moment the match kicks off (based on UTC server time). No last-minute cheating!
*   **🔔 Smart Notifications (JobQueue)**:
    *   *Pre-Match*: Sends personalized reminders 30 minutes before kick-off (prompts users to predict if they haven't, or warns them it's the last chance to edit).
    *   *Post-Match*: Instantly notifies users of the final match result, their prediction, and points earned.
*   **🔄 Automated Data Fetching**: Runs background jobs to automatically fetch daily fixtures and update completed match results from the API.
*   **🏆 Dynamic Leaderboard**: Ranks users based on their prediction accuracy:
    *   `3 Points`: Exact score match.
    *   `1 Point`: Correct match outcome (win/lose/draw) but different score.
    *   `0 Points`: Incorrect prediction.
*   **💾 Flexible Database**: Dual-support for **SQLite** (for local development or persistent simple hosting) and **PostgreSQL** (for cloud hosting like Supabase).

## 🛠️ Tech Stack

*   **Language**: Python 3.10+
*   **Telegram API**: `python-telegram-bot` (v20+ with JobQueue support)
*   **Database**: `sqlite3` (built-in) & `psycopg2` (PostgreSQL)
*   **Environment Management**: `python-dotenv`

## ⚙️ Prerequisites

Before running the bot, you need to get the following tokens:
1.  **Telegram Bot Token**: Get it from [@BotFather](https://t.me/BotFather) on Telegram.
2.  **Football Data API Token**: Sign up and get a free API token from your preferred football data provider (e.g., football-data.org).

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/football-prediction-bot.git](https://github.com/yourusername/football-prediction-bot.git)
   cd football-prediction-bot

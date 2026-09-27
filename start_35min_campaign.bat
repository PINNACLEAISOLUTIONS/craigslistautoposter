@echo off
echo ============================================================
echo   Silver Rose Management - Continuous 35-Minute Multi-City
echo ============================================================
cd /d C:\Users\futur\gemini_workspace\craigslistautoposter
python post_silver_rose.py --continuous --interval-mins 35 --publish
pause

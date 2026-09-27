@echo off
title Silver Rose - Chicago Hourly Continuous Poster
color 0B
cls
echo ======================================================================
echo             SILVER ROSE MANAGEMENT - CHICAGO AUTO-POSTER
echo                   (Obscura Stealth Browser / Real IP)
echo ======================================================================
echo.
echo Active Rotation (Advances section on each post + alternates category):
echo   1. North Chicagoland  -> Activity Partners
echo   2. West Chicagoland   -> General Community (with Promo Image)
echo   3. South Chicagoland  -> Activity Partners
echo   4. City of Chicago    -> General Community (with Promo Image)
echo   5. North Chicagoland  -> General Community (with Promo Image)
echo   6. West Chicagoland   -> Activity Partners
echo   7. South Chicagoland  -> General Community (with Promo Image)
echo   8. City of Chicago    -> Activity Partners
echo.
echo ----------------------------------------------------------------------
echo Pacing: 60-Minute Real-Time Terminal Countdown Between Posts
echo ----------------------------------------------------------------------
echo.
cd /d "%~dp0"
python post_chicago_obscura.py --continuous --publish --interval-mins 60 --start-step 0
pause

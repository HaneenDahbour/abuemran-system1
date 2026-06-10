@echo off
REM =================================================
REM  نظام أبو عمران — سكريبت النسخ الاحتياطي
REM  الاستخدام: انقر مرتين أو شغّل من CMD
REM =================================================

set BACKUP_DIR=%~dp0backups
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

set TIMESTAMP=%date:~10,4%-%date:~4,2%-%date:~7,2%_%time:~0,2%-%time:~3,2%
set TIMESTAMP=%TIMESTAMP: =0%
set FILENAME=%BACKUP_DIR%\backup_%TIMESTAMP%.sql

echo ===================================
echo   نظام أبو عمران — نسخ احتياطي
echo   %date% %time%
echo ===================================
echo.

REM ─── تأكدي أن pg_dump مثبّت (PostgreSQL Client) ───
where pg_dump >nul 2>&1
if %errorlevel% neq 0 (
    echo [خطأ] pg_dump غير موجود.
    echo حمّلي PostgreSQL Client من: https://www.postgresql.org/download/
    pause
    exit /b 1
)

REM ─── اقرئي DATABASE_URL من .env ───
set DATABASE_URL=
for /f "tokens=1,2 delims==" %%a in (%~dp0backend-py\.env) do (
    if "%%a"=="DATABASE_URL" set DATABASE_URL=%%b
)

if "%DATABASE_URL%"=="" (
    echo [خطأ] DATABASE_URL غير موجود في backend-py\.env
    pause
    exit /b 1
)

echo حفظ النسخة في: %FILENAME%
echo.

pg_dump "%DATABASE_URL%" --no-owner --no-acl -f "%FILENAME%"

if %errorlevel% equ 0 (
    echo.
    echo [نجاح] تم حفظ النسخة الاحتياطية بنجاح
    echo الملف: %FILENAME%

    REM احتفظ بآخر 10 نسخ فقط
    for /f "skip=10 delims=" %%f in ('dir /b /o-d "%BACKUP_DIR%\backup_*.sql"') do (
        del "%BACKUP_DIR%\%%f"
    )
) else (
    echo [خطأ] فشل النسخ الاحتياطي
)

echo.
pause

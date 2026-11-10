@echo off
rem AStock daily bar incremental update (QMT / xtquant).
rem Requires: miniQMT client running & logged in; D:\py has xtquant + pymysql.
cd /d D:\AgentFrame\TradingAgentForChina

if not exist backend\logs mkdir backend\logs
set LOG=backend\logs\qmt_daily_update.log

echo [%date% %time%] daily bar incremental start >> %LOG%
D:\py\python.exe backend\scripts\pipeline\qmt_backfill_daily.py >> %LOG% 2>&1
echo [%date% %time%] daily bar incremental end (exit=%errorlevel%) >> %LOG%

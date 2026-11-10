@echo off
rem Register Windows scheduled task: daily bar incremental update at 16:30 weekdays.
rem Run this file as Administrator. Re-running overwrites the same task name.
schtasks /create /f /tn "AStockAgent-DailyBar" /tr "D:\AgentFrame\TradingAgentForChina\backend\scripts\pipeline\run_qmt_daily.bat" /sc weekly /d MON,TUE,WED,THU,FRI /st 16:30

echo.
echo Task registered. Check with:
echo   schtasks /query /tn "AStockAgent-DailyBar"
echo Delete with:
echo   schtasks /delete /tn "AStockAgent-DailyBar" /f
pause

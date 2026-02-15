@echo off
REM InstantRisk E2E Integration Test Runner
REM Usage: run_e2e_test.bat [--no-backend]

echo ============================================================
echo  InstantRisk E2E Integration Test
echo ============================================================

REM Kill any stale Chrome/ChromeDriver processes
taskkill /F /IM chromedriver.exe >nul 2>&1
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Start ChromeDriver
echo Starting ChromeDriver on port 4444...
start /B "" "%USERPROFILE%\chromedriver\chromedriver.exe" --port=4444
timeout /t 3 /nobreak >nul

REM Check ChromeDriver
curl -s http://localhost:4444/status >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] ChromeDriver failed to start.
    echo Make sure chromedriver.exe is at %USERPROFILE%\chromedriver\chromedriver.exe
    exit /b 1
)
echo ChromeDriver ready.

REM Run the test
if "%1"=="--no-backend" (
    echo Running UI-only test (no backend)...
    call flutter drive --driver=test_driver/integration_test.dart --target=integration_test/full_e2e_test.dart -d chrome
) else (
    echo Running full E2E test with real backend...
    call flutter drive --driver=test_driver/integration_test.dart --target=integration_test/full_e2e_test.dart -d chrome --dart-define=BASE_URL=https://d2f065h47nuk0c.cloudfront.net/api/v1
)

set TEST_EXIT=%ERRORLEVEL%

REM Cleanup
taskkill /F /IM chromedriver.exe >nul 2>&1

if %TEST_EXIT% equ 0 (
    echo.
    echo [SUCCESS] All tests passed!
) else (
    echo.
    echo [FAILURE] Tests failed with exit code %TEST_EXIT%
)

exit /b %TEST_EXIT%

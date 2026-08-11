@echo off
cd /d "%~dp0"
echo Running local product media factory acceptance...
echo This local test creates product image, detail image, MP4 video, and visual report.
echo.
npm run acceptance:product-media:local
echo.
echo Report folder:
echo %cd%\????\?????\????????
echo.
pause

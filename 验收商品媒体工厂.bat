@echo off
cd /d "%~dp0"
echo Running product media factory acceptance...
echo This test creates product image, detail image, MP4 video, and checks online artifacts.
echo.
npm run acceptance:product-media -- https://wjhai.cn/merchant-admin
echo.
echo Report folder:
echo %cd%\????\?????\????????
echo.
pause

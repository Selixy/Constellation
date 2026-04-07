@echo off
setlocal enabledelayedexpansion

set /p ASSET_NAME=Nom de l'asset: 

if "%ASSET_NAME%"=="" (
  echo Nom invalide.
  exit /b 1
)

set "ASSET_DIR=%~dp0%ASSET_NAME%"

if exist "%ASSET_DIR%" (
  echo Le dossier existe deja: %ASSET_DIR%
  exit /b 1
)

mkdir "%ASSET_DIR%\output\textures"

if errorlevel 1 (
  echo Erreur pendant la creation des dossiers.
  exit /b 1
)

type nul > "%ASSET_DIR%\.gitkeep"
type nul > "%ASSET_DIR%\output\.gitkeep"
type nul > "%ASSET_DIR%\output\textures\.gitkeep"

echo Structure creee:
echo - %ASSET_DIR%
echo - %ASSET_DIR%\output
echo - %ASSET_DIR%\output\textures
echo - fichiers .gitkeep crees

endlocal

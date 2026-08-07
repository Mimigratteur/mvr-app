@echo off
title Installation du demarrage automatique -- Pont MVR
cd /d "%~dp0"

echo ============================================================
echo  Installation du demarrage automatique du pont MVR ^<-^> Audiveris
echo ============================================================
echo.
echo Ce script cree un raccourci dans le dossier de demarrage de
echo Windows, pointant vers demarrer_pont.bat. A partir de maintenant,
echo le pont se lancera tout seul (fenetre reduite) a chaque ouverture
echo de session -- plus besoin de double-cliquer dessus manuellement
echo avant d'utiliser MVR.
echo.

set "TARGET=%~dp0demarrer_pont.bat"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP%\Pont MVR Audiveris.lnk"

if not exist "%TARGET%" (
  echo [ERREUR] demarrer_pont.bat est introuvable a cote de ce script.
  echo Assure-toi que les deux fichiers sont dans le meme dossier.
  pause
  exit /b 1
)

powershell -NoProfile -Command ^
  "$s = New-Object -ComObject WScript.Shell; $sc = $s.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = '%TARGET%'; $sc.WorkingDirectory = '%~dp0'; $sc.WindowStyle = 7; $sc.Description = 'Pont local MVR <-> Audiveris'; $sc.Save()"

if not exist "%SHORTCUT%" (
  echo.
  echo [ERREUR] La creation du raccourci a echoue.
  echo Tu peux le faire toi-meme : clic droit sur demarrer_pont.bat,
  echo "Creer un raccourci", puis deplace ce raccourci dans :
  echo %STARTUP%
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  C'est fait ! Le pont demarrera desormais automatiquement,
echo  fenetre reduite, a chaque ouverture de session Windows.
echo ============================================================
echo.
echo Raccourci cree :
echo   %SHORTCUT%
echo.
echo Pour DESACTIVER le demarrage automatique plus tard :
echo   1. Appuie sur Windows+R, tape "shell:startup", Entree.
echo   2. Supprime le raccourci "Pont MVR Audiveris".
echo.
echo Veux-tu lancer le pont maintenant pour verifier que tout
echo fonctionne ? Ferme cette fenetre et double-clique sur
echo demarrer_pont.bat, ou attends simplement la prochaine ouverture
echo de session Windows.
echo.
pause

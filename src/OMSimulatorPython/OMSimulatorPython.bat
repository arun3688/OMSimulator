@echo off

set PYTHONPATH=%~dp0\..\lib;%PYTHONPATH%
set PATH=%~dp0\..\lib;%PATH%

python %*

@echo off
rem Liga o Atrial para usar no dia a dia: dois cliques neste arquivo.
rem Para desligar, feche esta janela (ou aperte Ctrl+C).
rem
rem (.cmd e nao .ps1: o Windows bloqueia scripts do PowerShell por
rem padrao, e um .cmd abre com dois cliques sem configurar nada.)

title Atrial
rem %~dp0 = a pasta onde ESTE arquivo esta, de onde quer que seja aberto
cd /d "%~dp0backend"
venv\Scripts\python servidor.py

rem Se o servidor parar (erro ou Ctrl+C), a janela espera uma tecla
rem antes de fechar: assim da para ler a mensagem.
pause

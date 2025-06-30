@echo off
nuitka --onefile --standalone --remove-output --enable-plugin=tk-inter --windows-icon-from-ico=ICON.ico --output-dir=dist poly.py
pause
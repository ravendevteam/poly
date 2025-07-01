#!/bin/sh
nuitka --onefile --standalone --remove-output --enable-plugin=tk-inter --windows-icon-from-ico=ICON.ico --output-dir=dist poly.py
mv dist/poly.bin dist/poly

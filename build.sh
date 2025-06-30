#!/bin/sh
echo "Beginning Poly build process..."
if ! [ -f /usr/bin/nuitka ]; then
    echo "Nuitka was not found on your system. Continue anyways? (y/N)"
    read -n1 nuitka_continue
    if [ "$nuitka_continue" != "y" ]; then
        exit
    fi
fi

nuitka --onefile --standalone --remove-output --enable-plugin=tk-inter --windows-icon-from-ico=ICON.ico --output-dir=dist poly.py

mv dist/poly.bin dist/poly

echo "Build complete!"

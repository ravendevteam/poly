@echo off
set FileVersion=1.0.0.0
set ProductVersion=1.2.0.0

python -m nuitka --onefile --standalone --enable-plugins=tk-inter --remove-output --output-dir=dist --output-filename=Poly.exe --follow-imports --product-name="Poly" --company-name="Raven Development Team" --file-description="A terminal multiplexer with tabs, autocomplete, and more." --file-version=%FileVersion% --product-version=%ProductVersion% --copyright="Copyright (c) 2025 Raven Development Team" --onefile-tempdir-spec="{CACHE_DIR}\RavenDevelopmentTeam\Poly\{VERSION}" poly.py
pause
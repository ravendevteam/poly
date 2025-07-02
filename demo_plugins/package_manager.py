"""
    Plugin Name: Poly Package Manager
    Description: A package manager for Poly to install plugins from a central repository.
    Author: mre31
    Version: 1.0
    Last Updated: July 2, 2025
"""

import os
import json
import urllib.request
from urllib.error import URLError, HTTPError
import hashlib
import time

REPO_URL = "https://raw.githubusercontent.com/mre31/ppm-poly-package-manager/master/"
MANIFEST_FILE = "plugins.json"

def get_manifest_url():
    """Returns the manifest URL with a cache-busting query parameter."""
    return f"{REPO_URL}{MANIFEST_FILE}?_={int(time.time())}"

def fetch_manifest(tab):
    """
    Fetches the plugin manifest from the repository, bypassing caches.
    Returns the parsed manifest as a dictionary, or None on error.
    """
    manifest_url = get_manifest_url()
    
    try:
        urllib.request.urlcleanup()
        
        req = urllib.request.Request(
            manifest_url,
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
            }
        )
        
        with urllib.request.urlopen(req) as response:
            manifest_data = response.read().decode('utf-8')
            return json.loads(manifest_data)
            
    except (HTTPError, URLError) as e:
        tab.add(f"Error: Could not fetch plugin manifest. {e}")
        return None
    except json.JSONDecodeError:
        tab.add("Error: Could not parse plugin manifest.")
        return None

def get_plugins_dir():
    """Returns the absolute path to the user's plplugins directory."""
    return os.path.join(os.path.expanduser("~"), "plplugins")

def ppm_install(tab, plugin_name):
    """
    Downloads and installs a plugin from the repository with hash verification.
    """
    if not plugin_name:
        tab.add("Usage: ppm install <plugin_name>")
        return

    manifest = fetch_manifest(tab)
    if manifest is None:
        return

    plugins = manifest.get("plugins", {})
    if plugin_name not in plugins:
        tab.add(f"Error: Plugin '{plugin_name}' not found in the repository.")
        return

    plugin_info = plugins[plugin_name]
    plugin_file = plugin_info.get("file")
    expected_hash = plugin_info.get("sha256")
    
    if not plugin_file or not expected_hash:
        tab.add(f"Error: Plugin '{plugin_name}' is missing 'file' or 'sha256' in manifest.")
        return

    plugins_dir = get_plugins_dir()
    dest_filename = os.path.basename(plugin_file)
    plugin_path = os.path.join(plugins_dir, dest_filename)
    if os.path.exists(plugin_path):
        tab.add(f"Plugin '{plugin_name}' is already installed.")
        return

    plugin_url = REPO_URL + plugin_file

    try:
        with urllib.request.urlopen(plugin_url) as response:
            plugin_content = response.read()
    except (HTTPError, URLError) as e:
        tab.add(f"Error: Could not download plugin file. {e}")
        return

    actual_hash = hashlib.sha256(plugin_content).hexdigest()
    if actual_hash != expected_hash:
        tab.add("Error: Hash mismatch! The downloaded file may be corrupted or tampered with.")
        tab.add(f"  Expected: {expected_hash}")
        tab.add(f"  Actual:   {actual_hash}")
        return
    
    tab.add("Hash verification successful.")
    
    plugins_dir = get_plugins_dir()
    dest_filename = os.path.basename(plugin_file)
    plugin_path = os.path.join(plugins_dir, dest_filename)
    os.makedirs(plugins_dir, exist_ok=True)

    try:
        with open(plugin_path, 'wb') as f:
            f.write(plugin_content)
        tab.add(f"Successfully installed plugin '{plugin_name}' to {plugin_path}")
        tab.add("Please restart Poly to load the new plugin.")
    except IOError as e:
        tab.add(f"Error: Could not write plugin file. {e}")

def ppm_help(tab):
    """Displays the help message for ppm."""
    tab.add("Poly Package Manager (PPM) - Help")
    tab.add("Usage: ppm <command> [options]")
    tab.add("")
    tab.add("Commands:")
    tab.add("  install (i) <plugin_name>   - Installs a plugin from the repository.")
    tab.add("  uninstall (un) <plugin_name> - Uninstalls a plugin.")
    tab.add("  update (up) <plugin|--all>  - Updates one or all installed plugins.")
    tab.add("  list (ls) [-i]              - Lists available or installed plugins.")
    tab.add("  search <keyword>            - Searches for plugins by keyword.")
    tab.add("  info <plugin_name>          - Shows detailed information about a plugin.")
    tab.add("  enable <plugin_name>        - Enables an installed plugin.")
    tab.add("  disable <plugin_name>       - Disables an installed plugin.")
    tab.add("  doctor                      - Checks for potential issues.")
    tab.add("  help                        - Shows this help message.")

def ppm_list(tab, installed_only=False):
    """Lists available or installed plugins."""
    plugins_dir = get_plugins_dir()
    if installed_only:
        tab.add("Installed plugins:")
        if not os.path.exists(plugins_dir):
            tab.add("  No plugins installed.")
            return
        
        found_plugins = False
        for fname in os.listdir(plugins_dir):
            if fname.endswith(".py"):
                tab.add(f"  - {os.path.splitext(fname)[0]} (enabled)")
                found_plugins = True
            elif fname.endswith(".py.disabled"):
                tab.add(f"  - {os.path.splitext(os.path.splitext(fname)[0])[0]} (disabled)")
                found_plugins = True
        
        if not found_plugins:
            tab.add("  No plugins installed.")

    else:
        tab.add("Available plugins from repository:")
        manifest = fetch_manifest(tab)
        if manifest is None:
            return
        
        plugins = manifest.get("plugins", {})
        if not plugins:
            tab.add("  No plugins found in the repository.")
            return

        for name, info in plugins.items():
            tab.add(f"  - {name} (v{info.get('version', 'N/A')}): {info.get('description', 'No description')}")

def ppm_uninstall(tab, plugin_name):
    """Uninstalls a plugin."""
    if not plugin_name:
        tab.add("Usage: ppm uninstall <plugin_name>")
        return

    plugins_dir = get_plugins_dir()
    
    manifest = fetch_manifest(tab)
    if manifest is None:
        plugin_file_name = f"{plugin_name}.py"
    else:
        plugins = manifest.get("plugins", {})
        plugin_info = plugins.get(plugin_name)
        if not plugin_info:
            tab.add(f"Warning: Plugin '{plugin_name}' not in manifest, attempting to remove anyway.")
            plugin_file_name = f"{plugin_name}.py"
        else:
            plugin_file_name = os.path.basename(plugin_info.get("file"))

    plugin_path = os.path.join(plugins_dir, plugin_file_name)

    if not os.path.exists(plugin_path):
        tab.add(f"Error: Plugin '{plugin_name}' is not installed.")
        return

    try:
        os.remove(plugin_path)
        tab.add(f"Successfully uninstalled plugin '{plugin_name}'.")
        tab.add("Please restart Poly for the change to take effect.")
    except OSError as e:
        tab.add(f"Error: Could not remove plugin file. {e}")

def ppm_search(tab, keyword):
    """Searches for plugins in the repository."""
    if not keyword:
        tab.add("Usage: ppm search <keyword>")
        return

    manifest = fetch_manifest(tab)
    if manifest is None:
        return

    plugins = manifest.get("plugins", {})
    matches = []
    for name, info in plugins.items():
        if keyword.lower() in name.lower() or keyword.lower() in info.get('description', '').lower():
            matches.append((name, info))

    if not matches:
        tab.add("No plugins found matching your search.")
        return

    for name, info in matches:
        tab.add(f"  - {name} (v{info.get('version', 'N/A')}): {info.get('description', 'No description')}")

def ppm_update(tab, plugin_name):
    """Updates one or all plugins."""
    if not plugin_name:
        tab.add("Usage: ppm update <plugin_name|--all>")
        return

    if plugin_name == "--all":
        plugins_dir = get_plugins_dir()
        if not os.path.exists(plugins_dir):
            tab.add("No plugins installed.")
            return
        
        installed_plugins = [os.path.splitext(fname)[0] for fname in os.listdir(plugins_dir) if fname.endswith(".py")]
        if not installed_plugins:
            tab.add("No plugins to update.")
            return
            
        for p_name in installed_plugins:
            ppm_install(tab, p_name)
    else:
        ppm_install(tab, plugin_name)

def ppm_info(tab, plugin_name):
    """Displays detailed information about a plugin."""
    if not plugin_name:
        tab.add("Usage: ppm info <plugin_name>")
        return

    manifest = fetch_manifest(tab)
    if manifest is None:
        return

    plugins = manifest.get("plugins", {})
    if plugin_name not in plugins:
        tab.add(f"Error: Plugin '{plugin_name}' not found in the repository.")
        return

    info = plugins[plugin_name]
    tab.add(f"--- Plugin Information: {plugin_name} ---")
    tab.add(f"  Version:     {info.get('version', 'N/A')}")
    tab.add(f"  Author:      {info.get('author', 'N/A')}")
    tab.add(f"  Description: {info.get('description', 'No description provided.')}")
    tab.add(f"  File:        {info.get('file', 'N/A')}")
    tab.add(f"  SHA256:      {info.get('sha256', 'N/A')}")

def _get_plugin_paths(plugin_name):
    """Helper to get enabled and disabled paths for a plugin."""
    plugins_dir = get_plugins_dir()
    base_path = os.path.join(plugins_dir, f"{plugin_name}.py")
    return base_path, f"{base_path}.disabled"

def ppm_enable(tab, plugin_name):
    """Enables an installed plugin."""
    if not plugin_name:
        tab.add("Usage: ppm enable <plugin_name>")
        return
    
    enabled_path, disabled_path = _get_plugin_paths(plugin_name)

    if not os.path.exists(disabled_path):
        if os.path.exists(enabled_path):
            tab.add(f"Plugin '{plugin_name}' is already enabled.")
        else:
            tab.add(f"Plugin '{plugin_name}' is not installed or not disabled.")
        return

    try:
        os.rename(disabled_path, enabled_path)
        tab.add(f"Plugin '{plugin_name}' enabled successfully.")
        tab.add("Please restart Poly to load the plugin.")
    except OSError as e:
        tab.add(f"Error: Could not enable plugin. {e}")

def ppm_disable(tab, plugin_name):
    """Disables an installed plugin."""
    if not plugin_name:
        tab.add("Usage: ppm disable <plugin_name>")
        return

    enabled_path, disabled_path = _get_plugin_paths(plugin_name)

    if not os.path.exists(enabled_path):
        if os.path.exists(disabled_path):
            tab.add(f"Plugin '{plugin_name}' is already disabled.")
        else:
            tab.add(f"Plugin '{plugin_name}' is not installed.")
        return

    try:
        os.rename(enabled_path, disabled_path)
        tab.add(f"Plugin '{plugin_name}' disabled successfully.")
        tab.add("Please restart Poly for the change to take effect.")
    except OSError as e:
        tab.add(f"Error: Could not disable plugin. {e}")

def ppm_doctor(tab):
    """Checks for potential issues with the PPM setup."""
    tab.add("--- Running PPM Doctor ---")
    issues_found = 0

    plugins_dir = get_plugins_dir()
    tab.add(f"Checking plugin directory: {plugins_dir}")
    if not os.path.exists(plugins_dir):
        tab.add("  [OK] Directory does not exist yet, but will be created on install.")
    elif not os.access(plugins_dir, os.W_OK):
        tab.add(f"  [FAIL] Plugin directory is not writable.")
        issues_found += 1
    else:
        tab.add("  [OK] Plugin directory is writable.")

    tab.add("Checking remote manifest...")
    manifest = fetch_manifest(tab)
    if manifest is None:
        tab.add("  [FAIL] Could not fetch the remote plugin manifest.")
        issues_found += 1
    else:
        tab.add("  [OK] Remote manifest is reachable and valid.")

    if manifest:
        tab.add("Verifying installed plugins...")
        remote_plugins = manifest.get("plugins", {})
        if not os.path.exists(plugins_dir):
            tab.add("  No plugins installed, skipping verification.")
        else:
            for fname in os.listdir(plugins_dir):
                if not fname.endswith(".py"):
                    continue

                plugin_name = os.path.splitext(fname)[0]
                plugin_path = os.path.join(plugins_dir, fname)

                if plugin_name not in remote_plugins:
                    tab.add(f"  [WARN] Plugin '{plugin_name}' is orphaned (not in remote manifest).")
                    issues_found += 1
                    continue
                
                expected_hash = remote_plugins[plugin_name].get("sha256")
                try:
                    with open(plugin_path, 'rb') as f:
                        content = f.read()
                    actual_hash = hashlib.sha256(content).hexdigest()

                    if actual_hash != expected_hash:
                        tab.add(f"  [FAIL] Hash mismatch for '{plugin_name}'. It may be corrupted.")
                        issues_found += 1
                    else:
                        tab.add(f"  [OK] Hash verified for '{plugin_name}'.")
                except IOError as e:
                    tab.add(f"  [FAIL] Could not read file '{fname}': {e}")
                    issues_found += 1

    tab.add("--- Doctor complete ---")
    if issues_found == 0:
        tab.add("No issues found. Your PPM setup looks healthy!")
    else:
        tab.add(f"Found {issues_found} issue(s). Please review the log above.")

def ppm_command(tab, args, rest):
    """
    Main handler for the 'ppm' command.
    """
    parts = rest.split()
    if not parts:
        ppm_help(tab)
        return

    subcommand = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None

    aliases = {
        "i": "install",
        "un": "uninstall",
        "up": "update",
        "ls": "list"
    }
    subcommand = aliases.get(subcommand, subcommand)
    
    if subcommand == "help":
        ppm_help(tab)
    elif subcommand == "install":
        ppm_install(tab, arg)
    elif subcommand == "uninstall":
        ppm_uninstall(tab, arg)
    elif subcommand == "list":
        installed_only = arg == "-i"
        ppm_list(tab, installed_only)
    elif subcommand == "search":
        ppm_search(tab, arg)
    elif subcommand == "update":
        ppm_update(tab, arg)
    elif subcommand == "info":
        ppm_info(tab, arg)
    elif subcommand == "enable":
        ppm_enable(tab, arg)
    elif subcommand == "disable":
        ppm_disable(tab, arg)
    elif subcommand == "doctor":
        ppm_doctor(tab)
    else:
        tab.add(f"Unknown command: {subcommand}")
        ppm_help(tab)




def register_plugin(app_context):
    """
    Registers the 'ppm' command.
    """
    define_command = app_context["define_command"]
    define_command("ppm", ppm_command, [])

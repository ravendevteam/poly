"""
    Written by lilaf
    Last updated: June 29, 2025
    Better web requests for Poly. 

    This plugin is free software and may be copied and used in any way.
"""
import urllib

def validate_url(url):
    if url.startswith("http") and "://" in url and "." in url:
        return True
    return False

def validateurlcmd(args, rest):
    tab = args[0]
    if not rest:
        tab.add("validateurl needs arguments!")
        return

    if validate_url(rest):
        tab.add(f"{rest} is a valid URL")
    else:
        tab.add(f"{rest} is not a valid URL")

def getrequest(args, rest):
    tab = args[0]
    if not rest:
        tab.add("getrequest needs arguments!")
        return
    
    if not validate_url(rest):
        tab.add(f"{rest} is not a valid URL")
        return

    try:
        request = urllib.request.urlopen(rest)
    except Exception as e:
        tab.add(f"Request failed with error: {e}")
        return
    
    tab.add(request.read())

def register_plugin(app_context):
    tab = app_context["tab"]
    define_command = app_context["define_command"]
    define_alias = app_context["define_alias"]

    define_command("getrequest", getrequest, [tab])
    define_command("validateurl", validateurlcmd, [tab])

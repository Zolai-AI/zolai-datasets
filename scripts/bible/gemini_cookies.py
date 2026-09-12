"""Shared Gemini cookie helper — extracts Chrome cookies for gemini-webapi.
All Gemini scripts import this instead of GeminiClient() directly.
"""

import browser_cookie3

_cached_psid = None
_cached_psidts = None


def get_gemini_cookies():
    """Extract __Secure-1PSID and __Secure-1PSIDTS from Chrome."""
    global _cached_psid, _cached_psidts
    
    if _cached_psid:
        return _cached_psid, _cached_psidts
    
    cj = browser_cookie3.chrome(domain_name=".google.com")
    cookies = {c.name: c.value for c in cj}
    
    _cached_psid = cookies.get('__Secure-1PSID', '')
    _cached_psidts = cookies.get('__Secure-1PSIDTS', '')
    
    if not _cached_psid:
        raise RuntimeError(
            "Chrome cookies not found! Make sure:\n"
            "1. Chrome is installed and you're logged into Google\n"
            "2. No Chrome process is locking the DB (close Chrome or use --incognito)\n"
            "3. browser-cookie3 is installed: pip install browser-cookie3"
        )
    
    return _cached_psid, _cached_psidts


def get_gemini_client():
    """Create a properly-authenticated GeminiClient."""
    import sys
    sys.path.insert(0, '/home/peter/Documents/Project/pcore/pcore-webai/packages/gemini-webapi')
    from gemini_webapi import GeminiClient
    
    psid, psidts = get_gemini_cookies()
    return GeminiClient(secure_1psid=psid, secure_1psidts=psidts)

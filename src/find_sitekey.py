"""
CAPTCHA Sitekey Finder

Finds reCAPTCHA and hCaptcha sitekeys on any webpage.
Has two modes:
  - Static: fast HTTP fetch, works for most sites
  - Browser: real browser, handles JS-loaded captchas

Author: Devesh
License: MIT
"""

import re
import sys
import time

import requests


# regex patterns for finding sitekeys
PATTERNS = {
    "v3": [
        r'render["\']?\s*[:=]\s*["\']([0-9A-Za-z_-]{40})["\']',
        r'recaptcha/api\.js\?render=([0-9A-Za-z_-]{40})',
        r'grecaptcha\.execute\s*\(\s*["\']([0-9A-Za-z_-]{40})["\']',
    ],
    "v2": [
        r'data-sitekey\s*=\s*["\']([0-9A-Za-z_-]{40})["\']',
        r'sitekey["\']?\s*[:=]\s*["\']([0-9A-Za-z_-]{40})["\']',
    ],
    "enterprise": [
        r'recaptcha/enterprise\.js\?render=([0-9A-Za-z_-]{40})',
        r'enterprise\.execute\s*\(\s*["\']([0-9A-Za-z_-]{40})["\']',
    ],
    "hcaptcha": [
        r'data-sitekey\s*=\s*["\']([0-9a-f-]{36})["\']',
        r'hcaptcha\.com.*sitekey=([0-9a-f-]{36})',
    ],
}


def find_static(url: str) -> dict:
    """
    Find sitekeys using a simple HTTP request.
    Fast but won't work if the captcha is loaded via JS.
    """
    print(f"[*] Fetching: {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        html = resp.text
    except Exception as e:
        return {"error": str(e)}

    return _extract_keys(html, url)


def find_browser(url: str) -> dict:
    """
    Find sitekeys using a real browser.
    Slower but handles dynamically loaded captchas.
    """
    # import here so it's optional
    from playwright.sync_api import sync_playwright

    print(f"[*] Loading in browser: {url}")

    results = {
        "url": url,
        "v2": [],
        "v3": [],
        "enterprise": [],
        "hcaptcha": [],
        "other": [],
    }

    network_keys = []

    def on_request(request):
        req_url = request.url
        if "recaptcha" in req_url.lower():
            if "render=" in req_url:
                match = re.search(r'render=([0-9A-Za-z_-]{40})', req_url)
                if match:
                    network_keys.append(("v3", match.group(1)))
            if "k=" in req_url:
                match = re.search(r'k=([0-9A-Za-z_-]{40})', req_url)
                if match:
                    network_keys.append(("v2", match.group(1)))
        if "hcaptcha" in req_url.lower() and "sitekey=" in req_url:
            match = re.search(r'sitekey=([0-9a-f-]{36})', req_url)
            if match:
                network_keys.append(("hcaptcha", match.group(1)))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", on_request)

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception:
            print("[*] Page load timeout, continuing...")

        print("[*] Waiting for dynamic content...")
        time.sleep(3)

        # get content after JS execution
        html = page.content()

        # also check script tags and iframes
        scripts = page.evaluate("""
            () => {
                const scripts = document.querySelectorAll('script');
                return Array.from(scripts).map(s => s.src + ' ' + s.innerHTML).join('\\n');
            }
        """)

        iframes = page.evaluate("""
            () => {
                const iframes = document.querySelectorAll('iframe');
                return Array.from(iframes).map(f => f.src).join('\\n');
            }
        """)

        combined = html + "\n" + scripts + "\n" + iframes

        # extract from page content
        results = _extract_keys(combined, url)

        # add keys found in network requests
        for key_type, key in network_keys:
            if key not in results.get(key_type, []):
                results[key_type].append(key)

        # check for other captcha types
        if "funcaptcha" in combined.lower() or "arkoselabs" in combined.lower():
            results["other"].append("FunCaptcha")
        if "geetest" in combined.lower():
            results["other"].append("GeeTest")
        if "turnstile" in combined.lower():
            results["other"].append("Cloudflare Turnstile")

        print("[*] Close browser window when done...")
        input("Press Enter to continue...")

        browser.close()

    return results


def _extract_keys(content: str, url: str) -> dict:
    """Extract sitekeys from content using regex patterns."""
    results = {
        "url": url,
        "v2": [],
        "v3": [],
        "enterprise": [],
        "hcaptcha": [],
        "other": [],
    }

    for pattern in PATTERNS["v3"]:
        for match in re.findall(pattern, content, re.IGNORECASE):
            if match not in results["v3"] and match not in results["v2"]:
                results["v3"].append(match)

    for pattern in PATTERNS["v2"]:
        for match in re.findall(pattern, content, re.IGNORECASE):
            if match not in results["v2"] and match not in results["v3"]:
                results["v2"].append(match)

    for pattern in PATTERNS["enterprise"]:
        for match in re.findall(pattern, content, re.IGNORECASE):
            if match not in results["enterprise"]:
                results["enterprise"].append(match)

    for pattern in PATTERNS["hcaptcha"]:
        for match in re.findall(pattern, content, re.IGNORECASE):
            if match not in results["hcaptcha"]:
                results["hcaptcha"].append(match)

    # detection flags
    results["recaptcha_detected"] = "recaptcha" in content.lower()
    results["hcaptcha_detected"] = "hcaptcha" in content.lower()

    return results


def print_results(results: dict):
    """Pretty print the results."""
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    if "error" in results:
        print(f"Error: {results['error']}")
        return

    found_any = False

    if results.get("v3"):
        found_any = True
        print(f"\nreCAPTCHA v3: {len(results['v3'])} found")
        for key in results["v3"]:
            print(f"  {key}")

    if results.get("v2"):
        found_any = True
        print(f"\nreCAPTCHA v2: {len(results['v2'])} found")
        for key in results["v2"]:
            print(f"  {key}")

    if results.get("enterprise"):
        found_any = True
        print(f"\nreCAPTCHA Enterprise: {len(results['enterprise'])} found")
        for key in results["enterprise"]:
            print(f"  {key}")

    if results.get("hcaptcha"):
        found_any = True
        print(f"\nhCaptcha: {len(results['hcaptcha'])} found")
        for key in results["hcaptcha"]:
            print(f"  {key}")

    if results.get("other"):
        found_any = True
        print(f"\nOther CAPTCHAs detected:")
        for name in results["other"]:
            print(f"  - {name}")

    if not found_any:
        if results.get("recaptcha_detected"):
            print("\nreCAPTCHA detected but sitekey not found.")
            print("Try using --browser mode or check network tab in devtools.")
        elif results.get("hcaptcha_detected"):
            print("\nhCaptcha detected but sitekey not found.")
        else:
            print("\nNo CAPTCHA detected on this page.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python find_sitekey.py <url> [--browser]")
        print()
        print("Examples:")
        print("  python find_sitekey.py https://example.com/login")
        print("  python find_sitekey.py https://example.com/login --browser")
        sys.exit(1)

    url = sys.argv[1]
    if not url.startswith("http"):
        url = "https://" + url

    use_browser = "--browser" in sys.argv

    if use_browser:
        results = find_browser(url)
    else:
        results = find_static(url)

    print_results(results)


if __name__ == "__main__":
    main()

"""
reCAPTCHA v2 Audio Solver

Solves v2 captchas by using the accessibility audio challenge.
The audio gets transcribed with Whisper - works surprisingly well
since Whisper handles distorted/noisy speech really good.

Author: Devesh
License: MIT
"""

import os
import time
import tempfile

import requests
from playwright.sync_api import sync_playwright
from faster_whisper import WhisperModel


class RecaptchaV2Solver:
    """
    Solves reCAPTCHA v2 using audio challenge + Whisper speech-to-text.

    The trick here is that Google has to provide audio challenges for
    accessibility reasons, and modern speech-to-text is good enough
    to transcribe them accurately.
    """

    def __init__(self, model_size: str = "base"):
        """
        Initialize solver with Whisper model.

        Args:
            model_size: Whisper model to use
                - "tiny"    : fastest, ~1s load, ok accuracy
                - "base"    : balanced, ~2s load, good accuracy (recommended)
                - "small"   : slower, ~3s load, better accuracy
                - "medium"  : slow, ~5s load, great accuracy
                - "large-v3": slowest, best accuracy (overkill for this)
        """
        print(f"[*] Loading Whisper model: {model_size}")

        # using CPU with int8 quantization - no GPU needed and still fast
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

        print("[+] Model ready")

    def solve(self, url: str, max_retries: int = 3) -> dict:
        """
        Solve reCAPTCHA v2 on the given page.

        Args:
            url: Page URL containing the captcha
            max_retries: How many times to retry if solving fails

        Returns:
            dict with:
                - success: bool
                - token: str (if successful)
                - error: str (if failed)
        """
        with sync_playwright() as p:
            # non-headless because some sites detect headless browsers
            browser = p.chromium.launch(headless=False)

            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/121.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            try:
                return self._solve(page, url, max_retries)
            finally:
                browser.close()

    def _solve(self, page, url: str, max_retries: int) -> dict:
        """Core solving logic."""
        page.goto(url)
        page.wait_for_load_state("networkidle")
        print(f"[*] Loaded: {url}")

        # find and click the recaptcha checkbox
        recaptcha_frame = page.frame_locator("iframe[src*='recaptcha']").first
        checkbox = recaptcha_frame.locator("#recaptcha-anchor")
        checkbox.click()
        print("[*] Clicked checkbox")

        time.sleep(2)

        # sometimes it just passes without a challenge (lucky!)
        try:
            checkmark = recaptcha_frame.locator(".recaptcha-checkbox-checked")
            if checkmark.is_visible(timeout=2000):
                print("[+] Passed without challenge")
                return self._get_token(page)
        except Exception:
            pass

        # challenge appeared, let's solve it
        for attempt in range(max_retries):
            print(f"[*] Attempt {attempt + 1}/{max_retries}")

            try:
                result = self._solve_audio(page)
                if result["success"]:
                    return result
                print(f"[-] Failed: {result.get('error', 'unknown')}")
            except Exception as e:
                print(f"[-] Error: {e}")

            time.sleep(1)

        return {"success": False, "error": "max retries exceeded"}

    def _solve_audio(self, page) -> dict:
        """Handle the audio challenge."""
        # challenge is in a different iframe
        challenge_frame = page.frame_locator("iframe[src*='bframe']").first

        # click audio button to switch from image to audio challenge
        audio_btn = challenge_frame.locator("#recaptcha-audio-button")
        audio_btn.click(timeout=5000)
        print("[*] Switched to audio")

        time.sleep(2)

        # check if we're being rate limited
        try:
            error_el = challenge_frame.locator(".rc-audiochallenge-error-message")
            if error_el.is_visible(timeout=1000):
                error_text = error_el.text_content()
                if error_text:
                    return {"success": False, "error": f"rate limited: {error_text}"}
        except Exception:
            pass

        # get the audio download link
        download_link = challenge_frame.locator(".rc-audiochallenge-tdownload-link")
        audio_url = download_link.get_attribute("href", timeout=5000)

        if not audio_url:
            return {"success": False, "error": "couldn't find audio url"}

        print(f"[*] Audio URL: {audio_url[:60]}...")

        # download and transcribe
        text = self._transcribe(audio_url)
        if not text:
            return {"success": False, "error": "transcription failed"}

        print(f"[*] Transcribed: {text}")

        # submit the answer
        answer_box = challenge_frame.locator("#audio-response")
        answer_box.fill(text)

        verify_btn = challenge_frame.locator("#recaptcha-verify-button")
        verify_btn.click()

        time.sleep(2)

        # check if it worked
        try:
            recaptcha_frame = page.frame_locator("iframe[src*='recaptcha']").first
            checkmark = recaptcha_frame.locator(".recaptcha-checkbox-checked")
            if checkmark.is_visible(timeout=3000):
                print("[+] SOLVED!")
                return self._get_token(page)
        except Exception:
            pass

        return {"success": False, "error": "verification failed"}

    def _transcribe(self, audio_url: str) -> str:
        """Download audio and transcribe with Whisper."""
        try:
            # download the mp3
            resp = requests.get(audio_url, timeout=10)
            resp.raise_for_status()

            # whisper needs a file path, so save to temp
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(resp.content)
                temp_path = f.name

            print(f"[*] Downloaded: {len(resp.content)} bytes")

            # transcribe - beam_size=5 helps with distorted audio
            segments, _ = self.model.transcribe(
                temp_path,
                language="en",
                beam_size=5
            )

            text = " ".join(seg.text for seg in segments)

            # cleanup temp file
            os.unlink(temp_path)

            # clean the text - recaptcha expects lowercase, no punctuation
            text = text.strip()
            text = "".join(c for c in text if c.isalnum() or c.isspace())
            text = " ".join(text.split())

            return text.lower()

        except Exception as e:
            print(f"[-] Transcription error: {e}")
            return ""

    def _get_token(self, page) -> dict:
        """Extract the recaptcha response token from the page."""
        try:
            token = page.evaluate(
                "document.getElementById('g-recaptcha-response').value"
            )
            return {
                "success": True,
                "token": token
            }
        except Exception:
            return {"success": True, "token": None}


# quick test
if __name__ == "__main__":
    demo_url = "https://www.google.com/recaptcha/api2/demo"

    print("=" * 50)
    print("reCAPTCHA v2 Solver Test")
    print("=" * 50)
    print()

    solver = RecaptchaV2Solver(model_size="base")
    result = solver.solve(demo_url)

    print()
    print("=" * 50)
    if result["success"]:
        print(f"[+] Success! Token: {result['token'][:50]}...")
    else:
        print(f"[-] Failed: {result.get('error')}")
    print("=" * 50)

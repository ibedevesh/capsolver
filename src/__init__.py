"""
Capsolver - Local CAPTCHA solving for AI agents

Solves reCAPTCHA v2 locally using audio challenge + Whisper.
"""

from .recaptcha_v2 import RecaptchaV2Solver

__version__ = "1.0.0"
__all__ = ["RecaptchaV2Solver"]

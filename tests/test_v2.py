"""
Test reCAPTCHA v2 solver against Google's demo page.
"""

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0] + "/src")

from recaptcha_v2 import RecaptchaV2Solver


def main():
    demo_url = "https://www.google.com/recaptcha/api2/demo"

    print("=" * 60)
    print("reCAPTCHA v2 Solver Test")
    print("=" * 60)
    print()
    print(f"Target: {demo_url}")
    print()

    solver = RecaptchaV2Solver(model_size="base")
    result = solver.solve(demo_url)

    print()
    print("=" * 60)

    if result["success"]:
        token = result.get("token", "")
        print(f"SUCCESS!")
        print(f"Token: {token[:60]}..." if token else "Token: (empty)")
    else:
        print(f"FAILED: {result.get('error', 'unknown')}")

    print("=" * 60)

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())

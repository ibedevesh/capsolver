"""
Example: Solving reCAPTCHA v2

This shows how to use the v2 solver to solve a captcha
and get the response token.
"""

import sys
sys.path.insert(0, str(__file__).rsplit("/", 2)[0] + "/src")

from recaptcha_v2 import RecaptchaV2Solver


def main():
    # the URL with the captcha you want to solve
    url = "https://www.google.com/recaptcha/api2/demo"

    # create solver - "base" model is a good default
    # use "small" or "medium" for better accuracy
    solver = RecaptchaV2Solver(model_size="base")

    # solve it
    result = solver.solve(url)

    if result["success"]:
        token = result["token"]
        print(f"Got token: {token[:50]}...")

        # now you can use this token to submit the form
        # the token goes in the g-recaptcha-response field
    else:
        print(f"Failed: {result['error']}")


if __name__ == "__main__":
    main()

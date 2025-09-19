import random
from django.core.cache import cache

def generate_unique_otp(length=6):
    """
    Generates a random OTP that is not currently in the cache.
    """
    while True:
        code = ''.join([str(random.randint(0, 9)) for _ in range(length)])
        # Check if this code is already used as a key
        if not cache.get(f"code_{code}"):
            return code

from slowapi import Limiter
from slowapi.util import get_remote_address

# This tells the limiter to track users by their IP address
limiter = Limiter(key_func=get_remote_address)

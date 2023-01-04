import os
import string
import random

def randstring(length: int=12) -> str:
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def datafile(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), 'data', filename)

def filesize(path: str) -> int:
    return os.stat(path).st_size

import os

shorten_url = os.getenv('SHORTEN_URL')

hesh_chars = '02356789bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ-_'
BASE = len(hesh_chars)

def b64ish(i: int) -> str:
    b64 = ''
    while i > 0:
        r = i % BASE
        i = i // BASE
        b64 += hesh_chars[r]
    return ''.join(b64)

def shorten(i: int):
    return f'{shorten_url}/{b64ish(i)}'
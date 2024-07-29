import os
import urllib.parse

impact_base_url = os.getenv('TCGCSV_IMPACT_AFFILIATE_BASE_URL')

hesh_chars = '02356789bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ-_'
BASE = len(hesh_chars)

def unb64ish(s: str) -> int:
    r = 0
    pwr = 0
    for c in s:
        r += hesh_chars.index(c) * BASE ** pwr
        pwr += 1
    return r

def generate_impact_affiliate_link(url='https://www.tcgplayer.com'):
    return f'{impact_base_url}?u={urllib.parse.quote(url, safe="")}'

def lambda_handler(event, context):
    if event.get('path') == '/':
        return {
            'statusCode': 302,
            'headers': {
                'Location': generate_impact_affiliate_link()
            }
        }

    b64 = event['pathParameters']['shortCode']
    if len(b64) > 10:
        return {'statusCode': 404}

    try:
        tcgplayer_id = unb64ish(b64)
    except ValueError:
        return {'statusCode': 404}

    return {
        'statusCode': 302,
        'headers': {
            'Location': generate_impact_affiliate_link(f'https://www.tcgplayer.com/product/{tcgplayer_id}'),
            'X-Robots-Tag': 'noindex',
        }
     }

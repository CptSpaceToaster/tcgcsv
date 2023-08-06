import os

affiliate_code = os.getenv('AFFILIATE_CODE')

hesh_chars = '02356789bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ-_'
BASE = len(hesh_chars)

def unb64ish(s: str) -> int:
    r = 0
    pwr = 0
    for c in s:
        r += hesh_chars.index(c) * BASE ** pwr
        pwr += 1
    return r

def lambda_handler(event, context):
    if event.get('path') == '/':
        return {
            'statusCode': 302,
            'headers': {
                'Location': f'https://www.tcgplayer.com?utm_campaign=affiliate&utm_source={affiliate_code}&utm_medium=tcgcsv'
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
            'Location': f'https://www.tcgplayer.com/product/{tcgplayer_id}?utm_campaign=affiliate&utm_source={affiliate_code}&utm_medium=tcgcsv'
        }
     }
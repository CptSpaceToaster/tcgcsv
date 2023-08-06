import requests

try:
    from .exceptions import TCGPlayerSDKException
except ImportError:
    from exceptions import TCGPlayerSDKException


TCGPLAYER_BASE_URL = 'https://api.tcgplayer.com'
TCGPLAYER_API_VERSION = 'v1.39.0'
TCGPLAYER_API_URL = f'{TCGPLAYER_BASE_URL}/{TCGPLAYER_API_VERSION}'

class TCGPlayerSDK():
    def __init__(
        self,
        public_key: str,
        private_key: str,
    ):
        self.public_key = public_key
        self.private_key = private_key

        self._identity = None
        self._token = None

    @property
    def token(self):
        if self._token is None:
            r = requests.post(
                f'{TCGPLAYER_API_URL}/token',
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self.public_key,
                    'client_secret': self.private_key,
                },
            )
            self._identity = r.json()
            self._token = f'{self._identity["token_type"]} {self._identity["access_token"]}'
        return self._token

    def _get_all_pages(self, path: str, extra_params={}):
        res = None
        offset = 0
        limit = 100

        while True:
            r = requests.get(
                path,
                params={
                    **extra_params,
                    'offset': offset,
                    'limit': 100,
                },
                headers={'Authorization': self.token},
            )

            parsed = r.json()
            if r.status_code != 200:
                # 404 WITH CONTENT IS NOT OK
                if parsed['errors'] == ['No products were found.']:
                    parsed = {
                        "success": True,
                        "errors": [],
                        "results": [],
                        "totalItems": 0
                    }
                else:
                    raise TCGPlayerSDKException(r)

            if res is None:
                res = parsed
            else:
                res['results'].extend(parsed['results'])

            offset += limit
            if len(res['results']) >= res['totalItems']:
                break

        return res

    def get_categories(self, sort_order='categoryId', sort_desc=False):
        return self._get_all_pages(
            f'{TCGPLAYER_API_URL}/catalog/categories',
            extra_params={
                'sortOrder': sort_order,
                'sortDesc': sort_desc,
            }
        )
    
    def get_groups(self, category_id, sort_order='publishedOn', sort_desc=True):
        return self._get_all_pages(
            f'{TCGPLAYER_API_URL}/catalog/categories/{category_id}/groups',
            extra_params={
                'sortOrder': sort_order,
                'sortDesc': sort_desc,
            }
        )
    
    def get_products_for_group(self, group_id, sort_order='name', sort_desc=False, get_extended_fields=True):
        return self._get_all_pages(
            f'{TCGPLAYER_API_URL}/catalog/products',
            extra_params={
                'groupId': group_id,
                'sortOrder': sort_order,
                'sortDesc': sort_desc,
                'getExtendedFields': get_extended_fields,
            }
        )
    
    def get_prices_for_group(self, group_id):
        r = requests.get(
            f'{TCGPLAYER_API_URL}/pricing/group/{group_id}',
            headers={'Authorization': self.token},
        )
        response = r.json()
        if r.status_code != 200:
            # 404 WITH CONTENT IS (still) NOT OK
            if response['errors'] == ['No products were found.']:
                response = {
                    "success": True,
                    "errors": [],
                    "results": [],
                }
            else:
                raise TCGPlayerSDKException(r)

        return response
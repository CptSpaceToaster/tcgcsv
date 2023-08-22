import os
import time

import asyncio
import aiohttp
from aiohttp_s3_client import S3Client

# https://blog.jonlu.ca/posts/async-python-http

# Hacks to run locally if needed for testing
try:
    from .tcgplayersdk import TCGPlayerSDK
    from .csv_utils import write_json, write_csv
    from .shorten import shorten
except ImportError:
    from tcgplayersdk import TCGPlayerSDK
    from csv_utils import write_json, write_csv
    from shorten import shorten

def flattenExtendedData(product):
    # This modifies the results dictionary in-place
    if 'extendedData' in product:
        extendedData = product.pop('extendedData', None)
        for extendedDataItem in extendedData:
            product[f'ext{extendedDataItem["name"].replace(" ", "")}'] = extendedDataItem["value"]


def injectPricesIntoProducts(product, prices):
    matching_prices = [price for price in prices if product['productId'] == price['productId']]
    if len(matching_prices) > 0:
        # TODO: If len(matching_prices) ever yields anything other than 1... we should probably log.
        product.update(matching_prices[0])


def overwriteURL(product):
    if 'url' in product:
        product['url'] = shorten(product['productId'])


async def main(bucket_name, public_key, private_key):
    start = time.time()

    MAX_CONCURRENCY = 100

    conn = aiohttp.TCPConnector(limit_per_host=MAX_CONCURRENCY, limit=0, ttl_dns_cache=300)
    session = aiohttp.ClientSession(connector=conn)

    # Initialize s3
    s3_client = S3Client(
        url=f"https://{bucket_name}.s3.us-east-1.amazonaws.com",
        session=session,
        access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        session_token=os.getenv('AWS_SESSION_TOKEN'),

    )

    # Initialize TCGPlayerSDK
    tcgplayer = TCGPlayerSDK(session, public_key, private_key)

    # Generate content
    categories_response = await tcgplayer.get_categories()
    await write_json(s3_client, 'categories', categories_response)
    categories = categories_response['results']
    await write_csv(s3_client, 'categories.csv', categories[0].keys(), categories)

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    category_group_pairs = []

    async def process_category(category):
        category_name = category['name']
        category_id = category['categoryId']
        safe_category_name = category_name.replace('&', 'And').replace(' ', '')
        async with semaphore:
            groups_response = await tcgplayer.get_groups(category_id)
            await write_json(s3_client, f'{category_id}/groups', groups_response)

            groups = groups_response['results']
            category_group_pairs.extend([(category_id, group) for group in groups])

            if len(groups) == 0: # Apparently there is a category without any groups
                return
            await write_csv(s3_client, f'{category_id}/{safe_category_name}Groups.csv', groups[0].keys(), groups)

    # TODO: Is there any way I can start the second process without blocking here like before with threads?
    await asyncio.gather(*(process_category(category) for category in reversed(categories)))

    async def process_group(category_id, group):
        if category_id not in [1, 2, 3, 16, 62]:
            return

        group_id = group['groupId']
        safe_group_name = group['name'].replace('&', 'And').replace(' ', '').replace(':', '').replace('.', '').replace('/', '-')
        async with semaphore:
            products_response = await tcgplayer.get_products_for_group(group_id)
            await write_json(s3_client, f'{category_id}/{group_id}/products', products_response)
            prices_response = await tcgplayer.get_prices_for_group(group_id)
            await write_json(s3_client, f'{category_id}/{group_id}/prices', prices_response)

            products = products_response['results']
            prices = prices_response['results']

            fieldnames = []
            for product in products:
                overwriteURL(product)
                injectPricesIntoProducts(product, prices)
                flattenExtendedData(product)

                # Filter out any keys
                for key in ['presaleInfo']:
                    product.pop(key, None)

                # This is probably inefficient, but it should preserve some order in the CSV
                # TODO: Profile this
                for key in product.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)

            await write_csv(s3_client, f'{category_id}/{group_id}/{safe_group_name}ProductsAndPrices.csv', fieldnames, products)

    await asyncio.gather(*(process_group(*cgp) for cgp in category_group_pairs))

    await session.close()

    delta = time.time() - start

    return {
        'statusCode': 200,
        'data': f'{int(delta // 60)} minutes, {int(delta % 60)} seconds'
    }


def lambda_handler(event, context):
    # Env vars
    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    public_key = os.getenv('TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TCGPLAYER_PRIVATE_KEY')

    response = asyncio.run(
        main(bucket_name, public_key, private_key)
    )

    return response


if __name__ == '__main__':
    os.environ['AWS_SHARED_CREDENTIALS_FILE'] = f'{os.path.expanduser("~")}/.aws/personal_credentials'

    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    public_key = os.getenv('TF_VAR_TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TF_VAR_TCGPLAYER_PRIVATE_KEY')

    response = asyncio.run(
        main(bucket_name, public_key, private_key)
    )

    with open('local.txt', 'w') as f:
        f.write(str(response['data']))

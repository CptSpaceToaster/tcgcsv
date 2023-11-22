import os
import time
import copy
from merkle_json import MerkleJson

import asyncio
import aiohttp
from aiohttp_s3_client import S3Client
import boto3

# https://blog.jonlu.ca/posts/async-python-http

# Hacks to run locally if needed for testing
try:
    from .tcgplayersdk import TCGPlayerSDK
    from .csv_utils import write_json, write_csv, write_txt, read_json
    from .shorten import shorten
except ImportError:
    from tcgplayersdk import TCGPlayerSDK
    from csv_utils import write_json, write_csv, write_txt, read_json
    from shorten import shorten


def flattenExtendedData(product):
    # This modifies the results dictionary in-place
    if 'extendedData' in product:
        extended_data = product.pop('extendedData', None)
        for extended_data_item in extended_data:
            product[f'ext{extended_data_item["name"].replace(" ", "")}'] = extended_data_item["value"]


def overwriteURL(product):
    if 'url' in product:
        product['url'] = shorten(product['productId'])


async def main(bucket_name, public_key, private_key, distribution_id):
    start = time.time()

    written_file_pairs = []
    total_requests = 0

    tcgplayer_manifest_filename = '/tcgplayer-manifest.txt'

    MAX_CONCURRENCY = 400

    cf = boto3.client('cloudfront')

    mj = MerkleJson()

    conn = aiohttp.TCPConnector(limit_per_host=MAX_CONCURRENCY, limit=0, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=conn) as session:
        # Initialize s3
        s3_client = S3Client(
            url=f"https://{bucket_name}.s3.us-east-1.amazonaws.com",
            session=session,
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN'),
        )

        # Collect manifest

        manifest = await read_json(s3_client, tcgplayer_manifest_filename)
        if manifest is None:
            manifest = {}

        # TODO: Verify if I can just call list.append() in an asyncio loop, or if I should be gathering results
        written_file_pairs = []

        # Initialize TCGPlayerSDK
        tcgplayer = TCGPlayerSDK(session, public_key, private_key)

        # Generate content
        total_requests += 1
        categories_response = await tcgplayer.get_categories()
        categories_json_filename = '/categories'
        categories_csv_filename = '/categories.csv'
        categories_hash = mj.hash(categories_response)
        categories = categories_response['results']

        if categories_hash != manifest.get(categories_json_filename):
            manifest[categories_json_filename] = categories_hash

            await write_json(s3_client, categories_json_filename, categories_response)
            written_file_pairs.append(categories_json_filename)

            await write_csv(s3_client, categories_csv_filename, categories[0].keys(), categories)
            written_file_pairs.append(categories_csv_filename)

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        category_group_pairs = []

        async def process_category(category):
            category_name = category['name']
            category_id = category['categoryId']

            if category_id in [21]: # Ignore the duplicate (and empty) "My Little Pony" group all-together
                return

            safe_category_name = category_name.replace('&', 'And').replace(' ', '')
            async with semaphore:
                groups_response = await tcgplayer.get_groups(category_id)
                groups_json_filename = f'/{category_id}/groups'
                groups_csv_filename = f'/{category_id}/{safe_category_name}Groups.csv'
                groups_hash = mj.hash(groups_response)
                groups = groups_response['results']

                if category_id not in [69, 70]: # Marvel & DC Comics seem to ONLY have empty product lists... and filtering them here saves a bundle of time and energy
                    category_group_pairs.extend([(category_id, group) for group in groups])

                if len(groups) == 0: # Apparently categories can exist without groups (rarely)
                    return

                if groups_hash != manifest.get(groups_json_filename):
                    manifest[groups_json_filename] = groups_hash

                    await write_json(s3_client, groups_json_filename, groups_response)
                    written_file_pairs.append(groups_json_filename)

                    await write_csv(s3_client, groups_csv_filename, groups[0].keys(), groups)
                    written_file_pairs.append(groups_csv_filename)

        # TODO: Is there any way I can start the second process without blocking here like before with threads?
        await asyncio.gather(*(
            asyncio.ensure_future(
                process_category(category)
            ) for category in reversed(categories)
        ))

        total_requests += len(categories)

        async def process_group(category_id, group):
            group_id = group['groupId']

            safe_group_name = group['name'].replace('&', 'And').replace(' ', '').replace(':', '').replace('.', '').replace('/', '-')
            async with semaphore:
                products_response = await tcgplayer.get_products_for_group(group_id)
                prices_response = await tcgplayer.get_prices_for_group(group_id)
                products_json_filename = f'/{category_id}/{group_id}/products'
                prices_json_filename = f'/{category_id}/{group_id}/prices'
                products_and_prices_csv_filename = f'/{category_id}/{group_id}/{safe_group_name}ProductsAndPrices.csv'
                products_hash = mj.hash(products_response)
                prices_hash = mj.hash(prices_response)

                if products_hash != manifest.get(products_json_filename):
                    manifest[products_json_filename] = products_hash

                    await write_json(s3_client, products_json_filename, products_response)
                    written_file_pairs.append(products_json_filename)

                if prices_hash != manifest.get(prices_json_filename):
                    manifest[prices_json_filename] = prices_hash

                    await write_json(s3_client, prices_json_filename, prices_response)
                    written_file_pairs.append(prices_json_filename)

                if products_hash != manifest.get(products_json_filename) or prices_hash != manifest.get(prices_json_filename):
                    products = products_response['results']
                    prices = prices_response['results']

                    products_to_write = []
                    fieldnames = []
                    for product in products:
                        overwriteURL(product)
                        flattenExtendedData(product)

                        # Filter out any keys
                        for key in ['presaleInfo']:
                            product.pop(key, None)

                        # duplicate rows if there are multiple prices
                        matching_prices = [price for price in prices if product['productId'] == price['productId']]
                        if len(matching_prices) > 0:
                            for price in matching_prices:
                                product.update(price)
                                # write a deep copy
                                products_to_write.append(copy.deepcopy(product))
                        else:
                            products_to_write.append(product)

                        # This is probably inefficient, but it should preserve some order in the CSV
                        # TODO: Profile this
                        for key in product.keys():
                            if key not in fieldnames:
                                fieldnames.append(key)

                    await write_csv(s3_client, products_and_prices_csv_filename, fieldnames, products_to_write)
                    written_file_pairs.append(products_and_prices_csv_filename)

        await asyncio.gather(*(
            asyncio.ensure_future(
                process_group(*cgp)
            ) for cgp in category_group_pairs
        ))

        total_requests += len(category_group_pairs) * 2

        await write_json(s3_client, tcgplayer_manifest_filename, manifest)
        written_file_pairs.append(tcgplayer_manifest_filename)

        await write_txt(s3_client, '/last-updated.txt', time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime()))
        written_file_pairs.append('/last-updated.txt')

    delta = time.time() - start

    cf.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': len(written_file_pairs),
                'Items': written_file_pairs,
            },
            'CallerReference': str(time.time()).replace(".", "")
        }
    )

    return {
        'statusCode': 200,
        'data': f'{{"total_requests": {total_requests}, "files_written": {len(written_file_pairs)}, "time_elapsed": "{int(delta // 60)} minutes, {int(delta % 60)} seconds"}}'
    }


def lambda_handler(event, context):
    # Env vars
    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    public_key = os.getenv('TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TCGPLAYER_PRIVATE_KEY')
    distribution_id = os.getenv('TCGCSV_DISTRIBUTION_ID')

    response = asyncio.run(
        main(bucket_name, public_key, private_key, distribution_id)
    )

    return response


if __name__ == '__main__':
    os.environ['AWS_SHARED_CREDENTIALS_FILE'] = f'{os.path.expanduser("~")}/.aws/personal_credentials'

    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    public_key = os.getenv('TF_VAR_TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TF_VAR_TCGPLAYER_PRIVATE_KEY')
    distribution_id = os.getenv('TCGCSV_DISTRIBUTION_ID')

    response = asyncio.run(
        main(bucket_name, public_key, private_key, distribution_id)
    )

    with open('local.txt', 'w') as f:
        f.write(str(response['data']))

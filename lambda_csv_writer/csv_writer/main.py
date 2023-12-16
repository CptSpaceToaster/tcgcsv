import os
import time
import copy
import json

from http import HTTPStatus
from itertools import groupby

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


async def main(bucket_name, public_key, private_key, distribution_id, discord_webhook):
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

        written_file_pairs = []
        new_files = []
        seen_files = []

        def establish_file_state(filename):
            if manifest.get(filename) is None:
                new_files.append(filename)
            else:
                seen_files.append(filename)

        # Initialize TCGPlayerSDK
        tcgplayer = TCGPlayerSDK(session, public_key, private_key)

        # Generate content
        total_requests += 1
        categories_response = await tcgplayer.get_categories()
        categories_json_filename = '/categories'
        categories_csv_filename = '/Categories.csv'
        categories_hash = mj.hash(categories_response)
        categories = categories_response['results']

        establish_file_state(categories_json_filename)
        if categories_hash != manifest.get(categories_json_filename):
            manifest[categories_json_filename] = categories_hash

            await write_json(s3_client, categories_json_filename, categories_response)
            written_file_pairs.append(categories_json_filename)

            await write_csv(s3_client, categories_csv_filename, categories[0].keys(), categories, 'Categories.csv')
            written_file_pairs.append(categories_csv_filename)

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        category_group_pairs = []

        async def process_category(category):
            category_id = category['categoryId']

            if category_id in [21]: # Ignore the duplicate (and empty) "My Little Pony" group all-together
                return

            async with semaphore:
                groups_response = await tcgplayer.get_groups(category_id)
                groups_json_filename = f'/{category_id}/groups'
                groups_csv_filename = f'/{category_id}/Groups.csv'
                groups_hash = mj.hash(groups_response)
                groups = groups_response['results']
                suggested_csv_name = f"{category['name'].replace('&', 'And').replace(' ', '')}Groups.csv"

                if category_id not in [69, 70]: # Marvel & DC Comics seem to ONLY have empty product lists... and filtering them here saves a bundle of time and energy
                    category_group_pairs.extend([(category_id, group) for group in groups])

                if len(groups) == 0: # Apparently categories can exist without groups (rarely)
                    return

                establish_file_state(groups_json_filename)
                if groups_hash != manifest.get(groups_json_filename):
                    manifest[groups_json_filename] = groups_hash

                    await write_json(s3_client, groups_json_filename, groups_response)
                    written_file_pairs.append(groups_json_filename)

                    await write_csv(s3_client, groups_csv_filename, groups[0].keys(), groups, suggested_csv_name)
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

            async with semaphore:
                products_response = await tcgplayer.get_products_for_group(group_id)
                prices_response = await tcgplayer.get_prices_for_group(group_id)
                products_json_filename = f'/{category_id}/{group_id}/products'
                prices_json_filename = f'/{category_id}/{group_id}/prices'
                products_and_prices_csv_filename = f'/{category_id}/{group_id}/ProductsAndPrices.csv'
                products_hash = mj.hash(products_response)
                prices_hash = mj.hash(prices_response)
                suggested_csv_name = f"{group['name'].replace('&', 'And').replace(' ', '').replace(':', '').replace('.', '').replace('/', '-')}ProductsAndPrices.csv"

                establish_file_state(products_json_filename)
                establish_file_state(prices_json_filename)
                if products_hash != manifest.get(products_json_filename) or prices_hash != manifest.get(prices_json_filename):
                    if products_hash != manifest.get(products_json_filename):
                        manifest[products_json_filename] = products_hash

                        await write_json(s3_client, products_json_filename, products_response)
                        written_file_pairs.append(products_json_filename)

                    if prices_hash != manifest.get(prices_json_filename):
                        manifest[prices_json_filename] = prices_hash

                        await write_json(s3_client, prices_json_filename, prices_response)
                        written_file_pairs.append(prices_json_filename)
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

                    await write_csv(s3_client, products_and_prices_csv_filename, fieldnames, products_to_write, suggested_csv_name)
                    written_file_pairs.append(products_and_prices_csv_filename)

        await asyncio.gather(*(
            asyncio.ensure_future(
                process_group(*cgp)
            ) for cgp in category_group_pairs
        ))

        total_requests += len(category_group_pairs) * 2

        # Post changes to discord
        removed_files = [filename for filename in manifest if filename not in seen_files and filename not in new_files]

        if len(new_files) or len(removed_files):
            embeds = []
            if len(removed_files):
                print(f"{len(removed_files)} removed files")
                print(json.dumps(removed_files))
                embeds.append({
                    "title": "Removed Files",
                    "color": 16711680,
                    "description": '\n'.join(removed_files)[:4095]
                })
            if len(new_files):
                print(f"{len(new_files)} new files")
                print(json.dumps(new_files))
                embeds.append({
                    "title": "Added Files",
                    "color": 65280,
                    "description": '\n'.join(new_files)[:4095]
                })

            await session.post(discord_webhook, json={"embeds": embeds})

            # Remove files from manifest and bucket
            removed_files.sort()
            for group, items in groupby(removed_files, lambda x: "/".join(x.split("/", 3)[:3])):
                for item in items:
                    del manifest[item]
                    async with s3_client.delete(item) as resp:
                        assert resp == HTTPStatus.NO_CONTENT
                async with s3_client.delete(f'{group}/ProductsAndPrices.csv') as resp:
                    assert resp == HTTPStatus.NO_CONTENT

        await write_json(s3_client, tcgplayer_manifest_filename, manifest)
        written_file_pairs.append(tcgplayer_manifest_filename)

        await write_txt(s3_client, '/last-updated.txt', time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime()))
        written_file_pairs.append('/last-updated.txt')

    delta = time.time() - start

    cf.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*'],
            },
            'CallerReference': str(time.time()).replace(".", "")
        }
    )

    status = json.dumps({
        "total_requests": total_requests,
        "files_written": len(written_file_pairs),
        "time_elapsed": f"{int(delta // 60)} minutes, {int(delta % 60)} seconds"}
    )
    print(status)

    return {
        'statusCode': 200,
        'data': status
    }


def lambda_handler(event, context):
    # Env vars
    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    public_key = os.getenv('TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TCGPLAYER_PRIVATE_KEY')
    distribution_id = os.getenv('TCGCSV_DISTRIBUTION_ID')
    discord_webhook = os.getenv('TCGCSV_DISCORD_WEBHOOK')

    response = asyncio.run(
        main(bucket_name, public_key, private_key, distribution_id, discord_webhook)
    )

    return response


if __name__ == '__main__':
    os.environ['AWS_SHARED_CREDENTIALS_FILE'] = f'{os.path.expanduser("~")}/.aws/personal_credentials'

    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    public_key = os.getenv('TF_VAR_TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TF_VAR_TCGPLAYER_PRIVATE_KEY')
    distribution_id = os.getenv('TCGCSV_DISTRIBUTION_ID')
    discord_webhook = os.getenv('TF_VAR_TCGCSV_DISCORD_WEBHOOK')

    response = asyncio.run(
        main(bucket_name, public_key, private_key, distribution_id, discord_webhook)
    )

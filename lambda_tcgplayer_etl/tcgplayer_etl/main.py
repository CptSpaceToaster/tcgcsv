import os
import time
import copy
import json
import io
import pprint

from http import HTTPStatus
from itertools import groupby

from merkle_json import MerkleJson
import asyncio
import aiohttp
from aiohttp_s3_client import S3Client
import boto3
import py7zr

# https://blog.jonlu.ca/posts/async-python-http

# Hacks to run locally if needed for testing
try:
    from .tcgplayersdk import TCGPlayerSDK
    from .csv_utils import write_json, write_csv, write_txt, read_json, write_buffered_bytes
    from .shorten import shorten
except ImportError:
    from tcgplayersdk import TCGPlayerSDK
    from csv_utils import write_json, write_csv, write_txt, read_json, write_buffered_bytes
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


async def main(bucket_name, tcgplayer_vault_bucket_name, frontend_bucket_name, archive_bucket_name, public_key, private_key, distribution_id, discord_webhook, dry_run=True):
    start = time.time()

    written_file_pairs = []
    total_requests = 0

    tcgplayer_manifest_filename = '/tcgplayer/manifest.txt'

    MAX_CONCURRENCY = 60

    cf = boto3.client('cloudfront')

    mj = MerkleJson()

    conn = aiohttp.TCPConnector(limit_per_host=MAX_CONCURRENCY, limit=0, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=conn) as session:
        # Initialize s3
        s3_client = None if dry_run else S3Client(
            url=f"https://{bucket_name}.s3.us-east-1.amazonaws.com",
            session=session,
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN'),
        )

        tcgplayer_vault_s3_client = None if dry_run else S3Client(
            url=f"https://{tcgplayer_vault_bucket_name}.s3.us-east-1.amazonaws.com",
            session=session,
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN'),
        )

        frontend_s3_client = None if dry_run else S3Client(
            url=f"https://{frontend_bucket_name}.s3.us-east-1.amazonaws.com",
            session=session,
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN'),
        )

        archive_s3_client = None if dry_run else S3Client(
            url=f"https://{archive_bucket_name}.s3.us-east-1.amazonaws.com",
            session=session,
            access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            session_token=os.getenv('AWS_SESSION_TOKEN'),
        )

        archive7z_buffer = io.BytesIO()
        ppmd_filters = [{"id": py7zr.FILTER_PPMD, 'order': 8, 'mem': 24}]
        archive7z = py7zr.SevenZipFile(archive7z_buffer, 'w', filters=ppmd_filters)

        # Collect manifest
        manifest = None if dry_run else await read_json(tcgplayer_vault_s3_client, tcgplayer_manifest_filename)
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

            if dry_run:
                print('Established Categories')
                pprint.pp(categories_response)
            else:
                await write_json(s3_client, categories_json_filename, categories_response)
                await write_json(tcgplayer_vault_s3_client, '/tcgplayer' + categories_json_filename, categories_response)
                written_file_pairs.append(categories_json_filename)

                await write_csv(s3_client, categories_csv_filename, categories[0].keys(), categories, 'Categories.csv')
                await write_csv(tcgplayer_vault_s3_client, '/tcgplayer' + categories_csv_filename, categories[0].keys(), categories, 'Categories.csv')
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

                if dry_run and category_id not in [77]:
                    return

                if category_id not in [69, 70]: # Marvel & DC Comics seem to ONLY have empty product lists... and filtering them here saves a bundle of time and energy
                    category_group_pairs.extend([(category_id, group) for group in groups])

                establish_file_state(groups_json_filename)
                if groups_hash != manifest.get(groups_json_filename):
                    manifest[groups_json_filename] = groups_hash

                    if dry_run:
                        print(f'{category_id} Established Groups')
                        pprint.pp(groups_response)
                    else:
                        await write_json(s3_client, groups_json_filename, groups_response)
                        await write_json(tcgplayer_vault_s3_client, '/tcgplayer' + groups_json_filename, groups_response)
                        written_file_pairs.append(groups_json_filename)

                        keys = [] if len(groups) == 0 else groups[0].keys()
                        await write_csv(s3_client, groups_csv_filename, keys, groups, suggested_csv_name)
                        await write_csv(tcgplayer_vault_s3_client, '/tcgplayer' + groups_csv_filename, keys, groups, suggested_csv_name)
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
                prices_json_archive_filename = f'{time.strftime("%Y-%m-%d", time.localtime())}/{category_id}/{group_id}/prices'
                products_and_prices_csv_filename = f'/{category_id}/{group_id}/ProductsAndPrices.csv'
                products_hash = mj.hash(products_response)
                prices_hash = mj.hash(prices_response)
                suggested_csv_name = f"{group['name'].replace('&', 'And').replace(' ', '').replace(':', '').replace('.', '').replace('/', '-')}ProductsAndPrices.csv"

                establish_file_state(products_json_filename)
                establish_file_state(prices_json_filename)

                # Always include price in archive
                with io.BytesIO(json.dumps(prices_response).encode('utf-8')) as buffer:
                    archive7z.writef(buffer, prices_json_archive_filename)

                if products_hash != manifest.get(products_json_filename) or prices_hash != manifest.get(prices_json_filename):
                    if products_hash != manifest.get(products_json_filename):
                        manifest[products_json_filename] = products_hash

                        if dry_run:
                            print(f'{category_id}/{group_id} Established Products')
                            # pprint.pp(products_response)
                        else:
                            await write_json(s3_client, products_json_filename, products_response)
                            await write_json(tcgplayer_vault_s3_client, '/tcgplayer' + products_json_filename, products_response)
                            written_file_pairs.append(products_json_filename)

                    if prices_hash != manifest.get(prices_json_filename):
                        manifest[prices_json_filename] = prices_hash

                        if dry_run:
                            print(f'{category_id}/{group_id} Established Prices')
                            # pprint.pp(prices_response)
                        else:
                            await write_json(s3_client, prices_json_filename, prices_response)
                            await write_json(tcgplayer_vault_s3_client, '/tcgplayer' + prices_json_filename, prices_response)
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

                    if dry_run:
                        print(f'{category_id}/{group_id} Established Products and Prices')
                        # pprint.pp(products_to_write)
                    else:
                        await write_csv(s3_client, products_and_prices_csv_filename, fieldnames, products_to_write, suggested_csv_name)
                        await write_csv(tcgplayer_vault_s3_client, '/tcgplayer' + products_and_prices_csv_filename, fieldnames, products_to_write, suggested_csv_name)
                        written_file_pairs.append(products_and_prices_csv_filename)

        await asyncio.gather(*(
            asyncio.ensure_future(
                process_group(*cgp)
            ) for cgp in category_group_pairs
        ))

        total_requests += len(category_group_pairs) * 2


        # Write price archive
        archive7z.close()
        price_archive_name = time.strftime('prices-%Y-%m-%d.ppmd.7z', time.localtime())
        archive7z_buffer.seek(0)
        if dry_run:
            print('Established 7z archive')
        else:
            await write_buffered_bytes(
                archive_s3_client,
                archive7z_buffer,
                f'/archive/{price_archive_name}',
                price_archive_name,
            )
            # TODO: When removing the block below, this seek(0) also needs to go.
            archive7z_buffer.seek(0)
            await write_buffered_bytes(
                archive_s3_client,
                archive7z_buffer,
                f'archive/tcgplayer/{price_archive_name}',
                price_archive_name,
            )
        archive7z_buffer.close()

        # Post changes to discord
        removed_files = [filename for filename in manifest if filename not in seen_files and filename not in new_files]

        if not dry_run:
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
            had_trouble_deleting = {}
            removed_files.sort()
            for group, items in groupby(removed_files, lambda x: "/".join(x.split("/", 3)[:3])):
                for item in items:
                    async with tcgplayer_vault_s3_client.delete('/tcgplayer' + item) as resp:
                        if resp.status != HTTPStatus.NO_CONTENT:
                            # had_trouble_deleting.append[item] = resp.status
                            pass
                        else:
                            # del manifest[item]
                            pass

                    async with s3_client.delete(item) as resp:
                        if resp.status != HTTPStatus.NO_CONTENT:
                            had_trouble_deleting.append[item] = resp.status
                        else:
                            del manifest[item]

                async with tcgplayer_vault_s3_client.delete(f'/tcgplayer{group}/ProductsAndPrices.csv') as resp:
                    if resp.status != HTTPStatus.NO_CONTENT:
                        # had_trouble_deleting.append[f'/tcgplayer{group}/ProductsAndPrices.csv'] = resp.status
                        pass
                async with s3_client.delete(f'{group}/ProductsAndPrices.csv') as resp:
                    if resp.status != HTTPStatus.NO_CONTENT:
                        had_trouble_deleting.append[f'{group}/ProductsAndPrices.csv'] = resp.status

            print(f"Had trouble deleting {len(had_trouble_deleting)} files:")
            print(json.dumps(had_trouble_deleting))

        timestamp = time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime())
        if dry_run:
            print('Established manifest')
            print(f'Established last-updated.txt {timestamp}')
        else:
            await write_json(tcgplayer_vault_s3_client, tcgplayer_manifest_filename, manifest)
            written_file_pairs.append(tcgplayer_manifest_filename)

            await write_txt(frontend_s3_client, '/last-updated.txt', timestamp)
            await write_txt(s3_client, '/last-updated.txt', timestamp)
            written_file_pairs.append('/last-updated.txt')

    delta = time.time() - start

    if not dry_run:
        # cf.create_invalidation(
        #     DistributionId=distribution_id,
        #     InvalidationBatch={
        #         'Paths': {
        #             'Quantity': 1,
        #             'Items': ['/tcgplayer/*', '/last-updated.txt'],
        #         },
        #         'CallerReference': str(time.time()).replace(".", "")
        #     }
        # )
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
    tcgplayer_vault_bucket_name = os.getenv('TCGCSV_TCGPLAYER_VAULT_BUCKET_NAME')
    frontend_bucket_name = os.getenv('TCGCSV_FRONTEND_BUCKET_NAME')
    archive_bucket_name = os.getenv('TCGCSV_ARCHIVE_BUCKET_NAME')
    public_key = os.getenv('TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TCGPLAYER_PRIVATE_KEY')
    distribution_id = os.getenv('TCGCSV_DISTRIBUTION_ID')
    discord_webhook = os.getenv('TCGCSV_DISCORD_WEBHOOK')

    response = asyncio.run(
        main(bucket_name, tcgplayer_vault_bucket_name, frontend_bucket_name, archive_bucket_name, public_key, private_key, distribution_id, discord_webhook, dry_run=False)
    )

    return response


if __name__ == '__main__':
    os.environ['AWS_SHARED_CREDENTIALS_FILE'] = f'{os.path.expanduser("~")}/.aws/personal_credentials'

    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    tcgplayer_vault_bucket_name = os.getenv('TCGCSV_TCGPLAYER_VAULT_BUCKET_NAME')
    frontend_bucket_name = os.getenv('TCGCSV_FRONTEND_BUCKET_NAME')
    archive_bucket_name = os.getenv('TCGCSV_ARCHIVE_BUCKET_NAME')
    public_key = os.getenv('TF_VAR_TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TF_VAR_TCGPLAYER_PRIVATE_KEY')
    distribution_id = os.getenv('TCGCSV_DISTRIBUTION_ID')
    discord_webhook = os.getenv('TF_VAR_TCGCSV_DISCORD_WEBHOOK')

    response = asyncio.run(
        main(bucket_name, tcgplayer_vault_bucket_name, frontend_bucket_name, archive_bucket_name, public_key, private_key, distribution_id, discord_webhook, dry_run=True)
    )

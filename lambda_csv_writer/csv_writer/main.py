import os
import time
from concurrent.futures import ThreadPoolExecutor, wait

# Hacks to run locally if needed for testing
try:
    from .tcgplayersdk import TCGPlayerSDK
    from .csv import write_json, write_csv
    from .index import write_index
    from .shorten import shorten
except ImportError:
    from tcgplayersdk import TCGPlayerSDK
    write_json = lambda *args: None
    write_csv = lambda *args: None
    write_index = lambda *args: None
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


def process_group(group_id, safe_group_name, bucket_name, category_id, tcgplayer):
    products_response = tcgplayer.get_products_for_group(group_id)
    write_json(bucket_name, f'{category_id}/{group_id}/products', products_response)

    prices_response = tcgplayer.get_prices_for_group(group_id)
    write_json(bucket_name, f'{category_id}/{group_id}/prices', prices_response)

    products = products_response['results']
    prices = prices_response['results']

    fieldnames = []
    for product in products:
        overwriteURL(product)
        injectPricesIntoProducts(product, prices)
        flattenExtendedData(product)

        # Filter out keys
        for key in ['presaleInfo']:
            product.pop(key, None)

        # This is probably inefficient, but it should preserve some order in the CSV
        # TODO: Profile this
        for key in product.keys():
            if key not in fieldnames:
                fieldnames.append(key)
        
    write_csv(bucket_name, f'{category_id}/{group_id}/{safe_group_name}ProductsAndPrices.csv', fieldnames, products)


def process_category(category_name, category_id, safe_category_name, bucket_name, tcgplayer, written_data, executor):
    # if category['name'] != 'Flesh & Blood TCG':
        #     continue

    groups_response = tcgplayer.get_groups(category_id)
    write_json(bucket_name, f'{category_id}/groups', groups_response)

    groups = groups_response['results']
    if len(groups) == 0: # Apparently there is a category without any groups
        return

    write_csv(bucket_name, f'{category_id}/{safe_category_name}Groups.csv', groups[0].keys(), groups)

    if category_name not in ['Magic', 'YuGiOh', 'Pokemon', 'Flesh & Blood TCG']:
        return

    for group in groups:
        group_id = group['groupId']
        safe_group_name = group['name'].replace('&', 'And').replace(' ', '').replace(':', '').replace('.', '')

        # Apparently you can nest these
        executor.submit(
            process_group, 
            group_id, 
            safe_group_name, 
            bucket_name, 
            category_id, 
            tcgplayer,
        )

        # assume the data will be written I guess?!?
        written_data[category_id]['groups'][group_id] = {
            'name': group['name'],
            'products_json': f'{category_id}/{group_id}/products',
            'prices_json': f'{category_id}/{group_id}/prices',
            'combined_csv': f'{category_id}/{group_id}/{safe_group_name}ProductsAndPrices.csv',
        }


def lambda_handler(event, context):
    # Env vars
    bucket_name = os.getenv('BUCKET_NAME')
    public_key = os.getenv('TCGPLAYER_PUBLIC_KEY')
    private_key = os.getenv('TCGPLAYER_PRIVATE_KEY')

    return main(bucket_name, public_key, private_key)


def main(bucket_name, public_key, private_key):
    start = time.time()
    
    written_data = {}

    # Initialize TCGPlayerSDK
    tcgplayer = TCGPlayerSDK(public_key, private_key)

    # Generate content
    categories_response = tcgplayer.get_categories()
    write_json(bucket_name, 'categories', categories_response)

    categories = categories_response['results']
    write_csv(bucket_name, 'categories.csv', categories[0].keys(), categories)

    futures = []

    # Oh dear x16
    executor = ThreadPoolExecutor(max_workers=16)
    for category in categories:
        category_name = category['name']
        category_id = category['categoryId']
        safe_category_name = category_name.replace('&', 'And').replace(' ', '')

        written_data[category_id] = {
            'name': category_name,
            'groups_json': f'{category_id}/groups',
            'groups_csv': f'{category_id}/{safe_category_name}Groups.csv',
            'groups': {},
        }

        f = executor.submit(
            process_category, 
            category_name, 
            category_id, 
            safe_category_name, 
            bucket_name, 
            tcgplayer, 
            written_data, 
            executor,
        )

        if f is not None:
            futures.append(f)

    wait(futures)
    executor.shutdown(wait=True)

    write_index(bucket_name, written_data)

    delta = time.time() - start

    count = 0
    for category in written_data.values():
        count += len(category['groups']) + 1

    return {
        'statusCode': 200,
        'data': f'{int(delta // 60)} minutes, {int(delta % 60)} seconds {count} {written_data}'
    }

if __name__ == '__main__':
    response = main('', os.getenv('TF_VAR_TCGPLAYER_PUBLIC_KEY'), os.getenv('TF_VAR_TCGPLAYER_PRIVATE_KEY'))
    with open('local.txt', 'w') as f:
        f.write(str(response['data']))
import os
import json
import time
from collections import OrderedDict

import boto3
# TODO: Remove smart_open, and use aiohttp_s3_client
import smart_open


template_start = '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta property="og:title" content="TCGCSV"/>
    <meta property="og:type" content="website"/>
    <meta property="og:url" content="http://tcgcsv.com"/>
    <meta property="og:description" content="TCGPlayer category, group, and product information updated daily"/>
    <meta name="theme-color" content="#663399">
    <title>TCGCSV</title>
    <link rel="manifest" href="/manifest.webmanifest">
    <link rel="icon" href="/favicon.ico" sizes="32x32">
    <link rel="icon" href="/icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@700&display=swap">
    <style>
      body { color: Black; background-color: White; }
      .content-grid { display: grid; grid-template-columns: 1fr 1fr; align-items: center; margin-bottom: 12px; }
      .links { margin-bottom: 2px; }
      .e { background-color: #EEE; }
      .z { color: #AAA; }
      .u { color: Black; }
      .c { color: DarkSeaGreen; font-style: italic; }
      a:visited, .s { color: #639; }
      header { margin-right: 16px; display: grid; align-items: center; column-gap: 24px; grid-template-columns: 1fr min-content min-content min-content; }
      header a img { height: 40px; }
      summary { font-size: 24px; margin-bottom: 4px; border-bottom: 1px solid #000; }
      summary, h1, h3 { font-family: 'Roboto Slab', serif; }
      code div { overflow: auto; max-width: 720px; border: solid gray; border-width: 2px 2px 2px 12px; padding:.2em .6em; line-height: 1.25em;}
      @media (prefers-color-scheme: dark) {
        .e { background-color: #333; }
        .z { color: #666; }
        .u { color: White; }
        body { color: White; background-color: #222; }
        a { color: SkyBlue; }
        a:visited, .s { color: #a7d; }
        summary { border-bottom: 1px solid #555; }
      }
      @media (max-width: 576px) {
        .content-grid { grid-template-columns: 1fr; }
        header { grid-template-rows: min-content min-content; grid-template-columns: min-content min-content 1fr; }
        header *:first-child { grid-column: span 3; }
      }
    </style>
  </head>
  <body>
    <header>
      <h1>TCGPlayer CSV & JSON&nbsp;Dumps</h1>
      <a target="_blank" rel="noopener noreferrer" href="https://github.com/CptSpaceToaster/tcgcsv"><img alt="Github Repo" src="/github-mark.svg"></a>
      <a target="_blank" rel="noopener noreferrer" href="https://discord.gg/bydv2BNV25"><img alt="Join Discord" src="/discord-mark.svg"></a>
      <a target="_blank" rel="noopener noreferrer" href="https://cpt.tcgcsv.com"><img alt="TCGPlayer Affiliate Link" src="/TCGplayer-logo-primary.png"></a>
    </header>
    <section>
      <h3>Ahoy There!</h3>
      <p>I'm CptSpaceToaster! This website is a personal project of mine that exposes categories, groups, products, and prices from TCGPlayer's API. The results are shared here for folks who can't get access to TCGPlayer's API. All responses used to generate the content on this website are cached as unmodified JSON text-files. The CSV's that I've put together DO have my personal affiliate links in there.</p>
      <p>
        All content <i>should</i> update daily at ~4pm EST (20:00:00 UTC).<br>
        <div class="updated-at">Last updated at: </div>
        <embed type="text/plain" src="last-updated.txt" height="44" style="color-scheme:light dark;">
      </p>
      <p>You can see my terraform learnings, AWS infrastructure, and open source mess for this website on <a target="_blank" rel="noopener noreferrer" href="https://github.com/CptSpaceToaster/tcgcsv">Github</a></p>
      <p>You can join this <a target="_blank" rel="noopener noreferrer" href="">discord</a> to contact me, get updates, and talk about what would be cool to have next!</p>
      <p>If you would like to support this project, please consider using my <a href="https://cpt.tcgcsv.com">affiliate link</a> to help keep the lights on</p>
    </section>
    <section>
    <p>Q. Can I scrape this website?<br>
    A. If the premade CSVs aren't quite what you need then go ahead! I would recommend processing the cached JSON files with any requests library.</p>
    <pre><code><div><b>import</b> requests

pokemon_category = <span class="s">&#39;3&#39;</span>

r = requests.get(f<span class="s">&quot;https://tcgcsv.com/<span class="u">{pokemon_category}</span>/groups&quot;</span>)
all_groups = r.json()[<span class="s">&#39;results&#39;</span>]

<b>for</b> group <b>in</b> all_groups:
    group_id = group[<span class="s">&#39;groupId&#39;</span>]
    r = requests.get(f<span class="s">&quot;https://tcgcsv.com/<span class="u">{pokemon_category}</span>/<span class="u">{group_id}</span>/products&quot;</span>)
    products = r.json()[<span class="s">&#39;results&#39;</span>]

    <b>for</b> product <b>in</b> products:
        <span class="c"># Process product information</span>
        <b>print</b>(f<span class="s">&quot;<span class="u">{product[</span>&#39;productId&#39;<span class="u">]}</span> - <span class="u">{product[</span>&#39;name&#39;<span class="u">]}</span>&quot;</span>)

    r = requests.get(f<span class="s">&quot;https://tcgcsv.com/<span class="u">{pokemon_category}</span>/<span class="u">{group_id}</span>/prices&quot;</span>)
    prices = r.json()[<span class="s">&#39;results&#39;</span>]

    <b>for</b> price <b>in</b> prices:
        <span class="c"># Process prices</span>
        <b>print</b>(f<span class="s">&quot;<span class="u">{price[</span>&#39;productId&#39;<span class="u">]}</span> - <span class="u">{price[</span>&#39;subTypeName&#39;<span class="u">]}</span> - <span class="u">{price[</span>&#39;midPrice&#39;<span class="u">]}</span>&quot;</span>)

    <b>break</b> <span class="c"># Only process the first group and break for testing</span>

</div></code></pre>
    </section>
    <main>
    <br>
'''

template_end = '''    </main>
  </body>
  <footer>
    <p>With special thanks to our friends:</p>
    <ul>
      <li>luceleaftea for maintaining a separate pile of CSVs on <a target="_blank" rel="noopener noreferrer" href="https://github.com/the-fab-cube/flesh-and-blood-cards">Github</a> for Flesh and Blood</li>
      <li>nago for hosting a wonderful pile of pokemon related assets over at <a target="_blank" rel="noopener noreferrer" href="https://malie.io/static/">Malie.io</a></li>
      <li>ZeldaZach for helping answer questions in TCGPlayer's discord with me, while also maintaining <a target="_blank" rel="noopener noreferrer" href="https://mtgjson.com">MTGJSON.com</a></li>
      <li>And viewers like you!</li>
    </ul>
  </footer>
</html>
'''

def write_index(bucket_name, shorten_domain, written_data, content_type='text/html'):
    params = {'client_kwargs': {'S3.Client.create_multipart_upload': {'ContentType': content_type}}}
    with smart_open.open(f's3://{bucket_name}/index.html', 'w', transport_params=params) as fout:
        write_content_in_descriptor(fout, shorten_domain, written_data)


def write_content_in_descriptor(fout, shorten_domain, written_data):
    fout.write(template_start)
    fout.write(f'      <div class="content-grid">\n')
    fout.write(f'        <span>All Categories</span>\n')
    fout.write(f'        <div class="links">\n')
    fout.write(f'          <a target="_blank" rel="noopener noreferrer" href="categories">Categories</a>\n')
    fout.write(f'          <a href="categories.csv">Categories.csv</a>\n')
    fout.write(f'        </div>\n')
    fout.write(f'      </div>\n')

    for category_id, category in written_data['categories'].items():
        category_name = [c for c in written_data['categories_results'] if c['categoryId'] == category_id][0]['name']

        fout.write(f'      <details>\n')

        group_count = len(category["groups"])
        class_param = ' class="z"' if group_count == 0 else ''

        fout.write(f'        <summary{class_param}>{category_name} ({group_count})</summary>\n')
        fout.write(f'        <div class="content-grid">\n')
        fout.write(f'          <span>Groups</span>\n')
        fout.write(f'          <div class="links">\n')
        fout.write(f'            <a target="_blank" rel="noopener noreferrer" href="{category["groups_json"]}">Groups</a>\n')
        fout.write(f'            <a href="{category["groups_csv"]}">Groups.csv</a>\n')
        fout.write(f'          </div>\n')

        even = True
        for group_id, group in category['groups'].items():
            group_name = [g for g in category['groups_results'] if g['groupId'] == group_id][0]['name']

            class_param = ' class="e"' if even else ''
            class_add = ' e' if even else ''

            fout.write(f'          <span{class_param}>{group_name}</span>\n')
            fout.write(f'          <div class="links{class_add}">\n')
            fout.write(f'            <a target="_blank" rel="noopener noreferrer" href="{group["products_json"]}">Products</a>\n')
            fout.write(f'            <a target="_blank" rel="noopener noreferrer" href="{group["prices_json"]}">Prices</a>\n')
            fout.write(f'            <a href="{group["combined_csv"]}">ProductsAndPrices.csv</a>\n')
            fout.write(f'          </div>\n')
            even = not even
        fout.write(f'        </div>\n')
        fout.write(f'      </details>\n')
    fout.write(template_end)


def get_all_objects_in_bucket(s3, bucket_name):
    res = None
    continuation_token = None

    while True:
        if continuation_token is None:
            r = s3.list_objects_v2(Bucket=bucket_name)
        else:
            r = s3.list_objects_v2(Bucket=bucket_name, ContinuationToken=continuation_token)

        if res is None:
            res = r
        else:
            res['Contents'].extend(r['Contents'])

        continuation_token = r.get('NextContinuationToken')
        if continuation_token is None:
            break

    return res


def process_objects(objs, bucket_name):
    written_data = {
        'categories_csv': '',
        'categories_json': '',
        'categories': {},
        'categories_results': [],
    }

    ignored_files = [
        'apple-touch-icon.png',
        'discord-mark.svg',
        'favicon.ico',
        'github-mark.svg',
        'icon-192.png',
        'icon-512.png',
        'icon.svg',
        'index.html',
        'last-updated.txt',
        'manifest.webmanifest',
        'TCGplayer-logo-primary.png',
    ]

    for obj in objs:
        name = obj['Key']
        if name in ignored_files:
            continue

        base = os.path.basename(name)
        category_and_group = os.path.dirname(name)

        # TODO: This whole dictionary walking mess can likely be replaced if I walk my own JSON output directly
        if category_and_group == '':
            if base.endswith('.csv'):
                written_data['categories_csv'] = base
            else:
                written_data['categories_json'] = base
                for json_line in smart_open.open(f's3://{bucket_name}/{base}', 'r'):
                    written_data['categories_results'] = json.loads(json_line)['results']
        else:
            group_or_category = int(os.path.basename(category_and_group))
            category = os.path.dirname(category_and_group)
            if category == '':
                # Ensure the category structure exist...
                cat = written_data['categories'].get(group_or_category, {
                    'groups_json': '',
                    'groups_csv': '',
                    'groups': {},
                    'groups_results': [],
                })
                written_data['categories'][group_or_category] = cat

                if base.endswith('.csv'):
                    written_data['categories'][group_or_category]['groups_csv'] = f'{group_or_category}/{base}'
                else:
                    written_data['categories'][group_or_category]['groups_json'] = f'{group_or_category}/{base}'
                    for json_line in smart_open.open(f's3://{bucket_name}/{group_or_category}/{base}', 'r'):
                        written_data['categories'][group_or_category]['groups_results'] = json.loads(json_line)['results']
            else:
                # TODO: This default dictionary assertion stuff smells bad
                # Ensure the category and group structure exist...
                category = int(category)
                cat = written_data['categories'].get(category, {
                    'groups_json': '',
                    'groups_csv': '',
                    'groups': {},
                    'groups_results': [],
                })
                written_data['categories'][category] = cat
                group = written_data['categories'][category]['groups'].get(group_or_category, {
                    'products_json': '',
                    'prices_json': '',
                    'combined_csv': '',
                })
                written_data['categories'][category]['groups'][group_or_category] = group

                if base.startswith('products'):
                    written_data['categories'][category]['groups'][group_or_category]['products_json'] = f'{category}/{group_or_category}/{base}'
                elif base.startswith('prices'):
                    written_data['categories'][category]['groups'][group_or_category]['prices_json'] = f'{category}/{group_or_category}/{base}'
                else:
                    written_data['categories'][category]['groups'][group_or_category]['combined_csv'] = f'{category}/{group_or_category}/{base}'

    written_data['categories'] = OrderedDict(sorted(written_data['categories'].items()))
    for val in written_data['categories'].values():
        val['groups'] = OrderedDict(sorted(val['groups'].items()))

    return written_data


def lambda_handler(event, context):
    # Env vars
    bucket_name = os.getenv('TCGCSV_BUCKET_NAME')
    shorten_domain = os.getenv('TCGCSV_SHORTEN_DOMAIN')
    distribution_id = os.getenv('TCGCSV_DISTRIBUTION_ID')

    s3 = boto3.client('s3')
    cf = boto3.client('cloudfront')

    # Get all objects
    all_objects = get_all_objects_in_bucket(s3, bucket_name)

    # Process data
    written_data = process_objects(all_objects['Contents'], bucket_name)

    # Write out
    write_index(bucket_name, shorten_domain, written_data)

    cf.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/index.html',]
            },
            'CallerReference': str(time.time()).replace(".", "")
        }
    )

    return {
        'statusCode': 200,
        'data': f'{len(written_data["categories"])}'
    }


def test_website_generation_locally():
    shorten_domain = os.getenv('TCGCSV_SHORTEN_DOMAIN')

    written_data = {
        'categories_csv': 'categories.csv',
        'categories_json': 'categories',
        'categories_results': [{
            'categoryId': 1,
            'name': 'Magic',
        }, {
            'categoryId': 2,
            'name': 'YuGiOh',
        }, {
            'categoryId': 3,
            'name': 'Pokemon',
        }],
        'categories': {
            1: {
                'groups_json': '1/groups',
                'groups_csv': '1/MagicGroups.csv',
                'groups_results': [{
                    'groupId': 1,
                    'name': '10th Edition',
                }],
                'groups': {
                    1: {
                        'products_json': '1/1/products',
                        'prices_json': '1/1/prices',
                        'combined_csv': '1/1/10thEditionProductsAndPrices',
                    }
                },
            },
            2: {
                'groups_json': '2/groups',
                'groups_csv': '2/YuGiOhGroups.csv',
                'group_results': [],
                'groups': {},
            },
            3: {
                'groups_json': '3/groups',
                'groups_csv': '3/PokemonGroups.csv',
                'groups_results': [{
                    'groupId': 604,
                    'name': 'Base Set',
                }],
                'groups': {
                    604: {
                        'products_json': '3/604/products',
                        'prices_json': '3/604/prices',
                        'combined_csv': '3/604/BaseSetProductsAndPrices',
                    }
                },
            },
        },
    }

    with open('index.html', 'w') as fout:
        write_content_in_descriptor(fout, shorten_domain, written_data)

    os.system("open index.html")


if __name__ == '__main__':
    # Do it big
    # os.environ['AWS_SHARED_CREDENTIALS_FILE'] = '~/.aws/personal_credentials'
    # print(lambda_handler(None, None))

    # Do it small
    with open('last-updated.txt', 'w') as f:
        print(time.strftime('%Y-%m-%dT%H:%M:%S%z', time.localtime()), file=f)
    test_website_generation_locally()

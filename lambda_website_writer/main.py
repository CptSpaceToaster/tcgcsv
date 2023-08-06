import os
import json
from collections import OrderedDict

try:
    import boto3
    import smart_open
except ImportError:
    pass


template_start = '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>TCGPlayer CSV & JSON Dumps</title>
    <style>
      .content-grid {
        display: grid; grid-template-columns: 1fr 1fr; align-items: center; margin-bottom: 12px;
      }
      .links { margin-bottom: 2px; }
      .e { background-color: #EEE; }
      .b { border-bottom: 1px solid #000; }
      .z { color: #AAA; }
      summary { font-size: 24px; margin-bottom: 4px; border-bottom: 1px solid #000; }
      @media (prefers-color-scheme: dark) {
        body { color: White; background: #222; }
        a { color: SkyBlue; }
        a:visited { color: Plum; }
        .e { background-color: #333; }
        .z { color: #666; }
        summary { border-bottom: 1px solid #555; }
      }
      @media (max-width: 550px) {
        .content-grid { grid-template-columns: 1fr; }
        h2 { grid-column: unset; }
      }
    </style>
  </head>
  <body>
    <header>
      <h1>TCGPlayer JSON Dumps</h1>
      <p>Ahoy There! I'm CptSpaceToaster! This website is a personal project of mine that vendors some information from TCGPlayer's API into JSON and CSV text dumps. Content <i>should</i> be updated daily, but things are VERY ramshackle at the moment. I would eventually like to open source some things here, and the roadmap has a lot to do! The JSON text dumps are as raw as they can be straight from TCGPlayer. The CSV's that I've put together DO have my personal affiliate links in there.</p>
      <ol>
        <li><s>Getting a discord up and running</s></li>
        <li>Write more of a project description & <s>link the discord</s></li>
        <li>Some more web development <s>(odd/even lines in the blocks of sets)</s></li>
        <li>Threading the lambda writer</li>
        <li>Some more categories</li>
        <li>All categories</li>
      </ol>
      <p>You can join this <a href="https://discord.gg/bydv2BNV25">discord</a> for updates and contact! </p>
      <br>
    </header>
    <main>
'''

template_end = '''    </main>
  </body>
</html>
'''

def write_index(bucket_name, written_data, content_type='text/html'):
    params = {'client_kwargs': {'S3.Client.create_multipart_upload': {'ContentType': content_type}}}
    with smart_open.open(f's3://{bucket_name}/index.html', 'w', transport_params=params) as fout:
        write_content_in_descriptor(fout, written_data)


def write_content_in_descriptor(fout, written_data):
    fout.write(template_start)
    fout.write(f'      <div class="content-grid">\n')
    fout.write(f'        <span>All Categories</span>\n')
    fout.write(f'        <div class="links">\n')
    fout.write(f'          <a target="_blank" rel="noopener noreferrer" href="categories">Categories</a>\n')
    fout.write(f'          <a href="categories.csv">Categories.csv</a>\n')
    fout.write(f'        </div>\n')
    fout.write(f'      </div>\n')
    
    for category_id, category in written_data['categories'].items():
        # category_name = written_data['categories_LUT'].get(category_id, f'categoryName({category_id})')
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
            # group_name = category['groups_LUT'].get(group_id, f'groupName({group_id})')
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

    ignored_files = ['index.html']

    for obj in objs:
        name = obj['Key']
        if name in ignored_files:
            continue

        base = os.path.basename(name)
        category_and_group = os.path.dirname(name)

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
                # TODO: be better
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
                # TODO: Also be better here
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

    for key, value in written_data['categories'].items():
        print(key, value)

    return written_data


def lambda_handler(event, context):
    # Env vars
    bucket_name = os.getenv('BUCKET_NAME')
    shorten_domain = os.getenv('SHORTEN_DOMAIN')

    s3 = boto3.client('s3')

    # Get all objects
    all_objects = get_all_objects_in_bucket(s3, bucket_name)
    
    # Process data
    written_data = process_objects(all_objects['Contents'], bucket_name)
    
    # Write out
    write_index(bucket_name, written_data)
    
    return {
        'statusCode': 200,
        'data': f'{len(written_data)}'
    }
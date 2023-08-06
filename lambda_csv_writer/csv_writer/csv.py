import io
import csv
import json

try:
    import smart_open
except ImportError:
    pass

def write_json(bucket_name, filename, results, content_type='text/json'):
    params = {'client_kwargs': {'S3.Client.create_multipart_upload': {'ContentType': content_type}}}
    with smart_open.open(f's3://{bucket_name}/{filename}', 'w', transport_params=params) as fout:
        json.dump(results, fout)
    

def write_csv(bucket_name, filename, fieldnames, results, content_type='text/csv'):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    params = {'client_kwargs': {'S3.Client.create_multipart_upload': {'ContentType': content_type}}}
    with smart_open.open(f's3://{bucket_name}/{filename}', 'w', transport_params=params) as fout:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        fout.write(stream.getvalue())

        for row in results:
            stream.seek(0)
            stream.truncate(0)
            writer.writerow(row)
            fout.write(stream.getvalue())
    stream.close()
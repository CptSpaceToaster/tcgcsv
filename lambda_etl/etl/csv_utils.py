import io
import csv
import json
from typing import List

import aiohttp_s3_client


PART_SIZE = 5 * 1024 * 1024  # 5MB


async def write_json(client: aiohttp_s3_client.S3Client, filename: str, results: dict, content_type: str = 'text/json'):
    def dict_sender(results: dict, chunk_size: int):
        with io.BytesIO(json.dumps(results).encode('utf-8')) as buffer:
            while True:
                data = buffer.read(chunk_size)
                if not data:
                    break
                yield data

    running = True
    tries = 20
    while running and tries > 0:
        try:
            await client.put_multipart(
                filename,
                dict_sender(
                    results,
                    chunk_size=PART_SIZE,
                ),
                headers={
                    'Content-Type': content_type,
                    'X-Robots-Tag': 'noindex',
                },
                part_upload_tries=20,
            )
            running = False
        except aiohttp_s3_client.client.AwsUploadError as e:
            tries -= 1
            if tries == 0:
                raise e

async def write_csv(client: aiohttp_s3_client.S3Client, filename: str, fieldnames: List[str], results: dict, suggested_filename: str, content_type: str = 'text/csv'):
    def csv_sender(results: dict, fieldnames: List[str], chunk_size: int):
        with io.BytesIO() as buffer:
            # CSV writer needs to write strings. TextIOWrapper gets us back to bytes
            with io.TextIOWrapper(buffer, 'utf-8', newline='') as sb:
                writer = csv.DictWriter(sb, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

                sb.flush()
                buffer.seek(0)

                while True:
                    data = buffer.read(chunk_size)
                    if not data:
                        break
                    yield data

    running = True
    tries = 20
    while running and tries > 0:
        try:
            await client.put_multipart(
                filename,
                csv_sender(
                    results,
                    fieldnames,
                    chunk_size=PART_SIZE,
                ),
                headers={
                    'Content-Type': content_type,
                    'Content-Disposition': f'attachment; filename="{suggested_filename}"',
                    'X-Robots-Tag': 'noindex',
                },
                part_upload_tries=20,
            )
            running = False
        except aiohttp_s3_client.client.AwsUploadError as e:
            tries -= 1
            if tries == 0:
                raise e


# TODO: This pattern seems to be showing up more and more and more... I could probabyl refactor the script to handle files and in-memory buffers with less copy+paste
async def write_buffered_bytes(client: aiohttp_s3_client.S3Client,buffered_bytes: io.BytesIO, filename: str, suggested_filename: str, content_type: str = 'application/octet-stream'):
    def buf_sender(buf: io.BytesIO, chunk_size: int):
        while True:
            data = buf.read(chunk_size)
            if not data:
                break
            yield data

    running = True
    tries = 20
    while running and tries > 0:
        try:
            await client.put_multipart(
                filename,
                buf_sender(
                    buffered_bytes,
                    chunk_size=PART_SIZE,
                ),
                headers={
                    'Content-Type': content_type,
                    'Content-Disposition': f'attachment; filename="{suggested_filename}"',
                    'X-Robots-Tag': 'noindex',
                },
                part_upload_tries=20,
            )
            running = False
        except aiohttp_s3_client.client.AwsUploadError as e:
            tries -= 1
            if tries == 0:
                raise e


async def write_txt(client: aiohttp_s3_client.S3Client, filename: str, text: str, content_type: str = 'text/plain'):
    await client.put(filename, text, headers={
        'Content-Type': content_type,
        'X-Robots-Tag': 'noindex',
    })

async def read_json(client: aiohttp_s3_client.S3Client, filename: str):
    async with client.get(filename) as response:
        if response.status == 200:
            return json.loads(await response.read())
        else:
            return None

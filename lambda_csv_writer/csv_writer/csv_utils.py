import io
import csv
import json
from typing import List

from aiohttp_s3_client import S3Client


PART_SIZE = 5 * 1024 * 1024  # 5MB


async def write_json(client: S3Client, filename: str, results: str, content_type: str = 'text/json'):
    def dict_sender(results: dict, chunk_size: int):
        with io.BytesIO(json.dumps(results).encode('utf-8')) as buffer:
            while True:
                data = buffer.read(chunk_size)
                if not data:
                    break
                yield data

    await client.put_multipart(
        filename,
        dict_sender(
            results,
            chunk_size=PART_SIZE,
        ),
        headers={'Content-Type': content_type},
    )

async def write_csv(client: S3Client, filename: str, fieldnames: List[str], results: dict, content_type: str = 'text/csv'):
    def csv_sender(results: dict, fieldnames: List[str], chunk_size: int):
        with io.BytesIO() as buffer:
            # CSV writer needs to write strings. TextIOWrapper gets us back to bytes
            sb = io.TextIOWrapper(buffer, 'utf-8', newline='')
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

    await client.put_multipart(
        filename,
        csv_sender(
            results,
            fieldnames,
            chunk_size=PART_SIZE,
        ),
        headers={'Content-Type': content_type},
    )

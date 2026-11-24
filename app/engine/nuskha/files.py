"""Where original files live. Local disk now and for the desktop app; any S3-compatible bucket for hosting."""
from pathlib import Path

from .config import settings


class LocalFileStore:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


class S3FileStore:
    def __init__(self):
        import boto3

        self.bucket = settings.s3_bucket
        self.s3 = boto3.client(
            "s3", endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key,
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)  # no error if it's already gone


file_store = S3FileStore() if settings.file_store == "s3" else LocalFileStore(settings.files_dir)

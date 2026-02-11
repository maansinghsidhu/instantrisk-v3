"""
S3 Client Service

Replaces MinIO client for object storage operations.
Provides upload, download, presigned URLs, and listing functionality.
"""
import os
import uuid
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, BinaryIO
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from app.config import settings
import logging

logger = logging.getLogger(__name__)


class S3Client:
    """S3 client for document storage operations."""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """Initialize S3 client.

        Args:
            bucket_name: S3 bucket name (defaults to settings.S3_DOCUMENTS_BUCKET)
            region: AWS region (defaults to settings.S3_REGION)
        """
        self.bucket_name = bucket_name or settings.S3_DOCUMENTS_BUCKET
        self.region = region or settings.S3_REGION

        # Configure client with retries and timeouts
        config = Config(
            region_name=self.region,
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=5,
            read_timeout=30,
        )
        self.client = boto3.client("s3", config=config)
        self.resource = boto3.resource("s3", config=config)

    def upload_file(
        self,
        file_obj: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Upload a file to S3.

        Args:
            file_obj: File-like object to upload
            key: S3 object key (path within bucket)
            content_type: MIME type of the file
            metadata: Optional metadata to attach to the object

        Returns:
            Dict with upload details including key, bucket, etag
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            if metadata:
                extra_args["Metadata"] = metadata

            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs=extra_args if extra_args else None,
            )

            # Get object info
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)

            logger.info(f"Uploaded file to s3://{self.bucket_name}/{key}")

            return {
                "bucket": self.bucket_name,
                "key": key,
                "etag": response.get("ETag", "").strip('"'),
                "size": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", ""),
                "uploaded_at": datetime.utcnow().isoformat(),
            }
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Upload bytes to S3.

        Args:
            data: Bytes to upload
            key: S3 object key
            content_type: MIME type
            metadata: Optional metadata

        Returns:
            Dict with upload details
        """
        from io import BytesIO
        return self.upload_file(BytesIO(data), key, content_type, metadata)

    def download_file(self, key: str) -> bytes:
        """Download a file from S3.

        Args:
            key: S3 object key

        Returns:
            File contents as bytes
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            data = response["Body"].read()
            logger.info(f"Downloaded file from s3://{self.bucket_name}/{key}")
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {key}")
            logger.error(f"Failed to download file from S3: {e}")
            raise

    def download_to_file(self, key: str, local_path: str) -> str:
        """Download a file from S3 to local filesystem.

        Args:
            key: S3 object key
            local_path: Local file path to save to

        Returns:
            Local file path
        """
        try:
            self.client.download_file(self.bucket_name, key, local_path)
            logger.info(f"Downloaded s3://{self.bucket_name}/{key} to {local_path}")
            return local_path
        except ClientError as e:
            logger.error(f"Failed to download file: {e}")
            raise

    def get_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = "get_object",
    ) -> str:
        """Generate a presigned URL for S3 object access.

        Args:
            key: S3 object key
            expiration: URL expiration in seconds (default 1 hour)
            method: S3 method ('get_object' for download, 'put_object' for upload)

        Returns:
            Presigned URL string
        """
        try:
            url = self.client.generate_presigned_url(
                method,
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def get_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expiration: int = 3600,
    ) -> Dict[str, str]:
        """Generate a presigned URL for uploading.

        Args:
            key: S3 object key
            content_type: Expected content type
            expiration: URL expiration in seconds

        Returns:
            Dict with url and required fields
        """
        try:
            response = self.client.generate_presigned_post(
                self.bucket_name,
                key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, settings.MAX_FILE_SIZE_MB * 1024 * 1024],
                ],
                ExpiresIn=expiration,
            )
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned upload URL: {e}")
            raise

    def delete_file(self, key: str) -> bool:
        """Delete a file from S3.

        Args:
            key: S3 object key

        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Deleted s3://{self.bucket_name}/{key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file: {e}")
            raise

    def delete_files(self, keys: List[str]) -> Dict[str, Any]:
        """Delete multiple files from S3.

        Args:
            keys: List of S3 object keys

        Returns:
            Dict with deleted and error counts
        """
        if not keys:
            return {"deleted": 0, "errors": []}

        try:
            response = self.client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": [{"Key": key} for key in keys]},
            )
            deleted = len(response.get("Deleted", []))
            errors = response.get("Errors", [])

            logger.info(f"Deleted {deleted} files, {len(errors)} errors")
            return {"deleted": deleted, "errors": errors}
        except ClientError as e:
            logger.error(f"Failed to delete files: {e}")
            raise

    def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> List[Dict[str, Any]]:
        """List files in S3 bucket with optional prefix.

        Args:
            prefix: Filter by key prefix
            max_keys: Maximum number of keys to return

        Returns:
            List of file info dicts
        """
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            files = []

            for page in paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=prefix,
                PaginationConfig={"MaxItems": max_keys},
            ):
                for obj in page.get("Contents", []):
                    files.append({
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "etag": obj["ETag"].strip('"'),
                    })

            return files
        except ClientError as e:
            logger.error(f"Failed to list files: {e}")
            raise

    def file_exists(self, key: str) -> bool:
        """Check if a file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if file exists
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def get_file_info(self, key: str) -> Dict[str, Any]:
        """Get metadata about a file.

        Args:
            key: S3 object key

        Returns:
            Dict with file metadata
        """
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                "key": key,
                "bucket": self.bucket_name,
                "size": response["ContentLength"],
                "content_type": response.get("ContentType", ""),
                "last_modified": response["LastModified"].isoformat(),
                "etag": response["ETag"].strip('"'),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"Object not found: {key}")
            raise

    def copy_file(
        self,
        source_key: str,
        dest_key: str,
        dest_bucket: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Copy a file within or between buckets.

        Args:
            source_key: Source object key
            dest_key: Destination object key
            dest_bucket: Destination bucket (defaults to same bucket)

        Returns:
            Dict with copy result
        """
        dest_bucket = dest_bucket or self.bucket_name
        try:
            copy_source = {"Bucket": self.bucket_name, "Key": source_key}
            self.client.copy_object(
                CopySource=copy_source,
                Bucket=dest_bucket,
                Key=dest_key,
            )
            logger.info(f"Copied {source_key} to {dest_bucket}/{dest_key}")
            return {"source": source_key, "dest_bucket": dest_bucket, "dest_key": dest_key}
        except ClientError as e:
            logger.error(f"Failed to copy file: {e}")
            raise


def generate_document_key(
    assessment_id: str,
    filename: str,
    folder: str = "documents",
) -> str:
    """Generate a unique S3 key for a document.

    Args:
        assessment_id: Assessment UUID
        filename: Original filename
        folder: Subfolder (documents, loss-runs, etc.)

    Returns:
        S3 key in format: {folder}/{assessment_id}/{uuid}_{sanitized_filename}
    """
    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    unique_id = uuid.uuid4().hex[:8]
    return f"{folder}/{assessment_id}/{unique_id}_{safe_name}"


def generate_loss_run_key(assessment_id: str, filename: str) -> str:
    """Generate S3 key for loss run files.

    Args:
        assessment_id: Assessment UUID
        filename: Original filename

    Returns:
        S3 key for loss run storage
    """
    return generate_document_key(assessment_id, filename, folder="loss-runs")


# Singleton instances for common buckets
_documents_client: Optional[S3Client] = None
_rapidrate_client: Optional[S3Client] = None


def get_documents_client() -> S3Client:
    """Get S3 client for documents bucket."""
    global _documents_client
    if _documents_client is None:
        _documents_client = S3Client(bucket_name=settings.S3_DOCUMENTS_BUCKET)
    return _documents_client


def get_rapidrate_client() -> S3Client:
    """Get S3 client for RapidRate data bucket."""
    global _rapidrate_client
    if _rapidrate_client is None:
        _rapidrate_client = S3Client(bucket_name=settings.S3_RAPIDRATE_BUCKET)
    return _rapidrate_client

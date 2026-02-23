"""Service layer for S3-backed image management."""

from typing import Any

from src.obj.image import ImageManager, S3Image
from src.services.entry_service import EntryService


class ImageService:
    """Provides image operations with an injected S3 client."""

    def __init__(
        self,
        s3_client: Any,
        bucket_name: str,
        entry_service: EntryService,
    ) -> None:
        self._s3 = s3_client
        self._bucket_name = bucket_name
        self.entry_service = entry_service

    def create_manager(self) -> ImageManager:
        """Build an ImageManager using current entries."""
        return ImageManager(
            entries=self.entry_service.get_entries(),
            s3_client=self._s3,
            bucket_name=self._bucket_name,
        )

    def create_manager_bare(self) -> ImageManager:
        """Build an ImageManager with no entries (for upload-only use)."""
        return ImageManager(
            entries=[],
            s3_client=self._s3,
            bucket_name=self._bucket_name,
        )

    def generate_presigned_url(
        self, s3_img: S3Image, expires_in_sec: int = 120
    ) -> str:
        """Generate a presigned URL without creating a full manager."""
        return self._s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket_name,
                "Key": s3_img.s3_id,
                "ResponseContentType": "image/png",
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expires_in_sec,
        )

import subprocess
from time import perf_counter as pc
from collections import defaultdict
import logging
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from hashlib import sha1

import boto3
from PIL import Image, ImageGrab

from src.utils.env import IMAGES_SERIES_BUCKET_NAME
from src.obj.entry import Entry


logger = logging.getLogger(__name__)


IMAGES_TMP_DIR = Path(".images-tmp-local")
IMAGES_TMP_DIR.mkdir(exist_ok=True)


FOLDER_NAME = "movies-series-images"
FOLDER_PATH = Path(FOLDER_NAME)


def get_new_image_id() -> str:
    """Generate a new image ID."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class S3Image:
    s3_id: str
    size_bytes: int | None = field(default=None, hash=False, compare=False)

    @property
    def id(self) -> str:
        return Path(self.s3_id).stem

    @property
    def dt(self) -> datetime:
        return datetime.fromisoformat(self.id).astimezone()

    @property
    def sha1(self) -> str:
        return sha1(self.id.encode()).hexdigest()

    @property
    def tag(self) -> str:
        # TODO: implement
        raise NotImplementedError("Tagging is not implemented yet.")

    @property
    def sha1_short(self) -> str:
        return self.sha1[:8]

    def __str__(self):
        _size_info = f" ({self.size_bytes / 1024:.0f} KB)" if self.size_bytes else ""
        return f"Image(#{self.sha1_short}; {self.dt:%d.%m.%Y @ %H:%M}){_size_info}"

    def match(self, filter: str) -> bool:
        """Check if the image id matches the filter."""
        if filter in self.sha1:
            return True
        # TODO implement the rest of the logic
        return False

    def local_path(self) -> Path:
        return IMAGES_TMP_DIR / self.s3_id

    def clear_cache(self) -> bool:
        if self.local_path().exists():
            self.local_path().unlink()
            return True
        return False


class ImagesStore:
    def __init__(self, entries: list[Entry]):
        self.entries = entries
        _t0 = pc()
        self._s3 = boto3.client("s3")
        self._check_access()
        self._check_s3_consistency()
        self.loaded_in = pc() - _t0

    def _get_local_images(self) -> list[S3Image]:
        return [
            S3Image(
                s3_id=str(img_path.relative_to(IMAGES_TMP_DIR)),
                size_bytes=img_path.stat().st_size,
            )
            for img_path in IMAGES_TMP_DIR.glob("**/*.png")
        ]

    def sync(self):
        """Runs
        aws s3 sync s3://<BUCKET_NAME> .images-tmp-local/ --delete
        """
        # TODO: use boto3 ?
        result = subprocess.run(
            [
                "aws",
                "s3",
                "sync",
                f"s3://{IMAGES_SERIES_BUCKET_NAME}",
                str(IMAGES_TMP_DIR),
                "--delete",
            ],
            check=True,
        )
        if result.returncode != 0:
            logger.error("Error syncing images")
            raise RuntimeError("Error syncing images.")

    def _check_access(self):
        try:
            self._s3.head_bucket(Bucket=IMAGES_SERIES_BUCKET_NAME)
        except Exception as e:
            logger.error("Error checking S3 bucket", exc_info=e)
            raise RuntimeError("Error accessing bucket.") from e

    def _check_s3_consistency(self):
        """Ensure that all images attached to entries
        have corresponding S3 objects."""
        existing_images = {img.s3_id for img in self._get_s3_images()}
        for entry in self.entries:
            for img in entry.images:
                if img not in existing_images:
                    logger.error(
                        f"Image {img} is attached to an entry but does not exist in S3."
                    )

    def _get_s3_images(self) -> list[S3Image]:
        response = self._s3.list_objects_v2(
            Bucket=IMAGES_SERIES_BUCKET_NAME, Prefix=FOLDER_NAME + "/"
        )
        return [
            S3Image(s3_id=key, size_bytes=obj.get("Size"))
            for obj in response.get("Contents", [])
            if (key := obj.get("Key"))
        ]

    def get_images_by_filter(self, filter: str) -> list[S3Image]:
        """
        Get images by a filter string.
        Matches:
            - part of image hash (e.g., "ad7c1") but only if unique
            - date string (e.g. "15.05.2025" or "2025-05-15")
        Note that the filter supports the '*' wildcard for the date.
            E.g. "15.05.2025*" or "2025-05-15*" would match all images from that date.
        """
        imgs = self._get_local_images()
        matched = [img for img in imgs if img.match(filter)]
        if len(matched) > 1:
            logger.error(
                f"Multiple images matched the hash filter '{filter}': {matched}"
            )
            return []
        return matched

    @staticmethod
    def grab_clipboard_image() -> Image.Image | None:
        img = ImageGrab.grabclipboard()
        if img is None:
            return None
        if not isinstance(img, Image.Image):
            logger.warning(f"Clipboard content is not an image: {img!r}")
            return None
        return img

    def _download_image_to(self, file_key: str, to: Path):
        try:
            self._s3.download_file(IMAGES_SERIES_BUCKET_NAME, file_key, str(to))
        except Exception as e:
            logger.error(f"Error downloading image {file_key}", exc_info=e)

    def show_images(self, s3_images: list[S3Image]):
        s3_image_paths: list[tuple[S3Image, Path]] = []

        for s3_img in s3_images:
            local_path = s3_img.local_path()
            if not local_path.exists():
                print(
                    f"Does not exist locally; downloading {s3_img.id} to {local_path}..."
                )
                self._download_image_to(s3_img.s3_id, local_path)
            s3_image_paths.append((s3_img, local_path))

        for s3_img, img_path in s3_image_paths:
            with Image.open(img_path) as img:
                img.show(title=s3_img.id)

    def _upload_image(self, img: Image.Image, s3_img: S3Image):
        """Caches the image locally and uploads it to S3."""
        img.save(s3_img.local_path(), format="PNG")
        self._s3.upload_file(
            str(s3_img.local_path()),
            IMAGES_SERIES_BUCKET_NAME,
            s3_img.s3_id,
        )

    def upload_from_clipboard(self) -> S3Image | None:
        # TODO: add tagging
        img = self.grab_clipboard_image()
        if img is None:
            return
        key = str(FOLDER_PATH / f"{get_new_image_id()}.png")
        s3_img = S3Image(key)
        self._upload_image(img, s3_img)
        return s3_img

    def delete_image(self, s3_img: S3Image):
        self._s3.delete_object(Bucket=IMAGES_SERIES_BUCKET_NAME, Key=s3_img.s3_id)
        s3_img.clear_cache()

    def get_image_to_entries(self) -> defaultdict[S3Image, list[Entry]]:
        """Map S3Image objects to their associated entries."""
        image_to_entries: defaultdict[S3Image, list[Entry]] = defaultdict(list)
        for entry in self.entries:
            for image_id in entry.images:
                image_to_entries[S3Image(image_id)].append(entry)
        for image in self._get_s3_images():
            image_to_entries[image]
        return image_to_entries

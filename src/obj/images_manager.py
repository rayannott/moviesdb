from collections import defaultdict
from io import BytesIO
import logging
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from hashlib import sha1
import tempfile

import boto3
from PIL import Image, ImageGrab

from src.utils.env import IMAGES_SERIES_BUCKET_NAME
from src.obj.entry import Entry


logger = logging.getLogger(__name__)


FOLDER_NAME = "movies-series-images"
FOLDER_PATH = Path(FOLDER_NAME)


def get_new_image_id() -> str:
    """Generate a new image ID."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class S3Image:
    s3_id: str

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
    def sha1_short(self) -> str:
        return self.sha1[:8]

    def __str__(self):
        return f"Image(#{self.sha1_short}; {self.dt:%d.%m.%Y @ %H:%M})"

    def match(self, filter: str) -> bool:
        """Check if the image id matches the filter."""
        if filter in self.sha1:
            return True
        # TODO implement the rest of the logic
        return False


class ImagesStore:
    def __init__(self, entries: list[Entry]):
        self._s3 = boto3.client("s3")
        self._check_access()
        self.entries = entries

    def _check_access(self):
        try:
            self._s3.head_bucket(Bucket=IMAGES_SERIES_BUCKET_NAME)
        except Exception as e:
            raise RuntimeError("Error accessing bucket.") from e
        
    def _check_consistency(self):
        """Ensure that all images attached to entries
        have corresponding S3 objects."""
        existing_images = {img.s3_id for img in self.get_images()}
        images_to_entries = self.get_image_to_entries()
        for img, entries in images_to_entries.items():
            for ent_ in entries:
                if ent_ not in existing_images:
                    logger.error(f"Image {img} is attached to a non-existent entry: {ent_}")

    def get_images(self) -> list[S3Image]:
        response = self._s3.list_objects_v2(
            Bucket=IMAGES_SERIES_BUCKET_NAME, Prefix=FOLDER_NAME + "/"
        )
        return [
            S3Image(key)
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
        imgs = self.get_images()
        matched = [img for img in imgs if img.match(filter)]
        if len(matched) > 1:
            logger.warning(
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
        self._s3.download_file(IMAGES_SERIES_BUCKET_NAME, file_key, str(to))

    def show_images(self, s3_images: list[S3Image]):
        with tempfile.TemporaryDirectory() as tmpdir:
            for s3_img in s3_images:
                self._download_image_to(s3_img.s3_id, Path(tmpdir) / f"{s3_img.id}.png")
            # Show all images in the temporary directory
            for img_path in Path(tmpdir).glob("*.png"):
                with Image.open(img_path) as img:
                    img.show()

    def _upload_image(self, img: Image.Image, file_key: str):
        buffer = BytesIO()
        # TODO: implement image formats
        img.save(buffer, format="PNG")
        buffer.seek(0)

        self._s3.upload_fileobj(buffer, IMAGES_SERIES_BUCKET_NAME, file_key)

    def upload_from_clipboard(self) -> S3Image | None:
        img = self.grab_clipboard_image()
        if img is None:
            print("No image found in clipboard.")
            return
        key = str(FOLDER_PATH / f"{get_new_image_id()}.png")
        self._upload_image(img, key)
        return S3Image(key)

    def move_image(self, from_: Path, to_: Path):
        self._s3.copy_object(
            Bucket=IMAGES_SERIES_BUCKET_NAME,
            CopySource={"Bucket": IMAGES_SERIES_BUCKET_NAME, "Key": str(from_)},
            Key=str(to_),
        )
        self._s3.delete_object(Bucket=IMAGES_SERIES_BUCKET_NAME, Key=str(from_))

    def delete_image(self, file_key: str):
        self._s3.delete_object(Bucket=IMAGES_SERIES_BUCKET_NAME, Key=file_key)

    def get_image_to_entries(self) -> defaultdict[S3Image, list[Entry]]:
        """Map S3Image objects to their associated entries."""
        image_to_entries: defaultdict[S3Image, list[Entry]] = defaultdict(list)
        for entry in self.entries:
            for image_id in entry.images:
                image_to_entries[S3Image(image_id)].append(entry)
        for image in self.get_images():
            image_to_entries[image]
        return image_to_entries

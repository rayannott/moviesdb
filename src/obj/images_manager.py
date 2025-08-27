import logging
import re
import subprocess
import webbrowser
from functools import cache
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from time import perf_counter as pc
from warnings import deprecated

import boto3
from PIL import Image, ImageGrab, UnidentifiedImageError

from src.obj.entry import Entry
from src.utils.env import IMAGES_SERIES_BUCKET_NAME

logger = logging.getLogger(__name__)

DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")

FOLDER_NAME = "movies-series-images"
FOLDER_PATH = Path(FOLDER_NAME)

IMAGES_TMP_DIR = Path(".images-tmp-local")
(IMAGES_TMP_DIR / FOLDER_NAME).mkdir(exist_ok=True, parents=True)


def get_new_image_id() -> str:
    """Generate a new image ID."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class S3Image:
    s3_id: str
    size_bytes: int | None = field(default=None, hash=False, compare=False)
    entries: list[Entry] = field(default_factory=list, hash=False, compare=False)
    tags: dict[str, str] = field(default_factory=dict, hash=False, compare=False)

    def with_tags(self, tags: dict[str, str]) -> "S3Image":
        return S3Image(
            s3_id=self.s3_id,
            size_bytes=self.size_bytes,
            entries=self.entries,
            tags=tags,
        )

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
        _size_info = (
            f"; {round(self.size_bytes / 1024):>4} KB" if self.size_bytes else ""
        )
        _tags = (
            " (" + ", ".join(f"{k}={v}" for k, v in self.tags.items()) + ")"
            if self.tags
            else ""
        )
        _attached = (
            f" -> {len(self.entries)} entries"
            if len(self.entries) > 1
            else f" -> {self.entries[0]}"
            if self.entries
            else ""
        )
        return f"Image(#{self.sha1_short}; {self.dt:%d.%m.%Y @ %H:%M}{_size_info}){_tags}{_attached}"

    def match(self, filter: str) -> bool:
        """Check if the image id matches the filter.
        If filter starts with '!', the match is negated."""
        should_negate = filter.startswith("!")

        def negate(x: bool) -> bool:
            return not x if should_negate else x

        filter = filter.lstrip("!")
        if filter == "*":
            return negate(True)
        if filter == "attached":
            return negate(bool(self.entries))
        if filter[0] == "#" and len(filter) >= 4 and filter[1:] in self.sha1:
            return negate(True)
        if (
            DATE_RE.match(filter)
            and self.dt.date() == datetime.strptime(filter, "%d.%m.%Y").date()
        ):
            return negate(True)
        # by tags
        if "=" in filter:
            tag_key, tag_value = filter.split("=", maxsplit=1)
            return negate(
                any(
                    tag_key in key and tag_value in value
                    for key, value in self.tags.items()
                )
            )
        return negate(False)

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
        self._s3 = boto3.client("s3", region_name="eu-north-1")
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

    @deprecated("Do not use local storage.", category=DeprecationWarning)
    def sync(self):
        """Runs
        aws s3 sync s3://<BUCKET_NAME> .images-tmp-local/ --delete
        """
        try:
            subprocess.run(
                [
                    "aws",
                    "s3",
                    "sync",
                    f"s3://{IMAGES_SERIES_BUCKET_NAME}",
                    str(IMAGES_TMP_DIR),
                    "--delete",
                ]
            )
        except Exception as e:
            logger.error("Error syncing images", exc_info=e)

    def _check_access(self):
        try:
            self._s3.head_bucket(Bucket=IMAGES_SERIES_BUCKET_NAME)
        except Exception as e:
            logger.error("Error checking S3 bucket", exc_info=e)
            raise RuntimeError("Error accessing bucket.") from e

    def _get_s3_response(self):
        return self._s3.list_objects_v2(
            Bucket=IMAGES_SERIES_BUCKET_NAME,
            Prefix=FOLDER_NAME + "/",
        )

    def _check_s3_consistency(self):
        """Ensure that all images attached to entries
        have corresponding S3 objects."""
        existing_images = {img.s3_id for img in self._get_s3_images()}
        for entry in self.entries:
            for img in entry.image_ids:
                if img not in existing_images:
                    logger.error(
                        f"Image {img} is attached to an entry but does not exist in S3."
                    )

    def _detect_duplicates(self):
        pass  # TODO: implement using ETag (hash)

    def _get_s3_images(self) -> list[S3Image]:
        response = self._get_s3_response()
        return [
            S3Image(s3_id=key, size_bytes=obj.get("Size"))
            for obj in response.get("Contents", [])
            if (key := obj.get("Key"))
        ]

    @cache
    def _get_ids_to_tags(self) -> dict[str, dict[str, str]]:
        tags: dict[str, dict[str, str]] = {}
        for s3_img in self._get_s3_images():
            resp = self._s3.get_object_tagging(
                Bucket=IMAGES_SERIES_BUCKET_NAME,
                Key=s3_img.s3_id,
            )
            tags[s3_img.s3_id] = {t["Key"]: t["Value"] for t in resp["TagSet"]}
        return tags

    def set_s3_tags_for(self, s3_img: S3Image, tags: dict[str, str]) -> S3Image:
        """Set tags for an S3 image. Overwrites existing tags with the same keys.
        Return the updated S3Image object."""
        tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
        self._s3.put_object_tagging(
            Bucket=IMAGES_SERIES_BUCKET_NAME,
            Key=s3_img.s3_id,
            Tagging={"TagSet": tag_set},  # type: ignore
        )
        return s3_img.with_tags(tags)

    def get_images(self, filter: str = "") -> list[S3Image]:
        """
        Get images.
        Optionally, filter by:
            - at least 4 characters of image sha1 hash (e.g., "#ad7c");
            - 'detached': all images that are not attached to any entry
            - 'attached': all images that are attached to an entry
            - '*': all images
            - exact date (e.g. "15.05.2025")
            - tag key-value pair (e.g. "tag=value"): matches if tag key contains "tag" and tag value contains "value"
        """
        response = self._get_s3_response()
        _id_to_entries_size: dict[str, tuple[list[Entry], int | None]] = {
            key: ([], obj.get("Size"))
            for obj in response.get("Contents", [])
            if (key := obj.get("Key"))
        }
        _tags = self._get_ids_to_tags()
        for entry in self.entries:
            for image_id in entry.image_ids:
                _id_to_entries_size[image_id][0].append(entry)
        images = [
            S3Image(
                s3_id=image_id,
                size_bytes=size,
                entries=entries,
                tags=_tags.get(image_id, {}),
            )
            for image_id, (entries, size) in _id_to_entries_size.items()
        ]
        return [img for img in images if not filter or img.match(filter)]

    @staticmethod
    def grab_clipboard_image() -> Image.Image | None:
        try:
            img = ImageGrab.grabclipboard()
        except UnidentifiedImageError as e:
            logger.warning(f"Could not identify clipboard image: {e}")
            return None
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

    def show_images(
        self, s3_images: list[S3Image], in_browser: bool = True
    ) -> Iterator[str]:
        if not in_browser:
            self._show_locally(s3_images)
            return
        controller = webbrowser.get("firefox")
        for img in s3_images:
            url = self.generate_presigned_url(img)
            controller.open_new_tab(url)
            yield f"Opened {img} in the browser"
        return

    @deprecated("Use show_images() instead.", category=DeprecationWarning)
    def _show_locally(self, s3_images: list[S3Image]) -> Iterator[str]:
        s3_image_paths: list[tuple[S3Image, Path]] = []
        for s3_img in s3_images:
            local_path = s3_img.local_path()
            if not local_path.exists():
                yield (
                    f"Does not exist locally; downloading {s3_img.id} to {local_path}..."
                )
            self._download_image_to(s3_img.s3_id, local_path)
            s3_image_paths.append((s3_img, local_path))
        for s3_img, img_path in s3_image_paths:
            with Image.open(img_path) as img:
                img.show(title=s3_img.id)
                yield f"Opened {s3_img} locally"

    def clear_cache(self) -> int:
        # only use to clear the local directory populated by uploading images
        n = 0
        for img in self._get_local_images():
            img.local_path().unlink()
            n += 1
        return n

    def _upload_image(
        self,
        img: Image.Image,
        s3_img: S3Image,
        tags: dict[str, str] | None,
    ) -> S3Image:
        """Caches the image locally and uploads it to S3."""
        img.save(s3_img.local_path(), format="PNG")
        self._s3.upload_file(
            str(s3_img.local_path()),
            IMAGES_SERIES_BUCKET_NAME,
            s3_img.s3_id,
        )
        if tags:
            return self.set_s3_tags_for(s3_img, tags)
        return s3_img

    def upload_from_clipboard(
        self, tags: dict[str, str] | None = None
    ) -> S3Image | None:
        img = self.grab_clipboard_image()
        if img is None:
            return None
        key = str(FOLDER_PATH / f"{get_new_image_id()}.png")
        s3_img = S3Image(key)
        return self._upload_image(img, s3_img, tags)

    def get_image_stats(self) -> tuple[int, int]:
        images = self.get_images()
        num_total_images = len(images)
        num_attached_images = sum(1 for img in images if img.entries)
        return num_total_images, num_attached_images

    def delete_image(self, s3_img: S3Image):
        self._s3.delete_object(Bucket=IMAGES_SERIES_BUCKET_NAME, Key=s3_img.s3_id)
        s3_img.clear_cache()

    @deprecated("Use get_images() instead.", category=DeprecationWarning)
    def get_image_to_entries(self) -> defaultdict[S3Image, list[Entry]]:
        """Map S3Image objects to their associated entries."""
        image_to_entries: defaultdict[S3Image, list[Entry]] = defaultdict(list)
        for entry in self.entries:
            for image_id in entry.image_ids:
                image_to_entries[S3Image(image_id)].append(entry)
        for image in self._get_s3_images():
            image_to_entries[image]
        return image_to_entries

    def generate_presigned_url(self, s3_img: S3Image, expires_in=120):
        """
        Generate a presigned URL for an S3 object.
        """
        url = self._s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": IMAGES_SERIES_BUCKET_NAME,
                "Key": s3_img.s3_id,
                "ResponseContentType": "image/png",
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expires_in,
        )
        return url

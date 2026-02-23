import io
import logging
import re
import subprocess
import webbrowser
from collections import defaultdict
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from hashlib import sha1
from pathlib import Path
from time import perf_counter as pc
from warnings import deprecated
from zoneinfo import ZoneInfo

from mypy_boto3_s3 import S3Client
from PIL import Image, ImageGrab, UnidentifiedImageError
from rich.console import Console
from rich.prompt import Prompt

from src.models.entry import Entry
from src.utils.rich_utils import get_pretty_progress

logger = logging.getLogger(__name__)

DATE_RE = re.compile(r"\d{2}\.\d{2}\.\d{4}")

FOLDER_NAME = "movies-series-images"
FOLDER_PATH = Path(FOLDER_NAME)

IMAGES_TMP_DIR = Path(".images-tmp-local")
(IMAGES_TMP_DIR / FOLDER_NAME).mkdir(exist_ok=True, parents=True)

IMAGES_EXPORTED_DIR = Path("export-local", "images")
IMAGES_EXPORTED_DIR.mkdir(exist_ok=True, parents=True)


def get_new_image_id() -> str:
    """Generate a new image ID."""
    return datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat()


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
    def filename(self) -> str:
        return Path(self.s3_id).name

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
        if filter[0] == "#" and len(filter) >= 4 and self.sha1.startswith(filter[1:]):
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

    def exported_local_path(self) -> Path:
        return IMAGES_EXPORTED_DIR / self.filename

    def clear_cache(self) -> bool:
        if self.local_path().exists():
            self.local_path().unlink()
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "s3_id": self.s3_id,
            "sha1": self.sha1,
            "size_bytes": self.size_bytes,
            "tags": self.tags,
        }


class ImageManager:
    def __init__(
        self,
        entries: list[Entry],
        s3_client: S3Client,
        bucket_name: str,
    ) -> None:
        self.entries = entries
        self._s3 = s3_client
        self._bucket_name = bucket_name
        _t0 = pc()
        self._check_access()
        self._check_s3_consistency()
        self.loaded_in = pc() - _t0

    def _get_exported_local_images(self) -> list[S3Image]:
        return [
            img
            for img in self._get_s3_images_bare()
            if img.exported_local_path().exists()
        ]

    def _get_local_images(self) -> list[S3Image]:
        return [
            S3Image(
                s3_id=FOLDER_NAME + "/" + img_path.name,
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
                    f"s3://{self._bucket_name}",
                    str(IMAGES_TMP_DIR),
                    "--delete",
                ]
            )
        except Exception as e:
            logger.error("Error syncing images", exc_info=e)

    def _check_access(self):
        try:
            self._s3.head_bucket(Bucket=self._bucket_name)
        except Exception as e:
            logger.error("Error checking S3 bucket", exc_info=e)
            raise RuntimeError("Error accessing bucket.") from e

    def _get_s3_response(self):
        return self._s3.list_objects_v2(
            Bucket=self._bucket_name,
            Prefix=FOLDER_NAME + "/",
        )

    def _check_s3_consistency(self):
        """Ensure that all images attached to entries
        have corresponding S3 objects."""
        existing_images = {img.s3_id for img in self._get_s3_images_bare()}
        for entry in self.entries:
            for img in entry.image_ids:
                if img not in existing_images:
                    logger.error(
                        f"Image {img} is attached to an entry but does not exist in S3."
                    )

    def _group_by_etag_hash(self) -> defaultdict[str, list[str]]:
        # to detect duplicates
        response = self._get_s3_response()
        raw_s3_obj_contents = response.get("Contents", [])
        hash_to_images = defaultdict(list)
        for obj in raw_s3_obj_contents:
            hash_to_images[obj.get("ETag")].append(obj.get("Key"))
        return hash_to_images

    def _get_s3_images_bare(self) -> list[S3Image]:
        response = self._get_s3_response()
        return [
            S3Image(s3_id=key, size_bytes=obj.get("Size"))
            for obj in response.get("Contents", [])
            if (key := obj.get("Key"))
        ]

    def _check_resolve_duplicate_images(
        self,
        cns: Console,
        *,
        verbose_if_no_dups: bool,
        prompt_to_delete: bool = True,
    ):
        hash_to_img_ids = self._group_by_etag_hash()
        dups = {h: ids for h, ids in hash_to_img_ids.items() if len(ids) > 1}
        if not dups:
            if verbose_if_no_dups:
                cns.print("[green]No duplicate images found.")
            return
        cns.print(f"[bold yellow]Found {len(dups)} duplicate groups:")
        for i, ids in enumerate(dups.values()):
            cns.print(f"Group {i + 1}:")
            for s3_id in ids:
                cns.print(f"  - {S3Image(s3_id)}")
        if not prompt_to_delete:
            return
        prompt = Prompt.ask(
            "[yellow]Delete all but the first added image in each group? (this will ask for confirmation again)",
            choices=["y", "n"],
            default="n",
            console=cns,
        )
        if prompt != "y":
            cns.print("[yellow]No images were deleted.")
            return
        to_delete = []
        for ids in dups.values():
            s3_img_objs = sorted(map(S3Image, ids), key=lambda img: img.dt)
            to_delete.extend(s3_img_objs[1:])
        cns.print(f"Selected {', '.join(map(str, to_delete))} for deletion.")
        prompt = Prompt.ask(
            "Delete them?",
            choices=["y", "n"],
            default="n",
            console=cns,
        )
        if prompt != "y":
            cns.print("[yellow]No images were deleted.")
            return
        for img in to_delete:
            self.delete_image(img)
            cns.print(f"[red]Deleted {img}")
        cns.print(f"[green]Deleted {len(to_delete)} images.")

    def load_tags_pretty(self, cns: Console) -> dict[str, dict[str, str]]:
        """
        Loads image tags from S3 concurrently using a ThreadPoolExecutor,
        while showing a single Rich progress bar.
        """
        res = {}
        _t0 = pc()

        def worker(s3_id: S3Image) -> tuple[str, dict[str, str]]:
            return s3_id.s3_id, self.get_tags_for(s3_id)

        all_ids = self._get_s3_images_bare()

        progress = get_pretty_progress()
        with progress, ThreadPoolExecutor(max_workers=16) as executor:
            task = progress.add_task("Loading image tags...", total=len(all_ids))
            futures = {executor.submit(worker, s3_id): s3_id for s3_id in all_ids}
            for fut in as_completed(futures):
                s3_id, tags = fut.result()
                res[s3_id] = tags
                progress.update(task, advance=1)

        self._tags_loaded_in = pc() - _t0
        cns.print(f"[dim]Tags loaded in {self._tags_loaded_in:.3f} sec.")
        return res

    def get_tags_for(self, s3_img: S3Image) -> dict[str, str]:
        resp = self._s3.get_object_tagging(
            Bucket=self._bucket_name,
            Key=s3_img.s3_id,
        )
        return {t["Key"]: t["Value"] for t in resp["TagSet"]}

    def _iterate_ids_tagsets(self) -> Iterator[tuple[str, dict[str, str]]]:
        for s3_img in self._get_s3_images_bare():
            yield s3_img.s3_id, self.get_tags_for(s3_img)

    @cache
    def _get_ids_to_tags(self) -> dict[str, dict[str, str]]:
        return dict(self._iterate_ids_tagsets())

    def set_s3_tags_for(self, s3_img: S3Image, tags: dict[str, str]) -> S3Image:
        """Set tags for an S3 image. Overwrites existing tags with the same keys.
        Return the updated S3Image object."""
        tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
        self._s3.put_object_tagging(
            Bucket=self._bucket_name,
            Key=s3_img.s3_id,
            Tagging={"TagSet": tag_set},  # type: ignore
        )
        return s3_img.with_tags(tags)

    def get_images(
        self,
        filter: str = "*",
        *,
        with_tags: dict[str, dict[str, str]] | None = None,
    ) -> list[S3Image]:
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
        _tags = self._get_ids_to_tags() if with_tags is None else with_tags
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
        return [img for img in images if img.match(filter)]

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

    def _download_image_to(self, s3_id: str, to: Path):
        try:
            self._s3.download_file(self._bucket_name, s3_id, str(to))
        except Exception as e:
            logger.error(f"Error downloading image {s3_id}", exc_info=e)

    def show_images(
        self, s3_images: list[S3Image], in_browser: bool = False
    ) -> Iterator[str]:
        for img in s3_images:
            url = self.generate_presigned_url(img)
            if not in_browser:
                yield f"{img}"
                self._show_locally(url)
            else:
                self.browser().open_new_tab(url)
                yield f"Opened {img} in the browser"

    @cache
    def browser(self):
        return webbrowser.get("firefox")

    def _show_in_browser(self, presigned_url: str):
        try:
            self.browser().open_new_tab(presigned_url)
        except Exception as e:
            logger.error("Error opening image in browser", exc_info=e)

    def _show_locally(self, presigned_url: str):
        try:
            subprocess.run(["mcat", presigned_url])
            print()
        except Exception as e:
            logger.error(
                "Error showing image locally with mcat. Make sure mcat is installed. Opening in browser instead.",
                exc_info=e,
            )
            self._show_in_browser(presigned_url)

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
            self._bucket_name,
            s3_img.s3_id,
        )
        if tags:
            return self.set_s3_tags_for(s3_img, tags)
        return s3_img

    def _upload_image_bytes(
        self,
        img_bytes: bytes,
        s3_img: S3Image,
        tags: dict[str, str] | None,
    ) -> S3Image:
        """Uploads image bytes to S3."""
        self._s3.upload_fileobj(
            io.BytesIO(img_bytes),
            self._bucket_name,
            s3_img.s3_id,
        )
        if tags:
            return self.set_s3_tags_for(s3_img, tags)
        return s3_img

    def upload_from_path(
        self, path: Path, tags: dict[str, str] | None = None
    ) -> S3Image | None:
        try:
            img = Image.open(path)
        except UnidentifiedImageError as e:
            logger.error(f"Error opening image from path {path}", exc_info=e)
            return None
        except Exception as e:
            logger.error(f"Unexpected error opening image from path {path}", exc_info=e)
            return None
        key = str(FOLDER_PATH / f"{get_new_image_id()}.png")
        s3_img = S3Image(key)
        return self._upload_image(img, s3_img, tags)

    def upload_from_clipboard(
        self, tags: dict[str, str] | None = None
    ) -> S3Image | None:
        img = self.grab_clipboard_image()
        if img is None:
            return None
        key = str(FOLDER_PATH / f"{get_new_image_id()}.png")
        s3_img = S3Image(key)
        return self._upload_image(img, s3_img, tags)

    def delete_image(self, s3_img: S3Image):
        self._s3.delete_object(Bucket=self._bucket_name, Key=s3_img.s3_id)
        s3_img.clear_cache()

    @deprecated("Use get_images() instead.", category=DeprecationWarning)
    def get_image_to_entries(self) -> defaultdict[S3Image, list[Entry]]:
        """Map S3Image objects to their associated entries."""
        image_to_entries: defaultdict[S3Image, list[Entry]] = defaultdict(list)
        for entry in self.entries:
            for image_id in entry.image_ids:
                image_to_entries[S3Image(image_id)].append(entry)
        for image in self._get_s3_images_bare():
            image_to_entries[image]
        return image_to_entries

    def generate_presigned_url(self, s3_img: S3Image, expires_in_sec=120):
        """
        Generate a presigned URL for an S3 object.
        """
        url = self._s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket_name,
                "Key": s3_img.s3_id,
                "ResponseContentType": "image/png",
                "ResponseContentDisposition": "inline",
            },
            ExpiresIn=expires_in_sec,
        )
        return url

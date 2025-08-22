from io import BytesIO
import logging
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass

import boto3
from PIL import Image, ImageGrab
import dotenv


dotenv.load_dotenv()


logger = logging.getLogger(__name__)


BUCKET_NAME = "airat-test-bucket"
FOLDER_NAME = "movies-series-images"
FOLDER_PATH = Path(FOLDER_NAME)


def get_new_image_id() -> str:
    """Generate a new image ID."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class S3Image:
    id: str


class Bucket:
    def __init__(self):
        self._s3 = boto3.client("s3")
        # check if bucket exists
        try:
            self._s3.head_bucket(Bucket=BUCKET_NAME)
        except Exception as e:
            logger.error(f"Error checking bucket: {e}")

    def get_images(self) -> list[str]:
        response = self._s3.list_objects_v2(
            Bucket=BUCKET_NAME, Prefix=FOLDER_NAME + "/"
        )
        return [key for obj in response.get("Contents", []) if (key := obj.get("Key"))]

    @staticmethod
    def grab_clipboard_image() -> Image.Image | None:
        img = ImageGrab.grabclipboard()
        if img is None:
            return None
        if not isinstance(img, Image.Image):
            logger.warning(f"Clipboard content is not an image: {img!r}")
            return None
        return img

    def _download_image_to(self, file_key: str, output_path: Path):
        self._s3.download_file(BUCKET_NAME, file_key, str(output_path))

    def _view_image(self, file_key: str):
        download_to = Path(f"/tmp/{file_key.split('/')[-1]}")
        self._download_image_to(file_key, download_to)
        with open(download_to, "rb") as f:
            img = Image.open(f)
        img.show()

    def _upload_image(self, img: Image.Image, file_key: str):
        buffer = BytesIO()
        # TODO: implement image formats
        img.save(buffer, format="PNG")
        buffer.seek(0)

        self._s3.upload_fileobj(buffer, BUCKET_NAME, file_key)

    def upload_from_clipboard(self) -> Image.Image | None:
        img = self.grab_clipboard_image()
        if img is None:
            print("No image found in clipboard.")
            return
        key = str(FOLDER_PATH / f"{get_new_image_id()}.png")
        self._upload_image(img, key)
        return img

    def move_image(self, from_: Path, to_: Path):
        self._s3.copy_object(
            Bucket=BUCKET_NAME,
            CopySource={"Bucket": BUCKET_NAME, "Key": str(from_)},
            Key=str(to_),
        )
        self._s3.delete_object(Bucket=BUCKET_NAME, Key=str(from_))

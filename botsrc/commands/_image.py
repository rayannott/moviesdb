import telebot
from telebot import types
from loguru import logger

from botsrc.utils import select_entry_by_oid_part
from src.models.entry import Entry
from src.obj.image import ImageManager, S3Image
from src.parser import Flags, KeywordArgs, PositionalArgs


MAX_IMAGES = 10


def get_media_group(
    image_manager: ImageManager,
    images: list[S3Image],
    caption: str | None = None,
) -> list[types.InputMediaPhoto]:
    photo_group = [
        types.InputMediaPhoto(
            image_manager.generate_presigned_url(img, expires_in_sec=10),
            caption=caption if i == 0 else None,
        )
        for i, img in enumerate(images)
    ]
    return photo_group


def image(
    message: types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
    kwargs: KeywordArgs,
    entries: list[Entry] | None = None,
) -> None:
    if entries is None:
        entries = []
    image_manager = ImageManager(entries)

    match pos:
        case ["list", filter]:
            imgs = image_manager.get_images(filter)
            logger.debug(f"found {len(imgs)} images matching {filter!r}")
            if not imgs:
                bot.send_message(
                    message.chat.id, f"No images found matching {filter!r}"
                )
                return
            msg = f"Found {len(imgs)} images matching {filter!r}:\n"
            if len(imgs) > MAX_IMAGES:
                imgs = imgs[-MAX_IMAGES:]
                msg += f"(last {MAX_IMAGES})\n"
            for img in imgs:
                msg += f"{img}\n"
            if "show" in flags:
                logger.debug(f"showing images for {filter!r}")
                photo_group = get_media_group(
                    image_manager,
                    imgs,
                    caption=f"{len(imgs)} images matching {filter!r}",
                )
                bot.send_media_group(message.chat.id, photo_group)  # type: ignore
            else:
                bot.send_message(message.chat.id, msg)
        case ["entry", entry_oid]:
            logger.debug(f"fetching images for entry matching {entry_oid=!r}")
            selected_entry = select_entry_by_oid_part(entry_oid, entries)
            if not selected_entry:
                bot.send_message(
                    message.chat.id, f"No entry found matching {entry_oid!r}"
                )
                logger.debug(f"no entry found matching {entry_oid!r}")
                return
            imgs = [S3Image(s3_id=img_id) for img_id in selected_entry.image_ids]
            if not imgs:
                bot.send_message(
                    message.chat.id, f"No images found for {selected_entry}"
                )
                logger.debug(f"no images found for {selected_entry}")
                return
            if len(imgs) > MAX_IMAGES:
                logger.debug(f"limiting images to last {MAX_IMAGES}")
                imgs = imgs[-MAX_IMAGES:]
            photo_group = get_media_group(
                image_manager, imgs, caption=f"Images of {selected_entry}"
            )
            bot.send_media_group(message.chat.id, photo_group)  # type: ignore
        case _:
            bot.send_message(message.chat.id, "Invalid image command.")
            logger.debug(
                f"invalid image command with pos={pos}, flags={flags}, kwargs={kwargs}"
            )

import telebot
from telebot import types
from loguru import logger

from src.obj.image import FOLDER_PATH, ImageManager, get_new_image_id, S3Image


def upload_photo(
    message: types.Message,
    bot: telebot.TeleBot,
):
    photo_id = message.photo[-1].file_id if message.photo else "no_photo"
    photo_info = bot.get_file(photo_id)
    if photo_info is None:
        logger.error(f"Failed to get file info for photo_id: {photo_id}")
        bot.reply_to(message, "Failed to get photo info.")
        return
    if photo_info.file_path is None:
        logger.error(f"File path is None for photo_id: {photo_id}")
        bot.reply_to(message, "Failed to get photo file path.")
        return
    photo_bytes = bot.download_file(photo_info.file_path)
    logger.debug(f"Photo received; {photo_id=}, {photo_info=}, {len(photo_bytes)=}")

    image_manager = ImageManager([])
    key = str(FOLDER_PATH / f"{get_new_image_id()}.png")
    s3_img = S3Image(key)

    image_manager._upload_image_bytes(photo_bytes, s3_img, tags=None)
    bot.reply_to(message, f"Photo uploaded with id: {s3_img.id}")
    logger.debug(f"Photo uploaded; {s3_img=}")

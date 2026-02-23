import telebot
from telebot import types
from loguru import logger

from botsrc.utils import format_entry, list_many_entries
from src.models.entry import build_tags
from src.mongo import Mongo
from src.parser import Flags, PositionalArgs
from src.utils.utils import replace_tag_alias


def tag(
    message: types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
):
    entries = Mongo.load_entries()
    tags = build_tags(entries)
    if not pos:
        msg = "Tags:\n" + "\n".join(
            f"{len(entries):>3}   {tag:<18}"
            for tag, entries in sorted(
                tags.items(), key=lambda x: len(x[1]), reverse=True
            )
        )
        bot.send_message(message.chat.id, msg)
        logger.debug("no positional arguments; listing all tags")
        return
    if len(pos) == 1:
        tag = replace_tag_alias(pos[0])
        if (entries := tags.get(tag)) is None:
            bot.send_message(message.chat.id, f"Tag {tag} not found.")
            logger.debug(f"tag {tag!r} not found")
            return
        res = list_many_entries(
            entries,
            "verbose" in flags,
            "oid" in flags,
            override_title=f"{len(entries)} entries with tag {tag!r}",
        )
        bot.send_message(message.chat.id, res)
        logger.debug(f"found and listed {len(entries)} entries with tag {tag!r}")
        return
    if len(pos) == 2 and "guest" not in flags:
        tag_name, oid = pos
        tag_name = replace_tag_alias(tag_name)
        entry = next((ent for ent in entries if oid in ent.id), None)
        if entry is None:
            bot.reply_to(message, "Could not find an entry.")
            logger.debug(f"could not find entry with oid {oid}")
            return
        if {"d", "delete"} & flags:
            if tag_name not in entry.tags:
                bot.reply_to(message, f"The entry does not have the tag {tag_name}:")
                logger.debug(f"tag {tag_name!r} not found in entry {entry.id}")
                return
            entry.tags.remove(tag_name)
            Mongo.update_entry(entry)
            bot.send_message(message.chat.id, f"Tag removed:\n{format_entry(entry)}")
            logger.debug(f"removed tag {tag_name!r} from entry {entry.id}")
            return
        entry.tags.add(tag_name)
        Mongo.update_entry(entry)
        bot.send_message(message.chat.id, f"Tag added:\n{format_entry(entry)}")
        logger.debug(f"added tag {tag_name!r} to entry {entry.id}")
        return
    bot.reply_to(message, "Too many arguments.")
    logger.debug("too many positional arguments")

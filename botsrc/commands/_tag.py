import telebot

from src.obj.entry import build_tags
from src.parser import Flags, PositionalArgs
from src.utils.utils import replace_tag_alias
from src.mongo import Mongo
from botsrc.utils import list_many_entries, format_entry


def tag(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    pos: PositionalArgs,
    flags: Flags,
):
    entries = Mongo.load_entries()
    tags = build_tags(entries)
    if not pos:
        msg = "Tags:\n" + "\n".join(
            f"{tag:<18} {len(entries)}"
            for tag, entries in sorted(
                tags.items(), key=lambda x: len(x[1]), reverse=True
            )
        )
        bot.send_message(message.chat.id, msg)
        return
    if len(pos) == 1:
        tag = replace_tag_alias(pos[0])
        if (entries := tags.get(tag)) is None:
            bot.send_message(message.chat.id, f"Tag {tag} not found.")
            return
        res = list_many_entries(
            entries,
            "verbose" in flags,
            "oid" in flags,
            override_title=f"{len(entries)} entries with tag {tag!r}",
        )
        bot.send_message(message.chat.id, res)
        return
    if len(pos) == 2 and "guest" not in flags:
        tag_name, oid = pos
        tag_name = replace_tag_alias(tag_name)
        entry = next((ent for ent in entries if oid in str(ent._id)), None)
        if entry is None:
            bot.reply_to(message, "Could not find an entry.")
            return
        if {"d", "delete"} & flags:
            if tag_name not in entry.tags:
                bot.reply_to(message, f"The entry does not have the tag {tag_name}:")
                return
            entry.tags.remove(tag_name)
            Mongo.update_entry(entry)
            bot.send_message(message.chat.id, f"Tag removed:\n{format_entry(entry)}")
            return
        entry.tags.add(tag_name)
        Mongo.update_entry(entry)
        bot.send_message(message.chat.id, f"Tag added:\n{format_entry(entry)}")
        return
    bot.reply_to(message, "Too many arguments.")

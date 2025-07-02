import logging
import io
import json
import zipfile

import telebot

from src.parser import Flags
from src.paths import LOGS_DIR


logger = logging.getLogger(__name__)


def logs(
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    flags: Flags,
):
    if not LOGS_DIR.exists():
        bot.reply_to(message, "Logs folder does not exist.")
        return

    if not any(LOGS_DIR.iterdir()):
        bot.reply_to(message, "Logs folder is empty.")
        return

    if "full" not in flags:
        log_files = sorted(
            LOGS_DIR.glob("log.jsonl*"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not log_files:
            bot.send_message(message.chat.id, "No .jsonl log files found.")
            return

        latest_log = log_files[0]

        try:
            lines = latest_log.read_text(encoding="utf-8").splitlines()
            last_lines = lines[-10:]
            parsed_lines = []
            for line in last_lines:
                try:
                    log_entry = json.loads(line)
                    level = log_entry.get("level", "?")
                    filename = log_entry.get("filename", "?")
                    func = log_entry.get("function", "?")
                    lineno = log_entry.get("line", "?")
                    timestamp = log_entry.get("timestamp", "?")
                    message_text = log_entry.get("message", "?").strip()
                    parsed_lines.append(
                        f"[{level}][{filename}:{func}][L{lineno}]({timestamp}): {message_text}"
                    )
                except json.JSONDecodeError:
                    parsed_lines.append(f"(Could not parse line: {line[:50]}...)")
        except Exception as e:
            bot.send_message(message.chat.id, f"Error reading log file: {e}")
            return

        if not parsed_lines:
            bot.send_message(message.chat.id, "Log file is empty.")
        else:
            output = "\n".join(parsed_lines)
            bot.send_message(
                message.chat.id,
                f"*Last 10 log entries from `{latest_log.name}`:*\n\n{output}",
                parse_mode="Markdown",
            )
        return

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in LOGS_DIR.rglob("*"):
            if file_path.is_file():
                zip_file.write(file_path, arcname=file_path.relative_to(LOGS_DIR))

    zip_buffer.seek(0)

    bot.send_document(
        message.chat.id,
        zip_buffer,
        caption="Here are the log files",
        visible_file_name="logs.zip",
    )

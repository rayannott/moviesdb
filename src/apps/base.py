import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable

from rich.console import Console

from src.parser import Flags, KeywordArgs, ParsingError, PositionalArgs, parse
from src.utils.help_utils import get_rich_help, parse_docstring
from src.utils.utils import possible_match

logger = logging.getLogger(__name__)


DEFAULT_COMMAND_ALIASES: dict[str, str] = {"clear": "cls"}

# TODO more logging in this module


class BaseApp(ABC):
    def __init__(
        self,
        cns: Console,
        input_fn: Callable[[str], str],
        prompt_str: str,
    ):
        self.cns = cns
        self.input = input_fn
        self.prompt_str = prompt_str
        self.running = True
        self.command_methods: dict[
            str, Callable[[PositionalArgs, KeywordArgs, Flags], None]
        ] = {
            method_name[4:]: getattr(self, method_name)
            for method_name in dir(self)
            if method_name.startswith("cmd_")
        }
        self.help_messages = {
            cmd_root: parse_docstring(cmd_fn.__doc__)
            for cmd_root, cmd_fn in self.command_methods.items()
        }
        self.register_aliases(DEFAULT_COMMAND_ALIASES)

    def register_aliases(self, aliases: dict[str, str]):
        for alias, command in aliases.items():
            self.command_methods[alias] = self.command_methods[command]
            self.help_messages[alias] = self.help_messages[command]

    def cmd_exit(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """exit
        Exit the books subapp."""
        self.running = False

    def cmd_help(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """help [<command>]
        Show help for the given command.
        If no argument is given, show for all.
        Note: 'help <cmd>' is equivalent to '<cmd> --help'."""
        query = pos[0] if pos else None
        self.cns.print(get_rich_help(query, self.help_messages))

    def cmd_cls(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """cls | clear
        Clear the console."""
        os.system("cls" if os.name == "nt" else "clear")
        self.header()

    def error(self, text: str):
        self.cns.print(f" {text}", style="bold red")

    def warning(self, text: str):
        self.cns.print(f" {text}", style="bold yellow")

    def _maybe_command(self, root):
        maybe = possible_match(root, set(self.command_methods))
        self.error(
            f'Invalid command: "{root}". '
            + (f'Did you mean: "{maybe}"? ' if maybe else "")
            + 'Type "help" for a list of commands'
        )

    def process_command(self, command: str):
        try:
            root, pos, kwargs, flags = parse(command)
        except ParsingError as e:
            self.error(f"{e}: {command!r}")
            logger.info(f"parsing error: {e} for command {command!r}")
            return
        command_method = self.command_methods.get(root)
        if command_method is None:
            self._maybe_command(root)
            return
        if "help" in flags:
            self.cmd_help([root], {}, set())
            return
        command_method(pos, kwargs, flags)
        logger.info(f"executed command: {root=!r}, {pos=!r}, {kwargs=!r}, {flags=!r}")

    def run(self):
        logger.info("starting App")
        self.pre_run()
        while self.running:
            try:
                command = self.input(self.prompt_str + " ")
                self.process_command(command)
            except EOFError:
                print()
                return
            except KeyboardInterrupt:
                return
            except Exception as _:
                self.cns.print_exception()
                logger.error("unhandled exception", exc_info=True)
        logger.info("stopping App")
        self.post_run()

    def pre_run(self):
        """Prepare the application to run."""
        self.header()

    def post_run(self):
        """Clean up the application after it has run."""
        pass

    @abstractmethod
    def header(self):
        """Show the application header."""
        pass

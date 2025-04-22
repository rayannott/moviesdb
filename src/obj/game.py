import random
import time
from statistics import mean, stdev
from typing import Callable

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from src.obj.entry_group import EntryGroup
from src.utils.rich_utils import comparison


class GuessingGame:
    def __init__(
        self,
        groups: list[EntryGroup],
        cns: Console,
        input_fn: Callable[[str], str],
    ):
        self.groups = groups
        self.cns = cns
        self.input = input_fn
        self.total = 0
        self.points = 0.0
        self.times_guess_ratings: list[float] = []
        self.times_binary_guess: list[float] = []
        self.binary_guesses: list[bool] = []

    def run(self):
        self.cns.print(
            "Which movie has the higher average rating? "
            "Type [bold blue]1[/] for the first one, or [bold blue]2[/] for the second one. "
            'Type "exit" to quit.'
        )
        while True:
            if self.total - self.points >= 4.0:
                self.cns.print("You've lost...", style="bold red")
                break
            if self.points - self.total >= 2.0:
                self.cns.print("You've won!", style="bold green")
                break

            group1, group2 = random.choice(self.groups), random.choice(self.groups)
            rating1, rating2 = group1.mean_rating, group2.mean_rating

            if group1.title == group2.title or rating1 == rating2:
                continue

            # guess the rating
            if self.total % 5 == 4:
                self.total += 1
                try:
                    t0 = time.time()
                    ans = float(
                        self.input(f"Guess the rating of [cyan]{group1.title!r}[/]: ")
                    )
                    self.times_guess_ratings.append(time.time() - t0)
                except ValueError:
                    self.cns.print("Invalid input", style="red")
                    continue
                if abs(ans - rating1) < 0.01:
                    self.cns.print("Perfect!", end=" ", style="bold green")
                    self.points += 2.0
                elif abs(ans - rating1) < 0.11:
                    self.cns.print("Yes!", end=" ", style="green")
                    self.points += 1.6
                elif abs(ans - rating1) < 0.41:
                    self.cns.print("Close!", end=" ", style="yellow")
                    self.points += 1.2
                else:
                    self.cns.print("Nope!", end=" ", style="red")
                self.cns.print(f"Actually, {rating1:.3f}.")
                continue

            # binary guess
            self.cns.print(
                Align(
                    comparison(
                        Panel(Text(group1.title, style="bold blue")),
                        Panel(Text(group2.title, style="bold blue")),
                    ),
                    align="center",
                    vertical="middle",
                ),
            )
            _inp_col = (
                "yellow"
                if self.points < self.total
                else "green"
                if self.points > self.total
                else "white"
            )
            t0 = time.time()
            answer = Prompt.ask(
                f"[{_inp_col}]{self.points:.1f}/{self.total}[/]>",
                console=self.cns,
                choices=["1", "2", "exit"],
            )
            self.times_binary_guess.append(time.time() - t0)
            if answer == "exit":
                break
            if (rating1 > rating2) == (answer == "1"):
                self.cns.print("Correct!", end=" ", style="bold green")
                self.points += 1.1
                self.binary_guesses.append(True)
            else:
                self.cns.print("Wrong!", end=" ", style="bold red")
                self.binary_guesses.append(False)
            self.total += 1
            self.cns.print(f"[blue]{rating1:.3f}[/] vs. [blue]{rating2:.3f}[/]")

        self.show_results()

    def show_results(self):
        self.cns.print(f"Score: {self.points:.1f}/{self.total}")
        if len(self.times_guess_ratings) > 1:
            self.cns.print(
                f"guess ratings time: {mean(self.times_guess_ratings):.3f} \u00b1 {stdev(self.times_guess_ratings):.3f} sec"
            )
        if len(self.times_binary_guess) > 1:
            self.cns.print(
                f"what is higher time: {mean(self.times_binary_guess):.3f} \u00b1 {stdev(self.times_binary_guess):.3f} sec"
            )
            self.cns.print(
                f"binary guesses: {self.binary_guesses.count(True)}/{len(self.binary_guesses)}"
                f" ({self.binary_guesses.count(True) / len(self.binary_guesses):.2%})"
            )

#!/usr/bin/env python3

# Copyright 2026 Panagiotis Ktistakis <panktist@gmail.com>
#
# This file is part of passata.
#
# passata is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# passata is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with passata.  If not, see <http://www.gnu.org/licenses/>.

"""Generate a wordlist using a Markov chain model."""

import random
import sys
from collections import defaultdict, deque
from pathlib import Path

import click

ORDER = 2
START = "^"
END = "$"


def load_training_words(wordpath: Path) -> list[str]:
    """Load and filter words from a dictionary file."""
    if not wordpath.exists():
        message = f"Dictionary file '{wordpath}' not found."
        raise sys.exit(message)

    return [
        stripped_word.lower()
        for word in wordpath.open()
        if (stripped_word := word.strip()).isalpha()
    ]


def build_model(words: list[str]) -> defaultdict[str, list[str]]:
    """Build a Markov model from the given list of words."""
    model: defaultdict[str, list[str]] = defaultdict(list)
    prefix = START * ORDER
    for word in words:
        w = f"{prefix}{word}{END}"
        for i in range(len(w) - ORDER):
            state = w[i : i + ORDER]
            nxt = w[i + ORDER]
            model[state].append(nxt)

    return model


def generate_word(
    model: defaultdict[str, list[str]],
    min_length: int,
    max_length: int,
) -> str:
    """Generate a single word using the Markov model."""
    while True:
        state = deque(START * ORDER, maxlen=ORDER)
        chars = []
        while True:
            options = model["".join(state)]
            next_char = random.choice(options)  # noqa: S311
            if next_char == END:
                break
            chars.append(next_char)
            state.append(next_char)

        word = "".join(chars)
        if min_length <= len(word) <= max_length:
            return word


def generate_wordlist(
    size: int,
    model: defaultdict[str, list[str]],
    outfile: Path,
    min_length: int,
    max_length: int,
) -> None:
    """Generate n unique random words and save them to a file."""
    unique_words = set()

    with click.progressbar(length=size, label="Generating random words") as bar:
        while len(unique_words) < size:
            current_size = len(unique_words)
            word = generate_word(model, min_length, max_length)
            unique_words.add(word)
            new_size = len(unique_words)
            if new_size > current_size:
                bar.update(1)

    with outfile.open("w") as f:
        f.writelines(f"{word}\n" for word in sorted(unique_words))


@click.command(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "max_content_width": 100,
    },
)
@click.option(
    "--min-length",
    default=3,
    show_default=True,
    help="Minimum word length",
)
@click.option(
    "--max-length",
    default=7,
    show_default=True,
    help="Maximum word length",
)
@click.option(
    "-e",
    "--entropy",
    default=18,
    show_default=True,
    help="Bits of entropy per word",
)
@click.option(
    "-o",
    "--outfile",
    default="markov.txt",
    type=click.Path(dir_okay=False, path_type=Path),
    show_default=True,
    help="Path of output file",
)
def cli(min_length: int, max_length: int, entropy: int, outfile: Path) -> None:
    """Generate a wordlist using a Markov chain model.

    Builds a model from /usr/share/dict/words to generate
    pronounceable-looking random words. The number of words is determined
    by the desired entropy. The final list of unique words is sorted and
    saved to the output file.
    """
    wordpath = Path("/usr/share/dict/words")
    training_words = load_training_words(wordpath)
    model = build_model(training_words)
    size = 2**entropy
    generate_wordlist(size, model, outfile, min_length, max_length)


if __name__ == "__main__":
    cli()

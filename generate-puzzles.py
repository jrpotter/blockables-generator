import aiohttp
import argparse
import asyncio
import datetime
import glob
import json
import os
import random
import sys
import time
import urllib.request

from collections import OrderedDict
from functools import reduce
from multiprocessing import Pool
from typing import Dict, List, NamedTuple, Optional, Set, Tuple
from utils import load_env_file


# LLM settings
ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# ANSI escaped logging tags.
ERROR = "\033[0;31m[ERROR]\033[0m"
INFO = "\033[0;36m[INFO]\033[0m"
SUCCESS = "\033[0;32m[SUCCESS]\033[0m"
WARN = "\033[0;33m[WARN]\033[0m"

# The unique colors used in previous puzzles. Refer to `analyze-puzzles`.
# Every Blockable's top left square should be indigo blue.
CLUE_COLORS = (
    [
        "#7C93CB",  # Indigo Blue, must be first
    ]
    + random.sample(
        [
            "#B86BAC",  # Light Purple/Pink
            "#E6B0D1",  # Pink
            "#F3F1A0",  # Yellow
            "#F5C146",  # Orange
            "#EE7B8C",  # Red
            "#A9D594",  # Green
        ],
        k=6,
    )
    + [
        "#A1DBE3",  # Light Blue, Gus's least favorite. Must be last.
    ]
)

# A subset of all categories used previously. Only include those
# that have been used at least 1% of the time.
CATEGORIES: OrderedDict[str, float] = OrderedDict(
    [
        ("Activity", 24.17),
        ("Actor and Role", 1.963),
        ("Before and After", 1.35),
        ("Book and Author", 0.2454),
        ("Character", 0.4908),
        ("Clothing", 1.227),
        ("Event", 1.595),
        ("Events", 1.35),
        ("Famous Character", 3.313),
        ("Famous Person", 9.08),
        ("Film & TV", 1.227),
        ("Food and Drink", 13.1327),
        ("Living Thing", 0.7362),
        ("Living Things", 1.227),
        ("People", 2.577),
        ("Person", 4.172),
        ("Place", 2.822),
        ("Song and Artist", 1.35),
        ("Thing", 7.975),
        ("Things", 5.89),
    ]
)

# The distribution of clue lengths from 2023-05-26 to 2025-08-17.
# Refer to `analyze-puzzles`.
CLUE_LENGTH_DISTRIB: OrderedDict[int, float] = OrderedDict(
    [
        (1, 2.49),
        (2, 18.88),
        (3, 36.91),
        (4, 25.39),
        (5, 10.13),
        (6, 4.23),
        (7, 1.39),
        (8, 0.40),
        (9, 0.18),
    ]
)
assert abs(sum(CLUE_LENGTH_DISTRIB.values()) - 100) < 1e-6

# The distribution of clue counts per puzzle from 2023-05-26 to 2025-08-17.
# Refer to `analyze-puzzles`.
PUZZLE_CLUE_COUNT_DISTRIB: OrderedDict[int, float] = OrderedDict(
    [
        (5, 0.25),
        (6, 12.64),
        (7, 51.04),
        (8, 36.07),
    ]
)
assert abs(sum(PUZZLE_CLUE_COUNT_DISTRIB.values()) - 100) < 1e-6

# All known words. A grid partition is considered valid if every
# same-colored square can be traversed to form a word in this set.
WORD_BANK: Set[str] = set()
with open("data/words.txt", "r") as f:
    for line in f:
        word = line.upper().strip()
        if len(word) in CLUE_LENGTH_DISTRIB:
            WORD_BANK.add(word)


def glob_recent_phrases(count: int) -> List[str]:
    recent = []
    for filename in glob.glob("generated/*.json"):
        with open(filename, "r") as f:
            data = json.load(f)[0]
            recent.append((data["created_at"], data["phrase"]))

    recent.sort(key=lambda entry: entry[0])
    return [v for [_, v] in recent][-count:]


def collapse_phrase(phrase: str) -> str:
    """Remove all whitespace and punctuation from capitalized argument.

    >>> collapse_phrase("Paint the fence bright yellow.")
    PAINTTHEFENCEBRIGHTYELLOW
    """
    return "".join(map(lambda p: p.upper(), filter(lambda p: p.isalpha(), phrase)))


async def async_llm_pause():
    sleep_secs = random.random() * 10 + 5
    print(f"{ERROR} Unexpected response. Pause for {sleep_secs} seconds...")
    await asyncio.sleep(sleep_secs)


def llm_pause():
    sleep_secs = random.random() * 10 + 5
    print(f"{ERROR} Unexpected response. Pause for {sleep_secs} seconds...")
    time.sleep(sleep_secs)


async def llm_generate_phrases(phrase_queue: asyncio.Queue, env: Dict[str, str]):
    headers = {
        "x-api-key": env[ANTHROPIC_API_KEY],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            category = random.choices(
                population=list(CATEGORIES.keys()),
                weights=list(CATEGORIES.values()),
                k=1,
            )[0]

            recently_generated = "\n".join(
                # Spacing to match injection into prompt.
                map(lambda p: "    - " + p, glob_recent_phrases(100))
            )

            payload = {
                "model": "claude-sonnet-4-20250514",
                "temperature": 1.0,
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "assistant",
                        "content": """
You are an incredibly adept tool for building high quality crossword puzzles.
""",
                    },
                    {
                        "role": "user",
                        "content": f"""
# Instructions

Generate a number of short statements and/or phrases. These should satisfy the following criteria:

- The primary subject of each utterance MUST fit category "{category}".
- Each utterance MUST be EXACTLY 25 letters in length, excluding whitespace and/or punctuation.
    - That is, the following Python expression should return `True`: `len([c for c in utterance if c.isalpha()]) == 25`
- Utterances should be as independent of one another as possible.
- Exclude trailing punctuation.
- All verbs MUST be in present tense.
- All utterances MUST be present participle.
- Be as creative as possible.
- Absolutely DO NOT reuse a phrase you've generated before. You have recently generated the following:
{recently_generated}

# Output
 
Do not format your response in any way.
Return plain text containing the phrases, written one line after another.

# Examples

## Category "Activity"

Ascending Mount Kilimanjaro
Taking a shower after a bad day
Raising an independent child
Sipping red wine in a vineyard
Smuggling candy into a cinema
Flying over the Pacific Ocean

## Category "Things"

Missing jigsaw puzzle pieces
Tyrannosaurus rex skeletons
Floor to ceiling bookshelves
Heartwarming greeting cards
Jaw-dropping acrobatic stunt

## Category "Famous People"

Venetian explorer Marco Polo
George Clooney as Danny Ocean
Hockey prodigy Wayne Gretzky
Jeremy Allen White in "The Bear"
Filmmaker Christopher Nolan

## Category "Famous Quote"

"Scooby Dooby Doo, where are you?"
"I've got blisters on my fingers!"
"Senator, you're no Jack Kennedy"

# Implicit Rules

Some categories have implicit rules.
If generating for any of the following categories, the utterances MUST obey the following rules:

- "Activity" always started with the present participle form of the verb or an adverb.
    - e.g. Sloppily refolding a road map, Raising an independent child, etc.
- "Famous Person" generally starts with a descriptor followed by the person.
    - e.g. Actress Helena Bonham Carter, Performer Bernadette Peters, etc.
- "Actor and Role" generally takes the form of "ACTOR as ROLE".
    - e.g. Robert Preston as Harold Hill, Steve Carell as Michael Scott
- "Song and Artist" generally take the form of "SONG by ARTIST".
    - e.g. "Lavender Haze" by Taylor Swift, "If I Can Dream" by Elvis Presley, etc.
- "Before and After" are two phrases glued together.
    - e.g. Independence day care center, Tony Soprano saxophone solos, etc.
""",
                    },
                ],
            }

            async with session.post(ANTHROPIC_API_URL, json=payload) as response:
                data = await response.json()

                if "content" not in data:
                    await async_llm_pause()
                    continue

                contents = map(
                    lambda c: c.strip(), data["content"][0]["text"].split("\n")
                )
                for entry in contents:
                    collapsed = collapse_phrase(entry)
                    if len(collapsed) == 25:
                        await phrase_queue.put((entry, category))


def llm_generate_clue(word: str, env: Dict[str, str]):
    request = urllib.request.Request(ANTHROPIC_API_URL)
    request.add_header("x-api-key", env[ANTHROPIC_API_KEY])
    request.add_header("anthropic-version", "2023-06-01")
    request.add_header("content-type", "application/json")

    while True:
        response = urllib.request.urlopen(
            request,
            data=json.dumps(
                {
                    "model": "claude-sonnet-4-20250514",
                    "temperature": 1.0,
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": """
You are an incredibly adept tool for building high quality crossword puzzles.
""",
                        },
                        {
                            "role": "user",
                            "content": f"""
# Instructions

- Generate a crossword clue for the word "{word}".
- The clue should be in the style of classic NY times crossword puzzles.
- Do not make the clue too easy or too hard.
- Favor clues that perform some level of wordplay.
- In cases of especially obscure words, use abbreviations.

# Output

Do not format your response in any way.
Return a plain text response with just the clue.

# Examples

- Word: JCN
  Clue: "Journal of Comparative Neurology, abbr."
- Word: ARE
  Clue: "___ we there yet?"
- Word: ART
  Clue: Singer Garfunkel or pianist Tatum
- Word: POM
  Clue: Double it for a cheerleader's prop
- Word: PLAN
  Clue: Course of action sometimes distinguished by a letter
- Word: SWANS
  Clue: Waterfowl which symbolize beauty in European fairy tales
- Word: RINKY
  Clue: "_____-dink: old-fashioned, worn-out"
- WORD: RUDE
  Clue: Impolite
- Word: CIR
  Clue: Citywide Immunization Registry, abbr.
- Word: SIN
  Clue: Sloth, greed, or wearing white after Labor Day (to some)
- Word: LIN
  Clue: ___ Manuel Miranda, creator of \"Hamilton\"
""",
                        },
                    ],
                }
            ).encode(),
        ).read()

        data = json.loads(response.decode())
        if "content" not in data:
            llm_pause()
            continue

        return data["content"][0]["text"]


Layout = List[List[str]]
Coloring = List[List[int]]
Ordering = List[Tuple[int, int]]


def layout_grid(phrase: str) -> Tuple[Layout, Layout]:
    cp = collapse_phrase(phrase)
    assert len(cp) == 25

    clockwise = [
        [cp[20], cp[21], cp[22], cp[23], cp[24]],
        [cp[19], cp[6], cp[7], cp[8], cp[9]],
        [cp[18], cp[5], cp[0], cp[1], cp[10]],
        [cp[17], cp[4], cp[3], cp[2], cp[11]],
        [cp[16], cp[15], cp[14], cp[13], cp[12]],
    ]

    counterclockwise = clockwise[::-1]

    if random.randint(0, 1) == 0:
        return clockwise, counterclockwise
    else:
        return counterclockwise, clockwise


def find_color_ordering(layout, coords) -> Optional[Ordering]:
    """Find a visit order that produces a valid word."""

    def dfs(current, so_far, remaining):
        if len(remaining) == 0:
            word = "".join([layout[i][j] for (i, j) in so_far])
            if word in WORD_BANK:
                return so_far
            else:
                return None

        for rem in remaining:
            if abs(rem[0] - current[0]) <= 1 and abs(rem[1] - current[1]) <= 1:
                result = dfs(rem, so_far + [rem], remaining.difference(set([rem])))
                if result:
                    return result

        return None

    copy = coords.copy()
    random.shuffle(copy)
    return dfs(copy[0], [copy[0]], set(copy[1:]))


def get_coord_at(grid: List[List[int]], index: Tuple[int, int]) -> Optional[int]:
    if index[0] < 0 or index[0] >= len(grid):
        return None
    if index[1] < 0 or index[1] >= len(grid[index[0]]):
        return None
    return grid[index[0]][index[1]]


def set_coord_to(grid: List[List[int]], index: Tuple[int, int], value: int):
    grid[index[0]][index[1]] = value


def partition_grid(clue_lengths: List[int], layout: Layout):
    """Attempt to find a valid coloring."""
    assert sum(clue_lengths) == 25

    # For example, @clue_lengths = [3, 2, 4] results in:
    # [0, 0, 0, 1, 1, 2, 2, 2, 2].
    color_map = reduce(
        lambda acc, next: acc + next,
        map(lambda c: [c[0]] * c[1], enumerate(clue_lengths)),
    )
    assert len(color_map) == 25

    # Nonnegative numbers indicate a color.
    coloring = [
        [-1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1],
        [-1, -1, -1, -1, -1],
    ]

    # Contains the order the blocks of a given color should be traversed.
    orderings: Dict[int, Ordering] = {}

    # The outer stack corresponds to each word. An inner stack
    # corresponds to the blocks traversed per-word.
    class Entry(NamedTuple):
        coord: Tuple[int, int]
        candidates: Set[Tuple[int, int]]

    partition = [[Entry(coord=(0, 0), candidates=set([(0, 1), (1, 0), (1, 1)]))]]

    def unwind():
        word = partition[-1]
        letter = word.pop()
        set_coord_to(coloring, letter.coord, -1)
        if len(word) == 0:
            partition.pop()

    while partition:
        word = partition[-1]
        letter = word[-1]
        index = sum(map(len, partition)) - 1

        set_coord_to(coloring, letter.coord, color_map[index])

        # Indicates this is the last letter of the word.
        word_boundary = len(word) == clue_lengths[len(partition) - 1]

        if word_boundary:
            ordering = find_color_ordering(layout, [w.coord for w in word])
            if ordering:
                orderings[color_map[index]] = ordering
            else:
                unwind()
                continue

            if index + 1 == 25:
                return coloring, orderings

        if len(letter.candidates) == 0:
            unwind()
            continue

        next_coord = random.choice(list(letter.candidates))
        letter.candidates.remove(next_coord)

        next_candidates: Set[Tuple[int, int]] = set()
        for i, j in [(x, y) for x in [-1, 0, 1] for y in [-1, 0, 1]]:
            if i == 0 and j == 0:
                continue
            nc = (next_coord[0] + i, next_coord[1] + j)
            if get_coord_at(coloring, nc) == -1:
                next_candidates.add(nc)

        entry = Entry(coord=next_coord, candidates=next_candidates)
        if word_boundary:
            partition.append([entry])
        else:
            word.append(entry)

    return None


def write_puzzle(
    phrase: str,
    category: str,
    layout: Layout,
    coloring: Coloring,
    orderings: Dict[int, Ordering],
    env: Dict[str, str],
):
    now = datetime.datetime.now(datetime.UTC)

    clues = []
    for color, ordering in orderings.items():
        word = "".join(layout[entry[0]][entry[1]] for entry in ordering)
        clues.append(
            {
                "color": CLUE_COLORS[color % len(CLUE_COLORS)],
                "clue": llm_generate_clue(word, env),
                "ordinal": color + 1,
                "reveal": word,
            }
        )

    grid_colors = []
    for i, row in enumerate(coloring):
        new_row = []
        for j, col in enumerate(row):
            new_row.append(
                CLUE_COLORS[get_coord_at(coloring, (i, j)) % len(CLUE_COLORS)]
            )
        grid_colors.append(new_row)

    number_placements = {}
    for color, ordering in orderings.items():
        number_placements[color + 1] = [
            ordering[0][0],
            ordering[0][1],
        ]

    puzzle = {
        "created_at": datetime.datetime.strftime(
            now,
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ),
        "category": category,
        "clues": clues,
        "direction": "right",
        "grid": str(layout).replace("'", '"'),
        "gridColors": str(grid_colors).replace("'", '"'),
        "numberPlacements": number_placements,
        # "ordinal": 1,
        "phrase": phrase,
        "author": {"link": "", "name": ""},
        # "date": "2023-05-26",
        # "id": uuid4(),
        "dimension": 5,
    }

    with open(f"generated/{collapse_phrase(phrase)}.json", "w") as f:
        json.dump([puzzle], f, indent=4)


def make_blockable(phrase: str, category: str, retries: int, env: Dict[str, str]):
    print(f'{INFO} Building "{phrase}"')

    for i in range(retries):
        puzzle_clue_count = random.choices(
            population=list(PUZZLE_CLUE_COUNT_DISTRIB.keys()),
            weights=list(PUZZLE_CLUE_COUNT_DISTRIB.values()),
            k=1,
        )[0]

        clue_lengths: List[int] = []
        while sum(clue_lengths) != 25:
            clue_lengths = random.choices(
                population=list(CLUE_LENGTH_DISTRIB.keys()),
                weights=list(CLUE_LENGTH_DISTRIB.values()),
                k=puzzle_clue_count,
            )

        for layout in layout_grid(phrase):
            partition = partition_grid(clue_lengths, layout)
            if partition is None:
                continue

            coloring, orderings = partition
            write_puzzle(phrase, category, layout, coloring, orderings, env)

            print(f'{SUCCESS} Written "{phrase}"')
            return

    print(f'{WARN} Failed "{phrase}"')


async def main(jobs: int, retries: int, env: Dict[str, str]):
    # The maxsize here is important to throttle the number of
    # phrase generation requests we make to the LLM.
    phrase_queue: asyncio.Queue = asyncio.Queue(maxsize=jobs * 2)
    asyncio.create_task(llm_generate_phrases(phrase_queue, env))

    with Pool(processes=jobs) as pool:
        while True:
            phrase, category = await phrase_queue.get()
            pool.apply_async(make_blockable, (phrase, category, retries, env))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="generate-puzzles",
        description="Generate Blockable puzzles",
    )
    parser.add_argument("-j", "--jobs", default=0, type=int)
    parser.add_argument("-r", "--retries", default=20, type=int)

    args = parser.parse_args()
    jobs = max(0, args.jobs) or os.process_cpu_count() or 1
    retries = max(0, args.retries) or 20

    try:
        env = load_env_file()
        if ANTHROPIC_API_KEY not in env:
            sys.stderr.write(
                f"{ERROR} Missing {ANTHROPIC_API_KEY} environment variable\n"
            )
            sys.exit(1)
    except FileNotFoundError:
        sys.stderr.write(f"{ERROR} Could not find .env file\n")
        sys.exit(1)

    asyncio.run(main(jobs, retries, env))

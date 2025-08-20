import glob
import json

from collections import defaultdict


def average_of(buckets):
    sum = 0
    count = 0
    for key, val in buckets.items():
        sum += key * val
        count += val
    return sum / count


def print_header(header):
    print(f"========== {header.upper()} ==========")


def distrib_of(buckets, header):
    total = sum(buckets.values())
    print_header(header)
    for key, val in sorted(buckets.items()):
        print(f"{key}: {val / total * 100:.4}%")


def main():
    clues_per_puzzle = defaultdict(int)
    clue_lengths = defaultdict(int)
    categories = defaultdict(int)
    unique_colors = set()

    for filename in glob.glob("data/*.json"):
        with open(filename, "r") as f:
            data = json.load(f)[0]

            clues_per_puzzle[len(data["clues"])] += 1
            categories[data["category"]] += 1

            for clue in data["clues"]:
                gridColors = defaultdict(int)
                for side in json.loads(data["gridColors"]):
                    for entry in side:
                        gridColors[entry] += 1
                        unique_colors.add(entry)
                assert sum(gridColors.values()) == 25
                for count in gridColors.values():
                    clue_lengths[count] += 1

    distrib_of(clue_lengths, "Clue Length")
    print(f"Average Clue Length: {average_of(clue_lengths):.4}\n")

    distrib_of(clues_per_puzzle, "Puzzle Clue Count")
    print(f"Average Puzzle Clue Count: {average_of(clues_per_puzzle):.4}\n")

    distrib_of(categories, "Categories")
    print()

    print_header("Unique Colors")
    print("\n".join(unique_colors))


if __name__ == "__main__":
    main()

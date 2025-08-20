# Blockables Generator

Utility scripts for building Blockables puzzles.

## Installation

Create a virtual environment and install the requirements like so:

```bash
$ python3 -m venv venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt
```

You'll need to create a `.env` file like so:

```
ANTHROPIC_API_KEY=<API_KEY>
```

## Generation

The primary script is `generate-puzzle.py`. To run, you must be
within the virtual environment. It's recommended to run unbuffered
like so:

```bash
$ python3 -u generate-puzzle.py -j 4
```

This runs indefinitely, repeatedly attempting to create 25 letter
phrases that can be arranged into a Blockables grid. On success, a
JSON dump is written to the `generated` directory.

## Other Scripts

Included are the following auxiliary scripts:

* `download-puzzles.py`
    - Queries each puzzle from `blockables.app`. Update `.env`
      before running.
* `analyze-puzzles.py`
    - Scans downloaded files and prints basic stats about them.

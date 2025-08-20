import json
import sys
import time
import urllib.request

from datetime import datetime, timedelta
from utils import load_env_file


BLOCKABLES_API_KEY = "BLOCKABLES_API_KEY"
BLOCKABLES_AUTHORIZATION = "BLOCKABLES_AUTHORIZATION"
START_DATE = datetime(2023, 5, 26)
URL = "https://cterwiozjbjdeoazbzdd.supabase.co/rest/v1/puzzles"


def main(apiKey, authorization):
    now = datetime.now()
    end_date = datetime(now.year, now.month, now.day)
    cursor = START_DATE

    while cursor <= end_date:
        try:
            request = urllib.request.Request(
                f"{URL}?select=*&date=eq.{cursor.year:02}-{cursor.month:02}-{cursor.day:02}"
            )
            request.add_header("apikey", apiKey)
            request.add_header("authorization", authorization)
            response = urllib.request.urlopen(request).read()
            with open(
                f"data/{cursor.year:02}-{cursor.month:02}-{cursor.day:02}.json", "w"
            ) as f:
                json.dump(json.loads(response), f, indent=2)
        except RuntimeError as e:
            sys.stderr.write(
                f"Failed on date {cursor.year:02}-{cursor.month:02}-{cursor.day:02}: {e}\n"
            )
        finally:
            cursor += timedelta(days=1)
            time.sleep(5)


if __name__ == "__main__":
    try:
        env = load_env_file()
        for key in [BLOCKABLES_API_KEY, BLOCKABLES_AUTHORIZATION]:
            if key not in env:
                sys.stderr.write(f"Missing {key} environment variable\n")
                sys.exit(1)
    except FileNotFoundError:
        sys.stderr.write("Could not find .env file\n")
        sys.exit(1)

    main(env[BLOCKABLES_API_KEY], env[BLOCKABLES_AUTHORIZATION])

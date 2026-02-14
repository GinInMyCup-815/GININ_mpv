import os
import json
from series_manager import SeriesManager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # путь к папке скрипта
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def main():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    series_profile = config["profiles"]["series"]
    manager = SeriesManager(series_profile)

    manager.play_next()

if __name__ == "__main__":
    main()
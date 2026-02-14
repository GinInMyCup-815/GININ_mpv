import json
import logging
import os

from series_manager import SeriesManager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # путь к папке скрипта
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    series_profile = config["profiles"]["series"]
    manager = SeriesManager(
        series_profile,
        mpv_path=config.get("mpv_path", "mpv"),
        mpv_options=config.get("mpv_options"),
        state_file=os.path.join(SCRIPT_DIR, "state.json"),
        mqtt_config=config.get("mqtt", {}),
    )

    manager.play_next()


if __name__ == "__main__":
    main()

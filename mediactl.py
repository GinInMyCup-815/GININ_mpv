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
    manager_kwargs = {
        "mpv_path": config.get("mpv_path", "mpv"),
        "mpv_options": config.get("mpv_options"),
        "state_file": os.path.join(SCRIPT_DIR, "state.json"),
        "mqtt_config": config.get("mqtt", {}),
    }

    try:
        manager = SeriesManager(series_profile, **manager_kwargs)
    except TypeError as exc:
        if "mqtt_config" not in str(exc):
            raise
        logging.warning(
            "Используется версия SeriesManager без поддержки mqtt_config. MQTT отключен для совместимости."
        )
        manager_kwargs.pop("mqtt_config", None)
        manager = SeriesManager(series_profile, **manager_kwargs)

    manager.play_next()


if __name__ == "__main__":
    main()

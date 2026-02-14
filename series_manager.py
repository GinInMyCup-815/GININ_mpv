import os
import json
from mpv_controller import MPVController

class SeriesManager:
    def __init__(self, profile_config, state_file="state.json"):
        self.source = profile_config["source_folder"]
        self.watched = profile_config["watched_folder"]
        self.autoplay_next = profile_config.get("autoplay_next", True)
        self.state_file = state_file
        self.mpv = MPVController("mpv", ["--fullscreen", ])
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        else:
            self.state = {}

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def get_next_episode(self):
        files = sorted(os.listdir(self.source))
        for f in files:
            if f not in self.state.get("watched", []):
                return os.path.join(self.source, f)
        return None

    def move_to_watched(self, filepath):
        dest = os.path.join(self.watched, os.path.basename(filepath))
        os.rename(filepath, dest)
        self.state.setdefault("watched", []).append(os.path.basename(filepath))
        self.save_state()

    def play_next(self):
        episode = self.get_next_episode()
        if not episode:
            print("Все серии просмотрены")
            return
        self.mpv.start(episode)
        # ждём завершения
        self.mpv.process.wait()
        self.move_to_watched(episode)
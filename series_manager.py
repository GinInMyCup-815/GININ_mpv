import json
import logging
import os
import shutil
import time

from mpv_controller import MPVController
from mqtt_bridge import MqttBridge

logger = logging.getLogger(__name__)


class SeriesManager:
    COMPLETE_THRESHOLD = 0.95

    def __init__(self, profile_config, mpv_path="mpv", mpv_options=None, state_file="state.json", mqtt_config=None):
        self.source = profile_config["source_folder"]
        self.watched = profile_config["watched_folder"]
        self.autoplay_next = profile_config.get("autoplay_next", True)
        self.audio_track = profile_config.get("audio_track")
        self.state_file = state_file
        self.mpv = MPVController(mpv_path, mpv_options or ["--fullscreen"])
        self.state = {"progress": {}}
        self.mqtt = MqttBridge(mqtt_config, on_command=self._handle_mqtt_command)
        self.current_episode = None
        self.load_state()

    def load_state(self):
        if not os.path.exists(self.state_file):
            self.state = {"progress": {}}
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                loaded_state = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Не удалось загрузить state-файл %s: %s. Будет создан новый.", self.state_file, exc)
            self.state = {"progress": {}}
            return

        progress = loaded_state.get("progress", {}) if isinstance(loaded_state, dict) else {}
        if not isinstance(progress, dict):
            progress = {}

        self.state = {"progress": progress}

    def save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def _episode_key(self, filepath):
        return os.path.basename(filepath)

    def _get_episode_progress(self, filepath):
        return self.state.get("progress", {}).get(self._episode_key(filepath), {})

    def _set_episode_progress(self, filepath, position=None, duration=None):
        key = self._episode_key(filepath)
        episode_state = self.state.setdefault("progress", {}).setdefault(key, {})
        if position is not None:
            episode_state["position"] = float(position)
        if duration is not None:
            episode_state["duration"] = float(duration)
        self.save_state()

    def _clear_episode_progress(self, filepath):
        key = self._episode_key(filepath)
        self.state.setdefault("progress", {}).pop(key, None)
        self.save_state()

    def get_next_episode(self):
        if not os.path.isdir(self.source):
            logger.error("Папка с сериями не найдена: %s", self.source)
            return None

        entries = sorted(os.listdir(self.source))
        for entry in entries:
            filepath = os.path.join(self.source, entry)
            if os.path.isfile(filepath):
                return filepath
        return None

    def move_to_watched(self, filepath):
        os.makedirs(self.watched, exist_ok=True)
        dest = os.path.join(self.watched, os.path.basename(filepath))
        shutil.move(filepath, dest)
        self._clear_episode_progress(filepath)
        logger.info("Серия перемещена в просмотренные: %s", dest)

    def _get_completion_ratio(self, filepath):
        episode_state = self._get_episode_progress(filepath)
        position = episode_state.get("position")
        duration = episode_state.get("duration")

        if position is None or duration is None or duration <= 0:
            return 0.0
        return min(max(position / duration, 0.0), 1.0)

    def _publish_player_state(self, snapshot):
        if not self.current_episode:
            return

        progress = None
        if snapshot.get("position") is not None and snapshot.get("duration"):
            if snapshot["duration"] > 0:
                progress = max(0.0, min(1.0, snapshot["position"] / snapshot["duration"]))

        payload = {
            "episode": os.path.basename(self.current_episode),
            "position": snapshot.get("position"),
            "duration": snapshot.get("duration"),
            "progress": progress,
            "paused": snapshot.get("paused"),
            "volume": snapshot.get("volume"),
            "timestamp": int(time.time()),
        }
        self.mqtt.publish_state(payload)

    def _persist_current_progress(self, episode, fallback_position=None):
        snapshot = self.mpv.get_playback_snapshot()
        position = snapshot.get("position")
        duration = snapshot.get("duration")

        if position is None and fallback_position is not None:
            position = fallback_position
            snapshot["position"] = position

        if position is None and duration is None:
            return False

        self._set_episode_progress(episode, position=position, duration=duration)
        self._publish_player_state(snapshot)
        return True

    def _handle_mqtt_command(self, command, data):
        # Extension point: add new command handlers here.
        if command == "pause/toggle":
            self.mpv.toggle_pause()
            return
        if command == "pause/set":
            self.mpv.set_pause(bool(data.get("value", True)))
            return
        if command == "seek":
            self.mpv.seek(float(data.get("seconds", 0)))
            return
        if command == "volume/set":
            self.mpv.set_volume(float(data.get("value", 50)))
            return
        if command == "audio/set":
            self.set_audio_track(int(data.get("track", 1)))
            return
        logger.info("MQTT неизвестная команда: %s (%s)", command, data)

    def play_next(self):
        episode = self.get_next_episode()
        if not episode:
            logger.info("Нет доступных серий в папке: %s", self.source)
            return

        self.current_episode = episode
        previous = self._get_episode_progress(episode)
        start_position = previous.get("position", 0)

        logger.info("Запуск серии: %s", os.path.basename(episode))
        if start_position:
            logger.info("Возобновление с таймкода: %.1f сек", start_position)
        if self.audio_track is not None:
            logger.info("Будет использована аудиодорожка #%s", self.audio_track)

        self.mqtt.start()
        self.mpv.start(episode, audio_track=self.audio_track, start_time=start_position)
        logger.info("Ожидание завершения воспроизведения...")

        started_at = time.monotonic()
        warned_no_ipc = False

        while self.mpv.is_running():
            fallback_position = start_position + (time.monotonic() - started_at)
            saved = self._persist_current_progress(episode, fallback_position=fallback_position)
            if not saved and not warned_no_ipc:
                logger.warning("Не удалось получить таймкод через IPC, используется fallback по времени.")
                warned_no_ipc = True
            time.sleep(1)

        fallback_position = start_position + (time.monotonic() - started_at)
        self._persist_current_progress(episode, fallback_position=fallback_position)

        completion = self._get_completion_ratio(episode)
        logger.info("Воспроизведение завершено: %s (прогресс %.1f%%)", os.path.basename(episode), completion * 100)

        if completion >= self.COMPLETE_THRESHOLD:
            self.move_to_watched(episode)
        else:
            logger.info(
                "Серия не перемещена: прогресс меньше %.0f%%. Сохранена позиция продолжения.",
                self.COMPLETE_THRESHOLD * 100,
            )

        self.mqtt.stop()
        self.current_episode = None

    def set_audio_track(self, track_number):
        self.audio_track = track_number
        if self.mpv.is_running():
            return self.mpv.set_audio_track(track_number)
        return {"status": "queued", "audio_track": track_number}

    def cycle_audio_track(self):
        if self.mpv.is_running():
            return self.mpv.cycle_audio_track()
        return {"error": "mpv is not running"}

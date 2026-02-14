import json
import os
import socket
import subprocess


class MPVController:
    def __init__(self, mpv_path, options, ipc_socket="\\\\.\\pipe\\mpvpipe"):
        self.mpv_path = mpv_path
        self.options = options
        self.ipc_socket = ipc_socket
        self.process = None

    def start(self, filepath, audio_track=None, start_time=None):
        cmd = [self.mpv_path] + self.options
        if audio_track is not None:
            cmd.append(f"--aid={audio_track}")
        if start_time is not None and start_time > 0:
            cmd.append(f"--start={start_time}")
        cmd.append(filepath)
        self.process = subprocess.Popen(cmd)

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

    def is_running(self):
        return self.process and self.process.poll() is None

    def _send_unix_socket_command(self, payload):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.ipc_socket)
            s.send(payload)
            data = s.recv(4096)
            return json.loads(data.decode())

    def _send_windows_pipe_command(self, payload):
        # mpv on Windows typically uses named pipes like \\.\pipe\mpvpipe
        with open(self.ipc_socket, "r+b", buffering=0) as pipe:
            pipe.write(payload)
            data = pipe.readline()
            return json.loads(data.decode())

    def _send_command(self, command):
        payload = json.dumps({"command": command}).encode() + b"\n"

        try:
            if self.ipc_socket.startswith("\\\\.\\pipe\\"):
                return self._send_windows_pipe_command(payload)
            if not os.path.exists(self.ipc_socket):
                return {"error": f"IPC socket unavailable: {self.ipc_socket}"}
            return self._send_unix_socket_command(payload)
        except Exception as e:
            return {"error": str(e)}

    def get_property(self, name):
        response = self._send_command(["get_property", name])
        return response.get("data")

    def get_playback_snapshot(self):
        return {
            "position": self.get_property("time-pos"),
            "duration": self.get_property("duration"),
            "paused": self.get_property("pause"),
            "volume": self.get_property("volume"),
        }


    def command(self, *args):
        return self._send_command(list(args))

    def set_property(self, name, value):
        return self._send_command(["set_property", name, value])

    def seek(self, seconds):
        return self.command("seek", float(seconds), "relative")

    def set_pause(self, paused):
        return self.set_property("pause", bool(paused))

    def toggle_pause(self):
        return self.command("cycle", "pause")

    def set_volume(self, volume):
        return self.set_property("volume", float(volume))

    def set_audio_track(self, track_number):
        return self._send_command(["set_property", "aid", track_number])

    def cycle_audio_track(self):
        return self._send_command(["cycle", "audio"])

    def get_status(self):
        return {"position": self.get_property("time-pos")}

import subprocess
import json
import time
import os
import socket

class MPVController:
    def __init__(self, mpv_path, options, ipc_socket="\\\\.\\pipe\\mpvpipe"):
        self.mpv_path = mpv_path
        self.options = options
        self.ipc_socket = ipc_socket
        self.process = None

    def start(self, filepath):
        cmd = [self.mpv_path] + self.options + [filepath]
        self.process = subprocess.Popen(cmd)

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

    def is_running(self):
        return self.process and self.process.poll() is None

    # Пример для опроса состояния через IPC
    def get_status(self):
        if not os.path.exists(self.ipc_socket):
            return {}
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(self.ipc_socket)
                # Запрос позиции и состояния
                s.send(json.dumps({"command": ["get_property", "time-pos"]}).encode() + b"\n")
                data = s.recv(1024)
                pos = json.loads(data.decode())['data']
                return {"position": pos}
        except Exception:
            return {"position": None}
            

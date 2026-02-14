import json
import logging

logger = logging.getLogger(__name__)

try:
    import paho.mqtt.client as mqtt
except Exception:  # pragma: no cover - optional dependency
    mqtt = None


class MqttBridge:
    """MQTT bridge for Home Assistant integration.

    Extension point:
    - add new command handlers into `self._command_handlers`
    - publish extra telemetry fields in `publish_state`
    """

    def __init__(self, config, on_command=None):
        self.config = config or {}
        self.on_command = on_command
        self.enabled = bool(self.config.get("enabled", False))
        self.client = None

        self.base_topic = self.config.get("base_topic", "mediactl/series")
        self.state_topic = f"{self.base_topic}/state"
        self.command_topic = f"{self.base_topic}/command/#"

    def start(self):
        if not self.enabled:
            return
        if mqtt is None:
            logger.warning("MQTT включен в config, но пакет paho-mqtt не установлен")
            return

        self.client = mqtt.Client(client_id=self.config.get("client_id", "mediactl-series"))

        username = self.config.get("username")
        password = self.config.get("password")
        if username:
            self.client.username_pw_set(username, password)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        host = self.config.get("host", "localhost")
        port = int(self.config.get("port", 1883))
        keepalive = int(self.config.get("keepalive", 60))

        self.client.connect(host, port, keepalive)
        self.client.loop_start()
        logger.info("MQTT подключен: %s:%s, base_topic=%s", host, port, self.base_topic)

    def stop(self):
        if not self.client:
            return
        self.client.loop_stop()
        self.client.disconnect()

    def publish_state(self, payload):
        if not self.client:
            return
        self.client.publish(self.state_topic, json.dumps(payload, ensure_ascii=False), qos=0, retain=False)

    def _on_connect(self, client, userdata, flags, rc):  # noqa: ARG002
        if rc == 0:
            client.subscribe(self.command_topic)
            logger.info("MQTT подписка активна: %s", self.command_topic)
        else:
            logger.error("MQTT connect error rc=%s", rc)

    def _on_message(self, client, userdata, msg):  # noqa: ARG002
        if not self.on_command:
            return

        topic = msg.topic
        command = topic.replace(f"{self.base_topic}/command/", "", 1)
        payload = msg.payload.decode("utf-8").strip()

        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            data = {"value": payload}

        self.on_command(command, data)

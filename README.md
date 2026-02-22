# GININ_mpv

## MQTT / Home Assistant (кратко)

1. В `config.json` включите блок `mqtt.enabled=true`, задайте `host`, `port`, `username/password` и `base_topic`.
2. Убедитесь, что установлен пакет `paho-mqtt` (`pip install paho-mqtt`).
3. Скрипт публикует состояние в `<base_topic>/state` (JSON: episode, position, duration, progress, paused, volume).
4. Для управления отправляйте команды в `<base_topic>/command/...`:
   - `pause/toggle`
   - `pause/set` с payload `{"value": true|false}`
   - `seek` с payload `{"seconds": 30}` (или отрицательное значение)
   - `volume/set` с payload `{"value": 40}`
   - `audio/set` с payload `{"track": 1}`
5. В Home Assistant добавьте MQTT sensors и buttons/scripts на эти топики.

Код оставлен расширяемым: добавляйте новые команды в `SeriesManager._handle_mqtt_command()` и новые поля телеметрии в `SeriesManager._publish_player_state()`.

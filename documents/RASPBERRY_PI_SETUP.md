# Raspberry Pi Gateway Setup

This gateway pulls frames from the Imou Ranger RTSP stream, runs motion and face filtering locally, then uploads selected frames to AWS.

## 1. Network

Put the Raspberry Pi and Imou Ranger on the same LAN/WiFi network. Reserve the camera IP address in your router if possible.

## 2. Enable RTSP

In the Imou Life app, enable RTSP from the camera settings. The stream URL is:

```text
rtsp://admin:SAFETY_CODE@CAMERA_IP:554/cam/realmonitor?channel=1&subtype=0
```

Test it from the Pi:

```bash
ffmpeg -i "rtsp://admin:SAFETY_CODE@CAMERA_IP:554/cam/realmonitor?channel=1&subtype=0" -vframes 1 test.jpg
```

## 3. Install Runtime

```bash
sudo apt update
sudo apt install -y python3 python3-pip ffmpeg
cd /home/pi/iot_cloud_home_security/edge
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with `API_ENDPOINT`, `API_KEY`, and `RTSP_URL`.

## 4. Install Service

```bash
sudo cp iot-face-client.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable iot-face-client.service
sudo systemctl start iot-face-client.service
systemctl status iot-face-client.service
```

## 5. Verify

Check the device dashboard for `cam-01`. A healthy stream should report `online`; RTSP/network failures should report `degraded` before the scheduled health check marks the gateway `offline`.

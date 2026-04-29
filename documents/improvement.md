# Enhancement Plan: Outperform the Example Project

**Deployment scope**: 4-5 family members, **Imou Ranger** WiFi IP camera (RTSP), Raspberry Pi as gateway.

---

## User Review Required

> [!IMPORTANT]
> **Hardware change**: The Imou Ranger is a **WiFi IP camera** with RTSP stream — NOT a Pi camera module. The Raspberry Pi acts as a **gateway** that pulls frames from the camera's RTSP stream, runs edge AI, and uploads to AWS. This affects Phase 3 (edge device) significantly.

> [!WARNING]
> The current `edge/` code assumes a directly-connected USB/Pi camera. Phase 3 will add **RTSP capture support** so the Pi can grab frames from the Imou Ranger over the local network.

---

## Phase 1: Backend — Rich Alert State Machine & API Enhancements

**Goal**: Add smart 3-state alert tracking with Telegram dedup + heartbeat API + direct Telegram from process_image.

---

### [MODIFY] [handler.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/backend/lambdas/device_health_check/handler.py)

**Changes:**
- Add **`alert_state`** field tracking: `online` → `degraded` → `offline`
- **Dedup logic**: Don't re-send offline alert if `alert_state` is already `offline`
- Track `last_alert_at` and `last_alert_error_key` in DynamoDB device record
- Send **recovery alert** via SNS when device transitions from `degraded`/`offline` → `online`
- Update `query_devices_handler` to expose: `alert_state`, `is_online`, `last_error`, `camera_device`, `capture_interval_sec`

### [NEW] [heartbeat_handler.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/backend/lambdas/device_health_check/heartbeat_handler.py)

**New Lambda handler** for `POST /api/devices/heartbeat`:
- Accept payload: `{ deviceId, status, captureIntervalSec, cameraDevice, lastCaptureAt, lastError }`
- Implement `evaluate_heartbeat_alert()` state machine:
  - `online → degraded` (new error): send Telegram/SNS alert
  - `degraded → degraded` (same error key): **skip** (dedup)
  - `degraded → degraded` (different error): send alert
  - `degraded/offline → online`: send **recovery** alert
- Persist `alert_state`, `last_alert_at`, `last_alert_error_key` to DynamoDB
- Return `{ ok, device_id, last_seen, alert_state }`

### [MODIFY] [handler.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/backend/lambdas/process_image/handler.py)

**Changes:**
- Add **direct Telegram call** for `stranger` detections (faster than SNS→Lambda chain)
- SNS path remains for Zalo/Email subscribers
- Import a shared `telegram_notify` module (new file)

### [NEW] [telegram_notify.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/backend/lambdas/process_image/telegram_notify.py)

- Lightweight Telegram helper using `urllib.request` (no extra deps)
- `send_telegram_message(text) → bool`
- Reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from env
- Gracefully returns `False` if tokens not configured (non-blocking)

### [MODIFY] [template.yaml](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/infrastructure/template.yaml)

- Add **Parameters**: `TelegramBotToken` (NoEcho), `TelegramChatId`
- Add `HeartbeatFunction` Lambda:
  - Route: `POST /api/devices/heartbeat`
  - CodeUri: `../backend/lambdas/device_health_check/`
  - Handler: `heartbeat_handler.heartbeat_handler`
- Add Telegram env vars to `ProcessImageFunction` and `DeviceHealthCheckFunction`
- Add `telegram_notify.py` to `device_health_check/` as well

---

## Phase 2: Webapp — Live Data, Web Simulator & Enhanced Dashboard

**Goal**: Replace all hardcoded mock data with live AWS API calls, add web simulator and alerts page.

---

### Install Dependencies

```bash
cd webapp && npm install swr
```

### [NEW] Shared Library Files

#### [NEW] [webapp/lib/types.ts](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/lib/types.ts)

TypeScript interfaces for the whole app:

```typescript
interface DetectionEvent {
  deviceId: string;
  timestamp: string;
  status: "known" | "unknown" | "no_face";
  personId: string;
  confidence: number;
  faceCount: number;
  rawImageKey: string;
  thumbnailKey?: string;
}

interface DeviceStatus {
  deviceId: string;
  status: "online" | "degraded" | "offline";
  alertState: string;
  lastSeenAt: string;
  lastError?: string;
  isOnline: boolean;
  cameraDevice?: string;
  captureIntervalSec?: number;
}

interface KnownPerson {
  personId: string;
  personName: string;
  faceId: string;
  s3Key: string;
  createdAt: string;
}
```

#### [NEW] [webapp/lib/api.ts](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/lib/api.ts)

API client: `getPresignedUrl()`, `uploadToS3()`, `registerFace()`, SWR fetcher.

### [NEW] Next.js API Routes (server-side proxy)

These keep `API_KEY` on the server side, never exposed to browser:

| Route File | Proxies To | Method |
|-----------|-----------|--------|
| `app/api/detections/route.ts` | `GET /api/events` | GET |
| `app/api/devices/route.ts` | `GET /api/devices` | GET |
| `app/api/faces/route.ts` | `GET/POST/DELETE /api/collection/faces` | ALL |
| `app/api/upload-url/route.ts` | `POST /api/presigned-url` | POST |
| `app/api/register-face/route.ts` | `POST /api/collection/faces` | POST |

### [MODIFY] Dashboard Pages (Live Data)

#### [MODIFY] [page.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/app/page.tsx) — Main Dashboard

- SWR with 3s auto-refresh for detections, 5s for devices
- Real stats: total detections, known count, stranger count, online devices
- **Alert sound** (audio element) when new stranger detected
- Device heartbeat section with `online`/`degraded`/`offline` indicators
- Loading spinner + error state
- Header link to `/simulate`

#### [MODIFY] [events/page.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/app/events/page.tsx)

- Live data via SWR from `/api/detections`
- **Working filter buttons**: All / Unknown / Known (client-side)
- Thumbnail image preview in each row
- Loading and empty states

#### [MODIFY] [devices/page.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/app/devices/page.tsx)

- Live data from `/api/devices`
- **3-state badges**: online (🟢), degraded (🟡), offline (🔴)
- Show `lastError` in red box when present
- Real stats computed from device data
- Show camera info: `Imou Ranger` model, RTSP connection status

#### [MODIFY] [persons/page.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/app/persons/page.tsx)

- Live data from `/api/faces`
- **Add Person form**: name input + drag-and-drop image upload
  - Upload flow: get presigned URL → upload to S3 → call register face API
  - Designed for **4-5 family members** (show registered member count)
- **Delete button** calls real API
- Show **face photo** from S3 URL

### [NEW] New Pages

#### [NEW] [simulate/page.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/app/simulate/page.tsx) — Web Simulator

Test the pipeline without hardware:
- **Webcam capture**: `getUserMedia` → canvas → capture frame → upload
- **File upload**: drag-and-drop or file picker
- Upload flow: presigned URL → S3 POST → show result
- After upload, poll `/api/detections` to show the detection result
- Status indicator: capturing → uploading → processing → result

#### [NEW] [alerts/page.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/app/alerts/page.tsx) — Alerts Page

- Filter detections by alert type: `stranger`, `degraded`, `offline`, `recovery`
- Timeline view with severity color-coding
- Show Telegram notification status

### [NEW/MODIFY] Components

#### [NEW] [components/DetectionCard.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/components/DetectionCard.tsx)

Reusable card for detection events:
- Thumbnail image, person name or "Stranger" badge
- Confidence progress bar, timestamp, device ID
- Color-coded: green (known), red (stranger), gray (no face)

#### [MODIFY] [Sidebar.tsx](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/components/Sidebar.tsx)

- Add nav items: `🎮 Simulator` → `/simulate`, `🚨 Alerts` → `/alerts`

#### [MODIFY] [globals.css](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/app/globals.css)

- Styles for DetectionCard, simulator webcam view, alerts timeline
- Pulse animation for live indicator
- Degraded (amber) status styles

### [NEW] [webapp/.env.example](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/.env.example)

```env
# Server-side only (never exposed to browser)
API_ENDPOINT=https://your-api-id.execute-api.region.amazonaws.com/dev
API_KEY=your-api-key-here

# Public (used in browser for S3 image URLs)
NEXT_PUBLIC_S3_BUCKET_URL=https://your-bucket.s3.region.amazonaws.com
```

---

## Phase 3: Edge Device — RTSP Capture from Imou Ranger

**Goal**: Adapt the edge device to capture frames from the **Imou Ranger** WiFi camera via RTSP, with the Pi acting as a processing gateway.

> [!IMPORTANT]
> The Imou Ranger provides RTSP at:
> `rtsp://admin:<safety_code>@<camera_ip>:554/cam/realmonitor?channel=1&subtype=0`
> 
> The Pi connects to this stream over WiFi/LAN — no physical camera connection needed.

---

### [MODIFY] [config.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/edge/config.py)

Add RTSP-specific configuration:

```python
@dataclass
class CameraConfig:
    # Camera source type: "rtsp", "picamera", "usb"
    source_type: str = "rtsp"
    
    # RTSP settings (for Imou Ranger)
    rtsp_url: str = ""  # rtsp://admin:SAFETYCODE@192.168.x.x:554/cam/realmonitor?channel=1&subtype=0
    rtsp_transport: str = "tcp"  # tcp or udp
    rtsp_timeout: int = 10       # connection timeout
    rtsp_reconnect_delay: int = 5
    
    # Existing settings
    resolution: tuple[int, int] = (640, 480)
    fps: int = 15
    jpeg_quality: int = 85
```

Load from env:
```
CAMERA_SOURCE_TYPE=rtsp
RTSP_URL=rtsp://admin:SAFETYCODE@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
```

### [MODIFY] [main.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/edge/main.py)

Update `init_camera()` to support 3 capture sources:

```python
def init_camera(config: AppConfig):
    if config.camera.source_type == "rtsp":
        return RTSPCameraWrapper(config.camera)
    elif config.camera.source_type == "picamera":
        # existing Picamera2 code
    else:
        # existing OpenCV USB fallback
```

Add `RTSPCameraWrapper` class:
- Uses `cv2.VideoCapture(rtsp_url)` with TCP transport
- Auto-reconnect on connection loss (with backoff)
- Frame health check (skip black/corrupt frames)
- Configurable grab interval (don't overload the stream)
- Reports degraded status on connection failure

Update heartbeat to include camera model info (`Imou Ranger`).

### [NEW] [edge/rtsp_camera.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/edge/rtsp_camera.py)

Dedicated RTSP camera module:

```python
class RTSPCameraWrapper:
    """Capture frames from Imou Ranger via RTSP stream."""
    
    def __init__(self, config: CameraConfig):
        self.rtsp_url = config.rtsp_url
        self._cap = None
        self._connect()
    
    def _connect(self):
        """Connect/reconnect to RTSP stream."""
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = 
            f"rtsp_transport;{config.rtsp_transport}"
        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        
    def read(self) -> tuple[bool, np.ndarray]:
        """Read a frame, with auto-reconnect."""
        if not self._cap or not self._cap.isOpened():
            self._reconnect()
        ret, frame = self._cap.read()
        if not ret:
            self._reconnect()
            ret, frame = self._cap.read()
        return ret, frame
    
    def _reconnect(self):
        """Reconnect to RTSP with backoff."""
        ...
    
    def release(self):
        if self._cap:
            self._cap.release()
```

Features:
- **Auto-reconnect** with exponential backoff on stream failure
- **Frame validation**: skip solid-color/corrupt frames
- **Connection health**: reports `degraded` if reconnecting frequently
- Environment variable `OPENCV_FFMPEG_CAPTURE_OPTIONS` for transport selection

### [MODIFY] [uploader.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/edge/uploader.py)

- Update heartbeat payload to include `cameraModel: "Imou Ranger"` and `cameraSource: "rtsp"`

### [NEW] [edge/.env.example](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/edge/.env.example)

```env
# Device identity
DEVICE_ID=cam-01

# Cloud API
API_ENDPOINT=https://your-api-id.execute-api.region.amazonaws.com/dev
API_KEY=your-api-key

# Camera: Imou Ranger RTSP
CAMERA_SOURCE_TYPE=rtsp
RTSP_URL=rtsp://admin:YOUR_SAFETY_CODE@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0
RTSP_TRANSPORT=tcp

# Capture settings
CAMERA_WIDTH=640
CAMERA_HEIGHT=480
CAPTURE_COOLDOWN=2.0
MOTION_MIN_AREA=5000

# Face detection
FACE_MODEL_TYPE=haar
FACE_CONFIDENCE_THRESHOLD=0.5
```

### [NEW] [edge/iot-face-client.service](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/edge/iot-face-client.service)

```ini
[Unit]
Description=IoT Home Security - Face Recognition Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/iot_cloud_home_security/edge
EnvironmentFile=/home/pi/iot_cloud_home_security/edge/.env
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Phase 4: Tests — Comprehensive Unit Tests

**Goal**: Surpass the example's single test file with full coverage.

---

### [NEW] [tests/conftest.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/tests/conftest.py)

- Mock AWS services (DynamoDB, S3, Rekognition, SNS, SQS)
- `load_lambda_module()` helper to import handlers with mocked boto3
- `FakeTable` class for simulating DynamoDB operations
- Shared test data fixtures (sample events, device records)

### [NEW] [tests/test_process_image.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/tests/test_process_image.py)

- Test SQS record parsing + S3 test event skip
- Test `stranger` → SNS + Telegram notification
- Test `known` (high confidence) → no notification
- Test `known` (low confidence) → notification
- Test `no_face` → no notification
- Test DynamoDB item saved with correct schema
- Test Telegram failure doesn't crash the handler

### [NEW] [tests/test_device_health_check.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/tests/test_device_health_check.py)

- Test online device → no alert
- Test newly offline → SNS alert + mark offline
- Test already-offline → no duplicate (dedup)
- Test device recovery → back to `online`

### [NEW] [tests/test_heartbeat.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/tests/test_heartbeat.py)

- Test heartbeat creates new device record
- Test heartbeat updates existing
- Test `online → degraded` sends alert
- Test `degraded → degraded` same error skips (dedup)
- Test `degraded → online` sends recovery
- Test `offline → online` sends recovery

### [NEW] [tests/test_manage_collection.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/tests/test_manage_collection.py)

- Test create collection (new + already exists)
- Test index face (4-5 family member faces)
- Test delete face
- Test list faces with pagination

### [NEW] [tests/test_notification_rules.py](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/tests/test_notification_rules.py)

- Test unknown → notify, cooldown → skip, known high conf → skip, known low conf → notify

---

## Phase 5: DevOps & Documentation

**Goal**: Start/stop scripts, deployment configs, professional documentation.

---

### DevOps

#### [NEW] [scripts/start-system.sh](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/scripts/start-system.sh)

Bash script:
1. SSH to Pi → `systemctl start iot-face-client.service`
2. Check Pi service status
3. Build webapp if `.next/BUILD_ID` missing
4. Start Next.js on port 3000 (background)
5. Wait for health check
6. Optionally open browser (`xdg-open`)

#### [NEW] [scripts/stop-system.sh](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/scripts/stop-system.sh)

Bash script:
1. SSH to Pi → stop service
2. Kill dashboard by PID file or port

#### [NEW] [.env.example](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/.env.example)

Root-level template referencing all component configs.

#### [NEW] [webapp/amplify.yml](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/webapp/amplify.yml)

AWS Amplify build spec for Next.js SSR deployment.

### Documentation

#### [MODIFY] [README.md](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/README.md)

Major update:
- Add **Imou Ranger** camera info in tech stack
- Add Telegram notifications section
- Add Web Simulator section
- Add `.env.example` references for each component
- Add Amplify deployment section
- Add testing instructions
- Expand data flow to include RTSP capture

Update Tech Stack table:
```
| **Edge** | RPi 3B+ + **Imou Ranger** (RTSP) |
```

Update Data Flow:
```
1. **Edge** → Imou Ranger RTSP → Pi Motion detection → Face detection
```

#### [NEW] [docs/RASPBERRY_PI_SETUP.md](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/docs/RASPBERRY_PI_SETUP.md)

Detailed Pi setup for Imou Ranger:
- Raspberry Pi OS setup
- Network config (same LAN as Imou Ranger)
- Enable RTSP on Imou Ranger (via Imou Life app → Settings → Advanced → RTSP)
- Find camera IP address
- Test RTSP: `ffmpeg -i "rtsp://admin:SAFETYCODE@IP:554/cam/realmonitor?channel=1&subtype=0" -vframes 1 test.jpg`
- Install Python deps: `pip install opencv-python numpy requests`
- Configure `.env` with RTSP URL
- Install systemd service
- Verify: `systemctl status iot-face-client`

#### [NEW] [docs/index.html](file:///media/mamapapa/Ubuntu/iot_cloud_home_security/docs/index.html)

GitHub Pages landing page with:
- Animated hero section
- Architecture diagram
- Feature cards
- Screenshots (after Phase 2 is done)

---

## Execution Order

| Phase | Description | Estimated Files | Depends On |
|-------|-----------|----------------|------------|
| **1** | Backend: alerts + heartbeat + Telegram | ~6 files | — |
| **2** | Webapp: live data + simulator + alerts | ~18 files | Phase 1 (APIs) |
| **3** | Edge: RTSP Imou Ranger support | ~5 files | — |
| **4** | Tests: all Lambda unit tests | ~6 files | Phase 1 |
| **5** | DevOps + Docs | ~7 files | Phase 2, 3 |

**Recommended order**: Phase 1 → Phase 3 → Phase 2 → Phase 4 → Phase 5

(Phase 3 can run in parallel with Phase 1 since they're independent)

---

## Final Feature Matrix

| Feature | Example | Main (After) | Winner |
|---------|---------|-------------|--------|
| Edge AI Filtering | ❌ | ✅ Motion + Face on Pi | **Main** |
| RTSP IP Camera | ❌ (v4l2 USB) | ✅ Imou Ranger RTSP | **Main** |
| Auto-reconnect | ❌ | ✅ With backoff | **Main** |
| SQS + DLQ | ❌ | ✅ | **Main** |
| SNS Multi-Channel | ❌ | ✅ Telegram + Zalo | **Main** |
| Direct Telegram | ✅ | ✅ (+ SNS) | **Main** |
| Thumbnails | ❌ | ✅ | **Main** |
| API Authentication | ❌ | ✅ API Keys | **Main** |
| DynamoDB GSI/TTL | ❌ | ✅ | **Main** |
| Rich Alert State | ✅ 3-state | ✅ 3-state + dedup | **Tie** |
| Live Dashboard | ✅ | ✅ SWR | **Tie** |
| Web Simulator | ✅ | ✅ (webcam + file) | **Main** |
| Alert Sound | ✅ | ✅ | **Tie** |
| Face Management | ✅ | ✅ (4-5 family) | **Tie** |
| Start/Stop Scripts | ✅ PS1 | ✅ Bash | **Main** |
| Tests | ✅ 1 file | ✅ 6 files | **Main** |
| .env Templates | ✅ 1 file | ✅ 3 files | **Main** |
| Amplify Deploy | ✅ | ✅ | **Tie** |
| Docs / GH Pages | ✅ | ✅ + Pi setup | **Main** |
| Cooldown Rules | ❌ | ✅ | **Main** |
| Notification Rules | ❌ | ✅ | **Main** |

---

## Verification Plan

### Automated Tests
```bash
python -m pytest tests/ -v          # All Lambda tests
cd webapp && npm run build          # Webapp builds
cd infrastructure && sam validate   # SAM template valid
```

### Manual Verification
- Run `npm run dev` → verify all pages load with live API data
- Test web simulator: webcam/file → upload → detection result
- Test face management: add 4-5 family photos → verify in collection
- Test RTSP: `python edge/main.py` connects to Imou Ranger
- Test start/stop scripts

## Open Questions

> [!IMPORTANT]
> Before I start coding, please confirm:
> 1. **Telegram**: Do you already have a bot token + chat ID, or set blank defaults?
> 2. **SAM deployed?**: Is the AWS stack already deployed? (affects whether webapp can test live)
> 3. **Approved to start?**: All 5 phases, in order: Phase 1 → 3 → 2 → 4 → 5?

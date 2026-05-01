# 🛡️ IoT Cloud Home Security – Face Recognition Framework

A complete home security system with AI-powered face recognition, built on AWS serverless architecture.

## Architecture Overview

![Workflow](documents/workflow.png)


## Tech Stack
| Layer | Technology |
|-------|-----------|
| **Edge** | Raspberry Pi 3B+ gateway + Imou Ranger RTSP camera (Python, OpenCV) |
| **Backend** | AWS Lambda (Python 3.12) |
| **AI** | Amazon Rekognition (DetectFaces, SearchFacesByImage) |
| **Database** | Amazon DynamoDB (with GSIs) |
| **Storage** | Amazon S3 (raw images + thumbnails) |
| **Queue** | Amazon SQS (decoupled processing) |
| **Notifications** | Direct Telegram fast path + Amazon SNS → Telegram / Email |
| **Monitoring** | Amazon EventBridge (scheduled health checks) |
| **Web App** | Next.js (TypeScript) deployed on Vercel |
| **Infrastructure** | AWS SAM (CloudFormation) |

## Project Structure

```
iot_cloud_home_security/
├── README.md                              # Main project guide
├── .env.example                           # Top-level deployment checklist values
├── pyproject.toml                         # Python project metadata and dev tooling
├── uv.lock                                # Locked Python dependency graph
├── main.py                                # Small root entry point / placeholder
│
├── backend/
│   └── lambdas/                           # AWS Lambda source packages
│       ├── generate_presigned_url/
│       │   ├── handler.py                 # API handler for S3 presigned upload URLs
│       │   └── requirements.txt           # Lambda package dependencies
│       ├── process_image/
│       │   ├── handler.py                 # SQS image processor + event query handler
│       │   ├── rekognition_service.py     # Amazon Rekognition detect/search wrapper
│       │   ├── thumbnail_service.py       # Thumbnail generation and S3 upload
│       │   ├── notification_rules.py      # Alert cooldown and notification decisions
│       │   ├── telegram_notify.py         # Direct Telegram alert helper
│       │   └── requirements.txt
│       ├── manage_collection/
│       │   ├── handler.py                 # Create collection, register/list/delete faces
│       │   └── requirements.txt
│       ├── device_health_check/
│       │   ├── handler.py                 # Scheduled health check + device query API
│       │   ├── heartbeat_handler.py       # Device heartbeat API handler
│       │   ├── telegram_notify.py         # Device status Telegram helper
│       │   └── requirements.txt
│       ├── notify_telegram/
│       │   ├── handler.py                 # SNS subscriber for Telegram notifications
│       │   └── requirements.txt
│       └── notify_zalo/
│           ├── handler.py                 # SNS subscriber for Zalo OA notifications
│           └── requirements.txt
│
├── edge/                                  # Raspberry Pi gateway runtime
│   ├── .env.example                       # Pi, API, and RTSP configuration template
│   ├── main.py                            # Main capture, heartbeat, and upload loop
│   ├── config.py                          # Environment parsing and runtime settings
│   ├── rtsp_camera.py                     # Imou Ranger / RTSP capture wrapper
│   ├── motion_detector.py                 # OpenCV motion detection
│   ├── face_detector.py                   # Local face detection before upload
│   ├── uploader.py                        # API call for presigned URL + S3 PUT upload
│   ├── iot-face-client.service            # systemd service for running on boot
│   └── requirements.txt                   # Pi Python dependencies
│
├── webapp/                                # Next.js dashboard
│   ├── .env.example                       # Dashboard server/API configuration template
│   ├── package.json                       # npm scripts and dependencies
│   ├── package-lock.json                  # Locked npm dependency graph
│   ├── next.config.ts                     # Next.js configuration
│   ├── tsconfig.json                      # TypeScript configuration
│   ├── eslint.config.mjs                  # ESLint configuration
│   ├── .vercelignore                      # Files excluded from Vercel uploads
│   ├── amplify.yml                        # Optional AWS Amplify SSR build configuration
│   ├── app/                               # Next.js App Router
│   │   ├── layout.tsx                     # Root shell and navigation layout
│   │   ├── globals.css                    # Dashboard styling
│   │   ├── page.tsx                       # Main security dashboard
│   │   ├── events/page.tsx                # Detection history
│   │   ├── devices/page.tsx               # Device health view
│   │   ├── persons/page.tsx               # Known-person management
│   │   ├── alerts/page.tsx                # Alert-focused view
│   │   ├── simulate/page.tsx              # Browser webcam/file upload simulator
│   │   └── api/                           # Server-side proxy routes to API Gateway
│   │       ├── detections/route.ts        # Proxies GET /api/events
│   │       ├── devices/route.ts           # Proxies GET /api/devices
│   │       ├── faces/route.ts             # Proxies collection face CRUD
│   │       ├── register-face/route.ts     # Alias for face registration
│   │       └── upload-url/route.ts        # Proxies presigned upload URL creation
│   ├── components/                        # Reusable dashboard UI components
│   │   ├── ActivityChart.tsx
│   │   ├── DetectionCard.tsx
│   │   ├── DeviceOverview.tsx
│   │   ├── RecentEvents.tsx
│   │   ├── Sidebar.tsx
│   │   └── StatsCards.tsx
│   ├── lib/
│   │   ├── api.ts                         # Client fetch helpers and S3 preview URL helper
│   │   └── types.ts                       # Shared dashboard TypeScript types
│   └── public/                            # Static assets served by Next.js
│
├── infrastructure/
│   └── template.yaml                      # AWS SAM / CloudFormation stack
│                                           # API Gateway, Lambda, S3, SQS, DynamoDB,
│                                           # SNS, EventBridge, and IAM policies
│
├── scripts/
│   ├── start-system.sh                    # Starts optional Pi service + local dashboard
│   └── stop-system.sh                     # Stops optional Pi service + local dashboard
│
├── docs/
│   └── RASPBERRY_PI_SETUP.md              # Detailed Raspberry Pi setup guide
│
├── documents/
│   ├── workflow.png                       # Architecture/workflow diagram
│   └── improvement.md                     # Improvement notes and planning
│
├── tests/
│   └── test_regressions.py                # Python regression tests
│
└── example/
    └── iot-face-recognition-serverless/   # Reference/legacy example implementation
```

Generated local folders such as `.venv/`, `webapp/.next/`, `webapp/node_modules/`, `infrastructure/.aws-sam/`, and `__pycache__/` are build or dependency artifacts and are not part of the source workflow.

## Project Workflow

The project is split into three runtime pieces:

1. **AWS backend** - SAM deploys API Gateway, Lambda, S3, SQS, DynamoDB, Rekognition access, SNS, and EventBridge.
2. **Edge gateway** - the Raspberry Pi reads the RTSP camera, detects motion/faces locally, requests an upload URL, and uploads frames to S3.
3. **Web dashboard** - the Next.js app is deployed on Vercel. It reads events, devices, faces, and upload URLs through its own server-side API proxy so the AWS API key is not exposed in the browser.

Normal flow:

1. Deploy the AWS stack.
2. Add stack outputs and the API key to Vercel environment variables for the dashboard.
3. Deploy the dashboard to Vercel, or rely on Vercel Git integration for auto-deploy after each push.
4. Configure the edge gateway with the same API endpoint and API key.
5. Start the Pi gateway, or use the Vercel dashboard simulator to upload test images.
6. Check detections, device status, known persons, and alerts from the dashboard.

## Quick Start

### Prerequisites
- AWS Account with CLI configured
- Python 3.12+
- Node.js 20.9+ for local Next.js dashboard checks
- AWS SAM CLI
- uv, if you want to use the locked Python development environment
- Vercel account and CLI access for hosted dashboard deployment

### 1. Deploy Infrastructure
```bash
cd infrastructure
sam build
cp samconfig.example.toml samconfig.toml
```

Edit `infrastructure/samconfig.toml` once and fill in:

- `stack_name`
- `region`
- `TelegramBotToken`
- `TelegramChatId`

Then deploy without answering the guided prompts again:

```bash
sam deploy
```

`infrastructure/samconfig.toml` is ignored by git, so keep real tokens there and commit only `samconfig.example.toml`.

After deployment, capture the stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name <your-sam-stack-name> \
  --query "Stacks[0].Outputs"
```

You need:

| Output | Used for |
|--------|----------|
| `ApiUrl` | `API_ENDPOINT` for the edge gateway and dashboard |
| `RawBucketName` | Raw image storage and troubleshooting uploads |
| `ThumbBucketName` | Dashboard image previews through `NEXT_PUBLIC_S3_BUCKET_URL` |

API Gateway also requires an API key. Find it in the AWS Console under **API Gateway → API Keys**, or list it with the AWS CLI for your deployed API usage plan.

### 2. Configure Web Dashboard Env
```bash
cd webapp
npm install
cp .env.example .env.local
```

Edit `webapp/.env.local`:

```bash
API_ENDPOINT=https://your-api-id.execute-api.region.amazonaws.com/dev
API_KEY=your-api-key
NEXT_PUBLIC_S3_BUCKET_URL=https://home-security-thumb-dev-your-account-id.s3.region.amazonaws.com
```

`API_ENDPOINT` and `API_KEY` are server-side only. Do not rename them to `NEXT_PUBLIC_*`.

For Vercel production, configure the same values in the Vercel project environment variables:

```bash
cd webapp
npx --yes vercel@52.2.1 env add API_ENDPOINT production
npx --yes vercel@52.2.1 env add API_KEY production
npx --yes vercel@52.2.1 env add NEXT_PUBLIC_S3_BUCKET_URL production
```

`API_KEY` must stay server-side. `NEXT_PUBLIC_S3_BUCKET_URL` is intentionally public because the browser uses it to render image previews.

### 3. Deploy the Dashboard to Vercel
Manual production deploy:

```bash
cd webapp
npx --yes vercel@52.2.1 deploy --prod --yes
```

Current production dashboard:

- `https://webapp-phi-vert.vercel.app` - live overview
- `https://webapp-phi-vert.vercel.app/events` - detection history
- `https://webapp-phi-vert.vercel.app/devices` - device health
- `https://webapp-phi-vert.vercel.app/persons` - known-person registration
- `https://webapp-phi-vert.vercel.app/alerts` - alert view
- `https://webapp-phi-vert.vercel.app/simulate` - upload webcam/file frames through the real S3 and Lambda pipeline

Quick production API checks:

```bash
curl https://webapp-phi-vert.vercel.app/api/devices
curl "https://webapp-phi-vert.vercel.app/api/detections?limit=5"
```

If Vercel returns `API_ENDPOINT and API_KEY must be configured on the server`, add or update the Vercel environment variables, then redeploy.

To enable GitHub auto-deploy, connect the Vercel project to the repository after the Vercel account has a GitHub login connection:

```bash
cd webapp
npx --yes vercel@52.2.1 git connect https://github.com/bunnies3011/iot_cloud_facial_recognition.git
```

After that, pushes to the connected production branch will trigger Vercel deployments automatically.

### 4. Check the Dashboard Locally
```bash
cd webapp
npm run dev
```

Open:

- `http://localhost:3000` - live overview
- `http://localhost:3000/events` - detection history
- `http://localhost:3000/devices` - device health
- `http://localhost:3000/persons` - known-person registration
- `http://localhost:3000/alerts` - alert view
- `http://localhost:3000/simulate` - upload webcam/file frames through the real S3 and Lambda pipeline

Quick API checks while the dashboard server is running:

```bash
curl http://localhost:3000/api/devices
curl "http://localhost:3000/api/detections?limit=5"
```

If the dashboard returns `API_ENDPOINT and API_KEY must be configured on the server`, check `webapp/.env.local` and restart `npm run dev`.

### 5. Setup Raspberry Pi Gateway
```bash
cd edge
uv sync
export DEVICE_ID=cam-01
export API_ENDPOINT=https://your-api-id.execute-api.region.amazonaws.com/dev
export API_KEY=your-api-key
export CAMERA_SOURCE_TYPE=rtsp
export RTSP_URL='rtsp://admin:SAFETYCODE@192.168.1.100:554/cam/realmonitor?channel=1&subtype=0'
uv run main.py
```

`uv run main.py` only starts the edge capture loop. It does not start or open the web dashboard.

If you are not using uv on the Pi, install the edge requirements and run Python directly:

```bash
cd edge
pip install -r requirements.txt
python main.py
```

For systemd setup on the Pi, use `edge/iot-face-client.service` and the detailed guide in `docs/RASPBERRY_PI_SETUP.md`.

### 6. Optional Local Helper Script
```bash
PI_HOST=pi@192.168.1.50 ./scripts/start-system.sh
```

This starts the remote Pi service over SSH, installs/builds the local dashboard if needed, and serves the local dashboard at `http://localhost:3000`. It is optional when the dashboard is already deployed on Vercel.

## Data Flow

1. **Edge** → Imou Ranger RTSP stream → Pi motion detection → Face detection
2. **Upload** → Request presigned URL → PUT image to S3
3. **Process** → S3 event → SQS → Lambda → Rekognition → DynamoDB
4. **Notify** → Direct Telegram for stranger alerts + SNS fan-out for other subscribers
5. **Monitor** → Heartbeat API + EventBridge health checks → degraded/offline/recovery alerts

## Device Health State

Devices now track `alert_state` separately from raw heartbeat status:

| State | Meaning |
|-------|---------|
| `online` | Heartbeats are healthy |
| `degraded` | RTSP/capture error or stale heartbeat |
| `offline` | Device missed the offline threshold |

The heartbeat API deduplicates repeated errors with `last_alert_error_key` and sends recovery alerts when a device returns to `online`.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/presigned-url` | Generate upload URL |
| GET | `/api/events` | Query detection events |
| GET | `/api/devices` | Get device statuses |
| POST | `/api/devices/heartbeat` | Update device heartbeat and alert state |
| POST | `/api/collection` | Create Rekognition collection |
| POST | `/api/collection/faces` | Register a face |
| GET | `/api/collection/faces` | List registered faces |
| DELETE | `/api/collection/faces` | Remove a face |

## Web Dashboard

The dashboard lives in `webapp/` and uses the Next.js App Router. Browser pages call local routes such as `/api/detections`, `/api/devices`, `/api/faces`, `/api/register-face`, and `/api/upload-url`. Those routes forward requests to API Gateway with the private `API_KEY`.

Dashboard pages:

| Path | Purpose |
|------|---------|
| `/` | Live detection and device-health summary |
| `/events` | Detection history with known/unknown filters |
| `/devices` | Camera heartbeat and alert state |
| `/persons` | Register and manage known faces |
| `/alerts` | Alert-focused view |
| `/simulate` | Browser webcam/file upload into the same S3 processing path |

Production is deployed on Vercel. Configure `API_ENDPOINT`, `API_KEY`, and `NEXT_PUBLIC_S3_BUCKET_URL` in Vercel project environment variables, then redeploy.

For optional AWS Amplify SSR deployment, use `webapp/amplify.yml` and configure the same environment variables in Amplify.

## Configuration Templates

- `edge/.env.example` for Raspberry Pi and Imou Ranger RTSP settings
- `webapp/.env.example` for dashboard API and S3 preview settings
- `.env.example` for a top-level deployment checklist

## Operations

Start the edge gateway on the Pi:

```bash
cd edge
uv run main.py
```

The hosted dashboard is available at:

```text
https://webapp-phi-vert.vercel.app
```

Optionally start the local dashboard and Pi service over SSH:

```bash
PI_HOST=pi@192.168.1.50 ./scripts/start-system.sh
```

Stop both:

```bash
PI_HOST=pi@192.168.1.50 ./scripts/stop-system.sh
```

For Pi setup details, see `docs/RASPBERRY_PI_SETUP.md`.

## Testing

```bash
python3 -m unittest discover -s tests
cd webapp && npm run lint && npm run build
cd ../infrastructure && sam validate --template-file template.yaml --region us-east-1
```
## Result
# Use camera imou ranger
![Used](documents/home_recognition.png)

# Use webcam laptop
![Webcam](documents/webcam.png)

# Telegram Notification Bot
![Notify](documents/notify_webcam.png)
Alert when no connection
![Notify](documents/notify_no_connection.png)
## License

MIT
# iot_cloud_facial_recognition

export type DetectionStatus = "known" | "unknown" | "no_face";
export type DeviceAlertState = "online" | "degraded" | "offline";

export interface DetectionEvent {
  deviceId: string;
  timestamp: string;
  status: DetectionStatus;
  personId: string;
  confidence: number;
  faceCount: number;
  rawImageKey: string;
  thumbnailKey?: string;
}

export interface DeviceStatus {
  deviceId: string;
  status: DeviceAlertState;
  alertState?: DeviceAlertState;
  lastSeenAt: string;
  lastError?: string;
  isOnline?: boolean;
  cameraDevice?: string;
  cameraModel?: string;
  cameraSource?: string;
  captureIntervalSec?: number;
  uploads?: number;
  errors?: number;
}

export interface KnownPerson {
  personId: string;
  personName: string;
  faceId: string;
  s3Key: string;
  createdAt: string;
}

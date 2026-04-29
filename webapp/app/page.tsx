"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { s3ImageUrl, usePolling } from "@/lib/api";
import type { DetectionEvent, DeviceStatus } from "@/lib/types";

type EventsResponse = { events: DetectionEvent[] };
type DevicesResponse = { devices: DeviceStatus[] };

export default function DashboardPage() {
  const detections = usePolling<EventsResponse>("/api/detections?limit=20", 3000);
  const devices = usePolling<DevicesResponse>("/api/devices", 5000);
  const lastAlertRef = useRef<string | null>(null);

  const events = useMemo(() => detections.data?.events ?? [], [detections.data?.events]);
  const deviceList = useMemo(() => devices.data?.devices ?? [], [devices.data?.devices]);
  const stats = useMemo(() => {
    const known = events.filter((event) => event.status === "known").length;
    const strangers = events.filter((event) => event.status === "unknown").length;
    const online = deviceList.filter((device) => getDeviceState(device) === "online").length;
    return { total: events.length, known, strangers, online, deviceCount: deviceList.length };
  }, [events, deviceList]);

  useEffect(() => {
    const latestStranger = events.find((event) => event.status === "unknown");
    if (!latestStranger) {
      return;
    }
    const key = `${latestStranger.deviceId}:${latestStranger.timestamp}`;
    if (lastAlertRef.current && lastAlertRef.current !== key) {
      playAlertTone();
    }
    lastAlertRef.current = key;
  }, [events]);

  const loading = detections.loading || devices.loading;
  const error = detections.error || devices.error;

  return (
    <>
      <div className="page-header">
        <h1>Security Dashboard</h1>
        <p>Live overview of Imou Ranger RTSP detections and device health</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <div className="loading-spinner" />}

      <div className="stats-grid">
        <StatCard color="blue" icon="O" label="Total Detections" value={stats.total} />
        <StatCard color="green" icon="K" label="Known Detections" value={stats.known} />
        <StatCard color="red" icon="!" label="Stranger Alerts" value={stats.strangers} />
        <StatCard
          color="cyan"
          icon="C"
          label="Cameras Online"
          value={`${stats.online}/${stats.deviceCount || 0}`}
        />
      </div>

      <div className="content-grid" style={{ marginBottom: "32px" }}>
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Recent Events</div>
              <div className="card-subtitle">Auto-refreshes every 3 seconds</div>
            </div>
            <Link href="/events" className="btn btn-outline btn-sm">
              View All
            </Link>
          </div>
          <div className="event-list">
            {events.slice(0, 6).map((event) => (
              <EventRow event={event} key={`${event.deviceId}-${event.timestamp}`} />
            ))}
            {!events.length && <EmptyState text="No detection events yet" />}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Device Heartbeats</div>
              <div className="card-subtitle">Online, degraded, and offline states</div>
            </div>
            <Link href="/simulate" className="btn btn-primary btn-sm">
              Simulator
            </Link>
          </div>
          <div className="event-list">
            {deviceList.map((device) => (
              <div className="device-card" key={device.deviceId}>
                <div className={`device-indicator ${getDeviceState(device)}`} />
                <div className="device-info">
                  <div className="device-name">{device.deviceId}</div>
                  <div className="device-detail">
                    {device.cameraModel || "Imou Ranger"} ·{" "}
                    {device.cameraDevice || device.cameraSource || "rtsp"}
                  </div>
                </div>
              </div>
            ))}
            {!deviceList.length && <EmptyState text="No devices have checked in" />}
          </div>
        </div>
      </div>
    </>
  );
}

function playAlertTone() {
  const audioWindow = window as Window & {
    webkitAudioContext?: typeof AudioContext;
  };
  const AudioContextClass = window.AudioContext || audioWindow.webkitAudioContext;
  if (!AudioContextClass) {
    return;
  }

  const context = new AudioContextClass();
  const oscillator = context.createOscillator();
  const gain = context.createGain();

  oscillator.type = "sine";
  oscillator.frequency.setValueAtTime(880, context.currentTime);
  oscillator.frequency.setValueAtTime(660, context.currentTime + 0.12);
  gain.gain.setValueAtTime(0.001, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.18, context.currentTime + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.32);

  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.35);
}

function StatCard(props: { color: string; icon: string; label: string; value: string | number }) {
  return (
    <div className={`stat-card ${props.color}`}>
      <div className="stat-icon">{props.icon}</div>
      <div className="stat-value">{props.value}</div>
      <div className="stat-label">{props.label}</div>
    </div>
  );
}

function EventRow({ event }: { event: DetectionEvent }) {
  const image = s3ImageUrl(event.thumbnailKey);
  return (
    <div className="event-item">
      {image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={image} alt="" className="event-thumbnail" />
      ) : (
        <div className="event-thumbnail">{event.status === "known" ? "K" : "!"}</div>
      )}
      <div className="event-info">
        <div className="event-title">
          {event.status === "known" ? event.personId : "Stranger Detected"}
        </div>
        <div className="event-meta">
          <span>{event.deviceId}</span>
          <span>{new Date(event.timestamp).toLocaleString()}</span>
          {event.confidence > 0 && <span>{event.confidence.toFixed(1)}%</span>}
        </div>
      </div>
      <span className={`event-status ${event.status.replace("_", "-")}`}>{event.status}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="empty-state">
      <p>{text}</p>
    </div>
  );
}

function getDeviceState(device: DeviceStatus) {
  return device.alertState || device.status || "offline";
}

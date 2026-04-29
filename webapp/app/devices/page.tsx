"use client";

import { useMemo } from "react";
import { usePolling } from "@/lib/api";
import type { DeviceStatus } from "@/lib/types";

type DevicesResponse = { devices: DeviceStatus[] };

export default function DevicesPage() {
  const { data, error, loading } = usePolling<DevicesResponse>("/api/devices", 5000);
  const devices = useMemo(() => data?.devices ?? [], [data?.devices]);

  const stats = useMemo(() => {
    const online = devices.filter((device) => getState(device) === "online").length;
    const degraded = devices.filter((device) => getState(device) === "degraded").length;
    const offline = devices.filter((device) => getState(device) === "offline").length;
    const uploads = devices.reduce((sum, device) => sum + Number(device.uploads ?? 0), 0);
    return { online, degraded, offline, uploads };
  }, [devices]);

  return (
    <>
      <div className="page-header">
        <h1>Device Management</h1>
        <p>Monitor Raspberry Pi gateway heartbeats and Imou Ranger RTSP health</p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <div className="loading-spinner" />}

      <div className="stats-grid" style={{ marginBottom: "32px" }}>
        <StatCard color="green" icon="O" value={stats.online} label="Online Devices" />
        <StatCard color="cyan" icon="D" value={stats.degraded} label="Degraded Devices" />
        <StatCard color="red" icon="X" value={stats.offline} label="Offline Devices" />
        <StatCard color="blue" icon="U" value={stats.uploads.toLocaleString()} label="Uploads" />
      </div>

      <div className="device-grid">
        {devices.map((device) => (
          <div className="card" key={device.deviceId} style={{ padding: "20px" }}>
            <div className="device-card-header">
              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <div className={`device-indicator ${getState(device)}`} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: "15px" }}>{device.deviceId}</div>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    {device.cameraModel || "Imou Ranger"}
                  </div>
                </div>
              </div>
              <span className={`badge ${badgeClass(getState(device))}`}>{getState(device)}</span>
            </div>

            <div className="device-detail-grid">
              <Detail label="Source" value={device.cameraDevice || "rtsp"} />
              <Detail
                label="Interval"
                value={`${device.captureIntervalSec ?? "n/a"}s`}
              />
              <Detail label="Uploads" value={String(device.uploads ?? 0)} />
              <Detail label="Errors" value={String(device.errors ?? 0)} />
            </div>

            {device.lastError && (
              <div className="error-box">{device.lastError}</div>
            )}

            <div className="device-last-seen">
              Last seen:{" "}
              {device.lastSeenAt ? new Date(device.lastSeenAt).toLocaleString() : "Never"}
            </div>
          </div>
        ))}
      </div>

      {!devices.length && !loading && (
        <div className="empty-state">
          <p>No device heartbeats have been received</p>
        </div>
      )}
    </>
  );
}

function StatCard({
  color,
  icon,
  value,
  label,
}: {
  color: string;
  icon: string;
  value: number | string;
  label: string;
}) {
  return (
    <div className={`stat-card ${color}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ color: "var(--text-muted)", marginBottom: "2px" }}>{label}</div>
      <div>{value}</div>
    </div>
  );
}

function getState(device: DeviceStatus) {
  return device.alertState || device.status || "offline";
}

function badgeClass(state: string) {
  if (state === "online") {
    return "badge-success";
  }
  if (state === "degraded") {
    return "badge-warning";
  }
  return "badge-danger";
}

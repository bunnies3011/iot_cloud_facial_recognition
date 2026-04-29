"use client";

import { useMemo, useState } from "react";
import { usePolling } from "@/lib/api";
import type { DetectionEvent, DeviceStatus } from "@/lib/types";

type EventsResponse = { events: DetectionEvent[] };
type DevicesResponse = { devices: DeviceStatus[] };
type AlertFilter = "all" | "stranger" | "degraded" | "offline" | "recovery";

export default function AlertsPage() {
  const [filter, setFilter] = useState<AlertFilter>("all");
  const events = usePolling<EventsResponse>("/api/detections?limit=100", 5000);
  const devices = usePolling<DevicesResponse>("/api/devices", 5000);

  const alerts = useMemo(() => {
    const detectionAlerts = (events.data?.events ?? [])
      .filter((event) => event.status === "unknown")
      .map((event) => ({
        id: `${event.deviceId}-${event.timestamp}`,
        type: "stranger" as AlertFilter,
        severity: "danger",
        title: "Stranger detected",
        detail: `${event.deviceId} · ${new Date(event.timestamp).toLocaleString()}`,
      }));

    const deviceAlerts = (devices.data?.devices ?? [])
      .filter((device) => getState(device) !== "online")
      .map((device) => ({
        id: device.deviceId,
        type: getState(device) as AlertFilter,
        severity: getState(device) === "offline" ? "danger" : "warning",
        title: `Device ${getState(device)}`,
        detail: `${device.deviceId} · Telegram/SNS alert state tracked`,
      }));

    const allAlerts = [...deviceAlerts, ...detectionAlerts];
    return filter === "all" ? allAlerts : allAlerts.filter((alert) => alert.type === filter);
  }, [devices.data?.devices, events.data?.events, filter]);

  return (
    <>
      <div className="page-header">
        <h1>Alerts</h1>
        <p>Security and device-health alerts with Telegram delivery status</p>
      </div>

      <div className="card" style={{ marginBottom: "24px" }}>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {(["all", "stranger", "degraded", "offline", "recovery"] as AlertFilter[]).map(
            (item) => (
              <button
                className={`btn btn-sm ${filter === item ? "btn-primary" : "btn-outline"}`}
                key={item}
                onClick={() => setFilter(item)}
              >
                {item}
              </button>
            ),
          )}
        </div>
      </div>

      <div className="card">
        <div className="timeline">
          {alerts.map((alert) => (
            <div className="timeline-item" key={alert.id}>
              <div className={`timeline-dot ${alert.severity}`} />
              <div className="card-title">{alert.title}</div>
              <div className="card-subtitle">{alert.detail}</div>
              <span className="badge badge-success" style={{ marginTop: "8px" }}>
                Telegram non-blocking
              </span>
            </div>
          ))}
          {!alerts.length && (
            <div className="empty-state">
              <p>No alerts match this filter</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function getState(device: DeviceStatus) {
  return device.alertState || device.status || "offline";
}

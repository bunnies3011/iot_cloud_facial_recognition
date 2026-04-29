"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { s3ImageUrl, usePolling } from "@/lib/api";
import type { DetectionEvent, DetectionStatus } from "@/lib/types";

type EventsResponse = { events: DetectionEvent[] };
type Filter = "all" | "unknown" | "known";

export default function EventsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const { data, error, loading } = usePolling<EventsResponse>(
    "/api/detections?limit=100",
    5000,
  );
  const events = useMemo(() => data?.events ?? [], [data?.events]);

  const filteredEvents = useMemo(() => {
    if (filter === "all") {
      return events;
    }
    return events.filter((event) => event.status === filter);
  }, [events, filter]);

  return (
    <>
      <div className="page-header">
        <h1>Detection Events</h1>
        <p>Browse live face detection events from the AWS pipeline</p>
      </div>

      <div className="card" style={{ marginBottom: "24px" }}>
        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          <FilterButton active={filter === "all"} onClick={() => setFilter("all")}>
            All Events
          </FilterButton>
          <FilterButton active={filter === "unknown"} onClick={() => setFilter("unknown")}>
            Unknown Only
          </FilterButton>
          <FilterButton active={filter === "known"} onClick={() => setFilter("known")}>
            Known Only
          </FilterButton>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <div className="loading-spinner" />}

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Preview</th>
                <th>Status</th>
                <th>Person</th>
                <th>Camera</th>
                <th>Confidence</th>
                <th>Faces</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map((event) => (
                <EventRow event={event} key={`${event.deviceId}-${event.timestamp}`} />
              ))}
            </tbody>
          </table>
        </div>
        {!filteredEvents.length && !loading && (
          <div className="empty-state">
            <p>No events match this filter</p>
          </div>
        )}
      </div>
    </>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button className={`btn btn-sm ${active ? "btn-primary" : "btn-outline"}`} onClick={onClick}>
      {children}
    </button>
  );
}

function EventRow({ event }: { event: DetectionEvent }) {
  const image = s3ImageUrl(event.thumbnailKey);
  const statusClass = event.status.replace("_", "-");

  return (
    <tr>
      <td>
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt="" className="event-thumbnail" />
        ) : (
          <div className="event-thumbnail">{statusLabel(event.status).charAt(0)}</div>
        )}
      </td>
      <td>
        <span className={`event-status ${statusClass}`}>{statusLabel(event.status)}</span>
      </td>
      <td style={{ fontWeight: 500 }}>
        {event.status === "known" ? event.personId : "Stranger"}
      </td>
      <td style={{ color: "var(--text-secondary)" }}>{event.deviceId}</td>
      <td>
        {event.confidence > 0 ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div className="confidence-bar" style={{ width: "80px" }}>
              <div
                className={`confidence-bar-fill ${
                  event.confidence >= 95 ? "high" : event.confidence >= 85 ? "medium" : "low"
                }`}
                style={{ width: `${Math.min(event.confidence, 100)}%` }}
              />
            </div>
            <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              {event.confidence.toFixed(1)}%
            </span>
          </div>
        ) : (
          <span style={{ color: "var(--text-muted)" }}>None</span>
        )}
      </td>
      <td>{event.faceCount}</td>
      <td style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
        {new Date(event.timestamp).toLocaleString()}
      </td>
    </tr>
  );
}

function statusLabel(status: DetectionStatus) {
  if (status === "no_face") {
    return "No Face";
  }
  return status === "unknown" ? "Unknown" : "Known";
}

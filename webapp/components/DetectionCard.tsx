"use client";

import { s3ImageUrl } from "@/lib/api";
import type { DetectionEvent } from "@/lib/types";

export default function DetectionCard({ event }: { event: DetectionEvent }) {
  const image = s3ImageUrl(event.thumbnailKey || event.rawImageKey);
  const statusClass = event.status.replace("_", "-");

  return (
    <article className={`detection-card ${statusClass}`}>
      {image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={image} alt="" className="detection-card-image" />
      ) : (
        <div className="detection-card-image">{event.status === "known" ? "K" : "!"}</div>
      )}
      <div className="detection-card-body">
        <div className="detection-card-title">
          {event.status === "known" ? event.personId : "Stranger"}
        </div>
        <div className="detection-card-meta">
          {event.deviceId} · {new Date(event.timestamp).toLocaleString()}
        </div>
        <div className="confidence-bar">
          <div
            className={`confidence-bar-fill ${
              event.confidence >= 95 ? "high" : event.confidence >= 85 ? "medium" : "low"
            }`}
            style={{ width: `${Math.min(event.confidence || 0, 100)}%` }}
          />
        </div>
      </div>
    </article>
  );
}

"use client";

const events = [
  {
    id: 1,
    device: "cam-01",
    status: "unknown",
    person: "Unknown",
    confidence: 0,
    time: "2 minutes ago",
    timestamp: "10:15:30",
  },
  {
    id: 2,
    device: "cam-02",
    status: "known",
    person: "Nguyen Van A",
    confidence: 98.7,
    time: "15 minutes ago",
    timestamp: "10:00:12",
  },
  {
    id: 3,
    device: "cam-01",
    status: "known",
    person: "Tran Thi B",
    confidence: 95.2,
    time: "32 minutes ago",
    timestamp: "09:43:55",
  },
  {
    id: 4,
    device: "cam-03",
    status: "unknown",
    person: "Unknown",
    confidence: 0,
    time: "1 hour ago",
    timestamp: "09:15:22",
  },
  {
    id: 5,
    device: "cam-01",
    status: "known",
    person: "Le Van C",
    confidence: 91.8,
    time: "2 hours ago",
    timestamp: "08:22:41",
  },
];

export default function RecentEvents() {
  return (
    <div className="event-list">
      {events.map((event) => (
        <div className="event-item" key={event.id}>
          <div className="event-thumbnail">
            {event.status === "known" ? "👤" : "❓"}
          </div>
          <div className="event-info">
            <div className="event-title">
              {event.status === "known"
                ? event.person
                : "Unknown Person Detected"}
            </div>
            <div className="event-meta">
              <span>📷 {event.device}</span>
              <span>🕐 {event.time}</span>
              {event.confidence > 0 && (
                <span>📊 {event.confidence.toFixed(1)}%</span>
              )}
            </div>
          </div>
          <span className={`event-status ${event.status}`}>
            {event.status}
          </span>
        </div>
      ))}
    </div>
  );
}

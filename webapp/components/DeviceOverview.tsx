"use client";

const devices = [
  {
    id: "cam-01",
    name: "Front Door Camera",
    status: "online",
    lastSeen: "Just now",
    location: "Main Entrance",
  },
  {
    id: "cam-02",
    name: "Backyard Camera",
    status: "online",
    lastSeen: "2 min ago",
    location: "Backyard",
  },
  {
    id: "cam-03",
    name: "Garage Camera",
    status: "online",
    lastSeen: "5 min ago",
    location: "Garage",
  },
  {
    id: "cam-04",
    name: "Living Room Camera",
    status: "online",
    lastSeen: "1 min ago",
    location: "Living Room",
  },
  {
    id: "cam-05",
    name: "Side Gate Camera",
    status: "offline",
    lastSeen: "45 min ago",
    location: "Side Gate",
  },
];

export default function DeviceOverview() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {devices.map((device) => (
        <div className="device-card" key={device.id}>
          <div
            className={`device-indicator ${device.status}`}
          />
          <div className="device-info">
            <div className="device-name">{device.name}</div>
            <div className="device-detail">
              {device.location} · {device.lastSeen}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

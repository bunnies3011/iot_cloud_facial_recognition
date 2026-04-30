"use client";

const stats = [
  {
    label: "Total Detections",
    value: "1,247",
    change: "+12% vs last week",
    changeType: "positive",
    icon: "DT",
    color: "blue",
  },
  {
    label: "Known Persons",
    value: "23",
    change: "2 new this month",
    changeType: "positive",
    icon: "ID",
    color: "green",
  },
  {
    label: "Unknown Alerts",
    value: "8",
    change: "-5% vs last week",
    changeType: "positive",
    icon: "AL",
    color: "red",
  },
  {
    label: "Cameras Online",
    value: "4/5",
    change: "1 offline",
    changeType: "negative",
    icon: "CM",
    color: "cyan",
  },
];

export default function StatsCards() {
  return (
    <div className="stats-grid">
      {stats.map((stat, index) => (
        <div className={`stat-card ${stat.color}`} key={index}>
          <div className="stat-icon">{stat.icon}</div>
          <div className="stat-value">{stat.value}</div>
          <div className="stat-label">{stat.label}</div>
          <div className={`stat-change ${stat.changeType}`}>
            {stat.changeType === "positive" ? "↑" : "↓"} {stat.change}
          </div>
        </div>
      ))}
    </div>
  );
}

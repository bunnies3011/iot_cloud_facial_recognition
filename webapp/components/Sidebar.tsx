"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", icon: "📊" },
  { href: "/events", label: "Events", icon: "🔔" },
  { href: "/devices", label: "Devices", icon: "📷" },
  { href: "/persons", label: "Known Persons", icon: "👤" },
  { href: "/simulate", label: "Simulator", icon: "🎮" },
  { href: "/alerts", label: "Alerts", icon: "🚨" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">🛡️</div>
        <span className="logo-text">SecureHome</span>
      </div>

      <ul className="sidebar-nav">
        {navItems.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={pathname === item.href ? "active" : ""}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </Link>
          </li>
        ))}
      </ul>

      <div
        style={{
          padding: "16px",
          borderTop: "1px solid var(--border-color)",
          marginTop: "auto",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "12px",
            color: "var(--text-muted)",
          }}
        >
          <div
            className="device-indicator online"
            style={{ width: "8px", height: "8px" }}
          />
          System Online
        </div>
      </div>
    </aside>
  );
}

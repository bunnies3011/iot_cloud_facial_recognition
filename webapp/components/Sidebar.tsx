"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", icon: "DB" },
  { href: "/events", label: "Events", icon: "EV" },
  { href: "/devices", label: "Devices", icon: "DV" },
  { href: "/persons", label: "Known Persons", icon: "ID" },
  { href: "/simulate", label: "Simulator", icon: "SM" },
  { href: "/alerts", label: "Alerts", icon: "AL" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-icon">HS</div>
        <span className="logo-text">Control Room</span>
      </div>

      <ul className="sidebar-nav">
        {navItems.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={pathname === item.href ? "active" : ""}
            >
              <span className="nav-icon" aria-hidden="true">{item.icon}</span>
              {item.label}
            </Link>
          </li>
        ))}
      </ul>

      <div className="sidebar-status">
        <div className="sidebar-status-row">
          <div className="device-indicator online" />
          System Online
        </div>
      </div>
    </aside>
  );
}

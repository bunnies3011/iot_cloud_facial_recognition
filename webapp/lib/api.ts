"use client";

import { useEffect, useState } from "react";

export async function fetcher<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function usePolling<T>(url: string, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const nextData = await fetcher<T>(url);
        if (!cancelled) {
          setData(nextData);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Request failed");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    const timer = window.setInterval(load, intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [url, intervalMs]);

  return { data, error, loading };
}

export async function getPresignedUrl(payload: {
  deviceId: string;
  timestamp?: string;
}) {
  const response = await fetch("/api/upload-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await responseError(response, "Upload URL request failed"));
  }
  return response.json() as Promise<{
    upload_url: string;
    s3_key: string;
    bucket: string;
  }>;
}

export async function uploadToS3(uploadUrl: string, file: Blob) {
  const response = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": "image/jpeg" },
  });
  if (!response.ok) {
    throw new Error(`S3 upload failed with ${response.status}`);
  }
}

export async function registerFace(payload: {
  personId: string;
  personName: string;
  s3Key: string;
}) {
  const response = await fetch("/api/register-face", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await responseError(response, "Register face failed"));
  }
  return response.json();
}

async function responseError(response: Response, fallback: string) {
  const body = await response.json().catch(() => null) as { error?: string } | null;
  return body?.error || `${fallback} with ${response.status}`;
}

export function s3ImageUrl(key?: string) {
  if (!key) {
    return "";
  }

  return `/api/image-url?key=${encodeURIComponent(key)}`;
}

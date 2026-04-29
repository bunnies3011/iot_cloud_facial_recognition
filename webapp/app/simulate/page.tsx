"use client";

import { ChangeEvent, useRef, useState } from "react";
import { getPresignedUrl, uploadToS3, usePolling } from "@/lib/api";
import type { DetectionEvent } from "@/lib/types";

type EventsResponse = { events: DetectionEvent[] };
type SimStatus = "idle" | "capturing" | "uploading" | "processing" | "result";

export default function SimulatePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState<SimStatus>("idle");
  const [message, setMessage] = useState("");
  const [uploadedKey, setUploadedKey] = useState<string | null>(null);
  const { data } = usePolling<EventsResponse>("/api/detections?limit=10", 3000);

  async function startCamera() {
    setStatus("capturing");
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
    }
  }

  async function captureFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      return;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const context = canvas.getContext("2d");
    context?.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.9),
    );
    if (blob) {
      await uploadBlob(blob);
    }
  }

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      await uploadBlob(file);
    }
  }

  async function uploadBlob(blob: Blob) {
    setStatus("uploading");
    setMessage("Uploading frame");
    const presigned = await getPresignedUrl({
      deviceId: "web-simulator",
      timestamp: new Date().toISOString(),
    });
    await uploadToS3(presigned.upload_url, blob);
    setUploadedKey(presigned.s3_key);
    setStatus("processing");
    setMessage("Waiting for Rekognition result");
    window.setTimeout(() => setStatus("result"), 5000);
  }

  const latestResult = data?.events.find((event) =>
    uploadedKey ? event.rawImageKey?.includes(uploadedKey) : false,
  );

  return (
    <>
      <div className="page-header">
        <h1>Web Simulator</h1>
        <p>Upload a webcam or file frame through the same S3 and Lambda pipeline</p>
      </div>

      <div className="simulator-grid">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Webcam</div>
              <div className="card-subtitle">Capture a test frame from this browser</div>
            </div>
          </div>
          <video ref={videoRef} autoPlay className="webcam-preview" muted playsInline />
          <canvas ref={canvasRef} style={{ display: "none" }} />
          <div style={{ display: "flex", gap: "12px", marginTop: "16px" }}>
            <button className="btn btn-outline" onClick={startCamera}>
              Start Camera
            </button>
            <button className="btn btn-primary" onClick={captureFrame}>
              Capture
            </button>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">File Upload</div>
              <div className="card-subtitle">Send an existing image to the pipeline</div>
            </div>
          </div>
          <label className="upload-dropzone" htmlFor="simFile">
            Choose image
            <input accept="image/*" id="simFile" onChange={handleFile} type="file" />
          </label>
          <div className={`pipeline-status ${status}`}>{message || status}</div>
          {latestResult && (
            <div className="result-box">
              {latestResult.status} · {latestResult.deviceId} ·{" "}
              {new Date(latestResult.timestamp).toLocaleString()}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { getPresignedUrl, uploadToS3, usePolling } from "@/lib/api";
import type { DetectionEvent, DetectionStatus } from "@/lib/types";

type EventsResponse = { events: DetectionEvent[] };
type SimStatus = "idle" | "capturing" | "uploading" | "processing" | "result" | "error";
const LIVE_CAPTURE_INTERVAL_MS = 3500;

export default function SimulatePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const liveTimerRef = useRef<number | null>(null);
  const liveActiveRef = useRef(false);
  const uploadInFlightRef = useRef(false);
  const [status, setStatus] = useState<SimStatus>("idle");
  const [message, setMessage] = useState("");
  const [cameraReady, setCameraReady] = useState(false);
  const [liveMode, setLiveMode] = useState(false);
  const [uploadedKeys, setUploadedKeys] = useState<string[]>([]);
  const { data } = usePolling<EventsResponse>("/api/detections?limit=10", 1000);

  useEffect(() => {
    return () => {
      liveActiveRef.current = false;
      if (liveTimerRef.current !== null) {
        window.clearInterval(liveTimerRef.current);
        liveTimerRef.current = null;
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function startCamera() {
    setStatus("capturing");
    setMessage("Requesting camera permission");
    try {
      if (!window.isSecureContext) {
        throw new Error("Camera requires HTTPS or localhost");
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("This browser does not support camera capture");
      }

      stopCamera(false);
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraReady(true);
      setMessage("Camera is ready");
      return true;
    } catch (err) {
      setStatus("error");
      setMessage(cameraErrorMessage(err));
      setCameraReady(false);
      return false;
    }
  }

  function stopCamera(updateStatus = true) {
    stopLiveDetection(false);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setCameraReady(false);
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (updateStatus) {
      setStatus("idle");
      setMessage("Camera stopped");
    }
  }

  async function startLiveDetection() {
    if (liveMode) {
      return;
    }

    const ready = streamRef.current ? true : await startCamera();
    if (!ready) {
      return;
    }

    setLiveMode(true);
    liveActiveRef.current = true;
    setStatus("processing");
    setMessage("Live detection running");
    await processLiveFrame();
    if (liveActiveRef.current) {
      liveTimerRef.current = window.setInterval(processLiveFrame, LIVE_CAPTURE_INTERVAL_MS);
    }
  }

  function stopLiveDetection(updateStatus = true) {
    liveActiveRef.current = false;
    if (liveTimerRef.current !== null) {
      window.clearInterval(liveTimerRef.current);
      liveTimerRef.current = null;
    }
    setLiveMode(false);
    if (updateStatus) {
      setStatus(streamRef.current ? "capturing" : "idle");
      setMessage(streamRef.current ? "Camera is ready" : "Camera stopped");
    }
  }

  async function processLiveFrame() {
    if (uploadInFlightRef.current || !streamRef.current || !liveActiveRef.current) {
      return;
    }

    uploadInFlightRef.current = true;
    try {
      const blob = await captureCameraBlob();
      if (!blob) {
        return;
      }
      const key = await uploadBlob(blob, "live");
      trackUploadedKey(key);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Live detection failed");
      stopLiveDetection(false);
    } finally {
      uploadInFlightRef.current = false;
    }
  }

  async function captureFrame() {
    stopLiveDetection(false);
    const blob = await captureCameraBlob();
    if (!blob) {
      return;
    }

    try {
      const key = await uploadBlob(blob, "manual");
      trackUploadedKey(key);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function captureCameraBlob() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) {
      return null;
    }
    if (!streamRef.current || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      setStatus("error");
      setMessage("Start the camera before capturing");
      return null;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const context = canvas.getContext("2d");
    context?.drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.9),
    );
    return blob;
  }

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) {
      try {
        const key = await uploadBlob(file, "manual");
        trackUploadedKey(key);
      } catch (err) {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Upload failed");
      }
    }
  }

  async function uploadBlob(blob: Blob, mode: "live" | "manual") {
    setStatus("uploading");
    setMessage(mode === "live" ? "Uploading live frame" : "Uploading frame");
    const presigned = await getPresignedUrl({
      deviceId: "web-simulator",
      timestamp: new Date().toISOString(),
    });
    await uploadToS3(presigned.upload_url, blob);
    setStatus("processing");
    setMessage(mode === "live" ? "Live detection running" : "Waiting for Rekognition result");
    if (mode === "manual") {
      window.setTimeout(() => setStatus("result"), 5000);
    }
    return presigned.s3_key;
  }

  function trackUploadedKey(key: string) {
    setUploadedKeys((keys) => [key, ...keys].slice(0, 20));
  }

  const latestResult = data?.events.find((event) => {
    const rawKey = event.rawImageKey || "";
    return uploadedKeys.some((key) => rawKey.includes(key));
  });

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
              <div className="card-subtitle">Run continuous Rekognition checks from this browser</div>
            </div>
          </div>
          <video ref={videoRef} autoPlay className="webcam-preview" muted playsInline />
          <canvas ref={canvasRef} style={{ display: "none" }} />
          <div style={{ display: "flex", gap: "12px", marginTop: "16px", flexWrap: "wrap" }}>
            <button className="btn btn-outline" onClick={startCamera}>
              Start Camera
            </button>
            <button className="btn btn-primary" onClick={startLiveDetection} disabled={liveMode}>
              Start Live Detection
            </button>
            <button className="btn btn-outline" onClick={() => stopLiveDetection()} disabled={!liveMode}>
              Stop Live
            </button>
            <button className="btn btn-outline" onClick={captureFrame} disabled={!cameraReady || liveMode}>
              Capture
            </button>
            <button className="btn btn-outline" onClick={() => stopCamera()}>
              Stop
            </button>
          </div>
          <div className={`pipeline-status ${status}`}>{message || status}</div>
          {latestResult && (
            <div className="result-box">
              <div className="result-box-header">
                <span className={`event-status ${latestResult.status.replace("_", "-")}`}>
                  {statusLabel(latestResult.status)}
                </span>
                <span>{new Date(latestResult.timestamp).toLocaleString()}</span>
              </div>
              <div className="result-box-details">
                {resultPersonLabel(latestResult)} · {latestResult.faceCount} face
                {latestResult.faceCount === 1 ? "" : "s"} ·{" "}
                {latestResult.confidence > 0
                  ? `${latestResult.confidence.toFixed(1)}% confidence`
                  : "no match confidence"}
              </div>
            </div>
          )}
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
              <div className="result-box-header">
                <span className={`event-status ${latestResult.status.replace("_", "-")}`}>
                  {statusLabel(latestResult.status)}
                </span>
                <span>{latestResult.deviceId}</span>
              </div>
              <div className="result-box-details">
                {resultPersonLabel(latestResult)} ·{" "}
                {new Date(latestResult.timestamp).toLocaleString()}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function cameraErrorMessage(err: unknown) {
  if (err instanceof DOMException) {
    if (err.name === "NotAllowedError") {
      return "Camera permission was blocked";
    }
    if (err.name === "NotFoundError") {
      return "No camera device was found";
    }
    if (err.name === "NotReadableError") {
      return "Camera is already in use by another app";
    }
  }
  return err instanceof Error ? err.message : "Camera could not be started";
}

function statusLabel(status: DetectionStatus) {
  if (status === "no_face") {
    return "No Face";
  }
  return status === "known" ? "Known" : "Unknown";
}

function resultPersonLabel(event: DetectionEvent) {
  if (event.status === "known") {
    return event.personId;
  }
  if (event.status === "no_face") {
    return "No face detected";
  }
  return "Unknown person";
}

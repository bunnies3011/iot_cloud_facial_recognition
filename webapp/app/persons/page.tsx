"use client";

import { FormEvent, useState } from "react";
import { getPresignedUrl, registerFace, s3ImageUrl, uploadToS3, usePolling } from "@/lib/api";

type FaceRecord = {
  face_id?: string;
  faceId?: string;
  external_image_id?: string;
  personId?: string;
  confidence?: number;
  s3Key?: string;
};

type FacesResponse = {
  faces: FaceRecord[];
  face_count: number;
};

export default function PersonsPage() {
  const { data, error, loading } = usePolling<FacesResponse>("/api/faces", 10000);
  const [personName, setPersonName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const faces = data?.faces ?? [];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!personName.trim() || !file) {
      setFormError("Name and face image are required");
      return;
    }

    setBusy(true);
    setFormError(null);
    try {
      const personId = personName.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
      const presigned = await getPresignedUrl({
        deviceId: "web-persons",
        timestamp: new Date().toISOString(),
      });
      await uploadToS3(presigned.upload_url, file);
      await registerFace({
        personId,
        personName: personName.trim(),
        s3Key: presigned.s3_key,
      });
      window.location.reload();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  async function deleteFace(faceId: string) {
    setBusy(true);
    try {
      await fetch("/api/faces", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ faceId }),
      });
      window.location.reload();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Known Persons</h1>
        <p>Register and manage the 4-5 family members allowed in the system</p>
      </div>

      {(error || formError) && <div className="error-banner">{error || formError}</div>}
      {loading && <div className="loading-spinner" />}

      <form className="card form-grid" onSubmit={submit} style={{ marginBottom: "24px" }}>
        <div>
          <label className="field-label" htmlFor="personName">
            Person name
          </label>
          <input
            className="text-field"
            id="personName"
            onChange={(event) => setPersonName(event.target.value)}
            placeholder="Family member name"
            value={personName}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="faceImage">
            Face image
          </label>
          <input
            accept="image/*"
            className="text-field"
            id="faceImage"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            type="file"
          />
        </div>
        <button className="btn btn-primary" disabled={busy} type="submit">
          Add Person
        </button>
        <div className="member-count">{faces.length}/5 members registered</div>
      </form>

      <div className="person-grid">
        {faces.map((face) => {
          const faceId = face.faceId || face.face_id || "";
          const personId = face.personId || face.external_image_id || "unknown";
          const image = s3ImageUrl(face.s3Key);
          return (
            <div className="person-card" key={faceId || personId}>
              {image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={image} alt="" className="person-avatar person-photo" />
              ) : (
                <div className="person-avatar">{personId.charAt(0).toUpperCase()}</div>
              )}
              <div className="person-name">{personId}</div>
              <div className="person-id">{faceId}</div>
              <div className="person-meta">
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Confidence</span>
                  <span style={{ color: "var(--text-secondary)" }}>
                    {Number(face.confidence ?? 0).toFixed(1)}%
                  </span>
                </div>
              </div>
              <button
                className="btn btn-outline btn-sm"
                disabled={busy || !faceId}
                onClick={() => deleteFace(faceId)}
                style={{ color: "var(--accent-red)", marginTop: "16px" }}
              >
                Remove
              </button>
            </div>
          );
        })}
      </div>

      {!faces.length && !loading && (
        <div className="empty-state">
          <p>No known persons are registered yet</p>
        </div>
      )}
    </>
  );
}

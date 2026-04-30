import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const apiEndpoint = process.env.API_ENDPOINT;
  const apiKey = process.env.API_KEY;

  if (!apiEndpoint || !apiKey) {
    return NextResponse.json(
      { error: "API_ENDPOINT and API_KEY must be configured on the server" },
      { status: 500 },
    );
  }

  const sourceUrl = new URL(request.url);
  const key = sourceUrl.searchParams.get("key");
  if (!key) {
    return NextResponse.json({ error: "Missing required query parameter: key" }, { status: 400 });
  }

  const target = new URL(`${apiEndpoint.replace(/\/$/, "")}/api/image-url`);
  target.searchParams.set("key", key);

  const response = await fetch(target, {
    headers: { "x-api-key": apiKey },
    cache: "no-store",
  });
  const body = await response.json().catch(() => null) as { url?: string; error?: string } | null;

  if (!response.ok || !body?.url) {
    return NextResponse.json(
      { error: body?.error || "Failed to generate image URL" },
      { status: response.status || 500 },
    );
  }

  return NextResponse.redirect(body.url);
}

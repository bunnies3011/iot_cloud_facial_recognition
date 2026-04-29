import { NextResponse } from "next/server";

export async function GET(request: Request) {
  return proxyRequest(request, "/api/events");
}

async function proxyRequest(request: Request, path: string) {
  const apiEndpoint = process.env.API_ENDPOINT;
  const apiKey = process.env.API_KEY;

  if (!apiEndpoint || !apiKey) {
    return NextResponse.json(
      { error: "API_ENDPOINT and API_KEY must be configured on the server" },
      { status: 500 },
    );
  }

  const sourceUrl = new URL(request.url);
  const target = `${apiEndpoint.replace(/\/$/, "")}${path}${sourceUrl.search}`;
  const response = await fetch(target, {
    headers: { "x-api-key": apiKey },
    cache: "no-store",
  });
  const body = await response.text();

  return new NextResponse(body, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
  });
}

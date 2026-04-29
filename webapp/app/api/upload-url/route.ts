import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const apiEndpoint = process.env.API_ENDPOINT;
  const apiKey = process.env.API_KEY;

  if (!apiEndpoint || !apiKey) {
    return NextResponse.json(
      { error: "API_ENDPOINT and API_KEY must be configured on the server" },
      { status: 500 },
    );
  }

  const response = await fetch(`${apiEndpoint.replace(/\/$/, "")}/api/presigned-url`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
    },
    body: await request.text(),
    cache: "no-store",
  });

  return new NextResponse(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
  });
}

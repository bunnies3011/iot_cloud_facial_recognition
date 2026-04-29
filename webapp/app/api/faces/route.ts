import { NextResponse } from "next/server";

export async function GET(request: Request) {
  return proxy(request, "GET");
}

export async function POST(request: Request) {
  return proxy(request, "POST");
}

export async function DELETE(request: Request) {
  return proxy(request, "DELETE");
}

async function proxy(request: Request, method: string) {
  const apiEndpoint = process.env.API_ENDPOINT;
  const apiKey = process.env.API_KEY;

  if (!apiEndpoint || !apiKey) {
    return NextResponse.json(
      { error: "API_ENDPOINT and API_KEY must be configured on the server" },
      { status: 500 },
    );
  }

  const sourceUrl = new URL(request.url);
  const body = method === "GET" ? undefined : await request.text();
  const response = await fetch(
    `${apiEndpoint.replace(/\/$/, "")}/api/collection/faces${sourceUrl.search}`,
    {
      method,
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
      },
      body,
      cache: "no-store",
    },
  );

  return new NextResponse(await response.text(), {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
  });
}

import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.API_URL ?? 'http://localhost:8000';

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${API_URL}/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!upstream.ok || !upstream.body) {
      const detail = await upstream.text().catch(() => `HTTP ${upstream.status}`);
      return NextResponse.json(
        { error: detail || 'Upstream error' },
        { status: upstream.status },
      );
    }

    // Pipe the SSE stream straight through to the browser
    return new Response(upstream.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'X-Accel-Buffering': 'no', // disable nginx buffering in production
      },
    });
  } catch (err) {
    return NextResponse.json(
      { error: `Backend unreachable: ${(err as Error).message}` },
      { status: 502 },
    );
  }
}

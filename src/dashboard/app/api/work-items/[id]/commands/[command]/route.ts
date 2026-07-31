// Issue one workflow-kernel command against one work item.
//
//   POST /api/work-items/{id}/commands/{start|complete|skip|cancel|reassign}
//     body: { expected_version?, reason? }
//
// A thin proxy on purpose. Every rule that matters — may this role act on this
// node, is the transition legal, are the gates open, has someone else moved the
// item already — lives in the backend, and duplicating any of it here would
// create a second opinion that can disagree with the one that decides.

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../../../lib/backend-proxy";

// The kernel's whole vocabulary. Anything else is rejected before it leaves the
// dashboard rather than becoming a confusing 404 from the API.
const COMMANDS = new Set(["start", "complete", "skip", "cancel", "reassign"]);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; command: string }> },
) {
  const { id, command } = await params;

  if (!UUID_RE.test(id)) {
    return NextResponse.json({ error: "Mã đầu việc không hợp lệ" }, { status: 400 });
  }
  if (!COMMANDS.has(command)) {
    return NextResponse.json({ error: "Lệnh không hợp lệ" }, { status: 400 });
  }

  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    // A command with no body is normal — expected_version and reason are both
    // optional, and start/complete usually carry neither.
  }

  return proxyJsonToBackend(
    "POST",
    `/api/v1/work-items/${id}/commands/${command}`,
    body,
  );
}

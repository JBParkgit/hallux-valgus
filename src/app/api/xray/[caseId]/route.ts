import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ caseId: string }> },
) {
  const { caseId } = await params;

  // Sanitize: only allow alphanumeric + basic cuid chars
  if (!/^[a-zA-Z0-9_-]+$/.test(caseId)) {
    return new NextResponse("Invalid ID", { status: 400 });
  }

  const filePath = path.join(process.cwd(), "data", "xray_images", `${caseId}.png`);

  try {
    const buffer = await readFile(filePath);
    return new NextResponse(buffer, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "public, max-age=86400, immutable",
      },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}

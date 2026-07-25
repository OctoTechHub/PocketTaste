import { createReadStream, statSync } from "node:fs";
import { join, normalize, sep } from "node:path";
import { Readable } from "node:stream";

export const dynamic = "force-dynamic";

const ROOT = join(process.cwd(), "data", "videos");

/** Streams a downloaded MP4 from data/videos/ with HTTP Range support (seeking). */
export async function GET(req: Request) {
  const f = new URL(req.url).searchParams.get("f");
  if (!f) return new Response("Missing 'f'", { status: 400 });

  const target = normalize(join(ROOT, f));
  if (target !== ROOT && !target.startsWith(ROOT + sep)) {
    return new Response("Forbidden", { status: 403 });
  }

  let size: number;
  try {
    const stat = statSync(target);
    if (!stat.isFile()) return new Response("Not found", { status: 404 });
    size = stat.size;
  } catch {
    return new Response("Not found", { status: 404 });
  }

  const baseHeaders: Record<string, string> = {
    "Content-Type": "video/mp4",
    "Accept-Ranges": "bytes",
    "Cache-Control": "public, max-age=3600",
  };

  const range = req.headers.get("range");
  if (range) {
    const match = /bytes=(\d*)-(\d*)/.exec(range);
    let start = match?.[1] ? Number.parseInt(match[1], 10) : 0;
    let end = match?.[2] ? Number.parseInt(match[2], 10) : size - 1;
    if (Number.isNaN(start)) start = 0;
    if (Number.isNaN(end) || end >= size) end = size - 1;
    if (start > end || start >= size) {
      return new Response("Range Not Satisfiable", {
        status: 416,
        headers: { "Content-Range": `bytes */${size}` },
      });
    }
    const stream = createReadStream(target, { start, end });
    return new Response(Readable.toWeb(stream) as ReadableStream, {
      status: 206,
      headers: {
        ...baseHeaders,
        "Content-Range": `bytes ${start}-${end}/${size}`,
        "Content-Length": String(end - start + 1),
      },
    });
  }

  const stream = createReadStream(target);
  return new Response(Readable.toWeb(stream) as ReadableStream, {
    status: 200,
    headers: { ...baseHeaders, "Content-Length": String(size) },
  });
}

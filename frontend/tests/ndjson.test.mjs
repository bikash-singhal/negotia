import assert from "node:assert/strict";
import test from "node:test";

import { readNdjsonStream } from "../src/api/ndjson.ts";

test("parses UTF-8 events split across bytes and JSON lines", async () => {
  const encoded = new TextEncoder().encode(
    [
      JSON.stringify({ type: "started" }),
      JSON.stringify({ type: "delta", text: "Let’s discuss ₹ and 🤝." }),
      JSON.stringify({ type: "completed", turn: { id: "turn-id" } }),
    ].join("\n"),
  );
  const body = new ReadableStream({
    start(controller) {
      for (const byte of encoded) {
        controller.enqueue(Uint8Array.of(byte));
      }
      controller.close();
    },
  });
  const events = [];

  await readNdjsonStream(new Response(body), (event) => events.push(event));

  assert.deepEqual(events, [
    { type: "started" },
    { type: "delta", text: "Let’s discuss ₹ and 🤝." },
    { type: "completed", turn: { id: "turn-id" } },
  ]);
});

test("rejects a malformed JSON line", async () => {
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('{"type":"started"}\n{bad}\n'));
      controller.close();
    },
  });

  await assert.rejects(
    readNdjsonStream(new Response(body), () => undefined),
    SyntaxError,
  );
});

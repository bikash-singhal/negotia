export async function readNdjsonStream<T>(
  response: Response,
  onEvent: (event: T) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("The streaming response did not contain a body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      buffer = consumeCompleteLines(buffer, onEvent);
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      onEvent(parseLine<T>(buffer));
    }
  } finally {
    reader.releaseLock();
  }
}

function consumeCompleteLines<T>(
  buffer: string,
  onEvent: (event: T) => void,
): string {
  let lineEnd = buffer.indexOf("\n");
  while (lineEnd >= 0) {
    const line = buffer.slice(0, lineEnd).trim();
    buffer = buffer.slice(lineEnd + 1);
    if (line) {
      onEvent(parseLine<T>(line));
    }
    lineEnd = buffer.indexOf("\n");
  }
  return buffer;
}

function parseLine<T>(line: string): T {
  return JSON.parse(line) as T;
}

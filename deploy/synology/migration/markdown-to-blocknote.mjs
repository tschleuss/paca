// Use the reviewed, locked workstation MCP client's own Markdown converter.
// Input and output stay on this Mac; document contents are never executed.
import { markdownToBlocknote } from '../agents/node_modules/@paca-ai/paca-mcp/build/utils/converters.js';

// Pipes on macOS can be nonblocking; synchronous reads may fail with EAGAIN.
let raw = '';
process.stdin.setEncoding('utf8');
for await (const chunk of process.stdin) raw += chunk;
const input = JSON.parse(raw);
const output = {};
for (const [key, markdown] of Object.entries(input)) {
  output[key] = markdownToBlocknote(markdown);
}
process.stdout.write(JSON.stringify(output));

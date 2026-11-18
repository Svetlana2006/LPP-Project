import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const repositoryDir = path.resolve(frontendDir, "..");
const windows = process.platform === "win32";
const venvPython = path.join(
  repositoryDir,
  ".venv",
  windows ? "Scripts" : "bin",
  windows ? "python.exe" : "python",
);
const pythonCommand = existsSync(venvPython)
  ? venvPython
  : process.env.PYTHON || (windows ? "python" : "python3");
let stopping = false;
let api;
let vite;

function findFreePort(start, excluded = new Set()) {
  return new Promise((resolve, reject) => {
    let port = start;
    const tryPort = () => {
      if (excluded.has(port)) {
        port += 1;
        tryPort();
        return;
      }
      const server = createServer();
      server.once("error", (error) => {
        if (error.code === "EADDRINUSE") {
          port += 1;
          tryPort();
        } else {
          reject(error);
        }
      });
      server.listen(port, "127.0.0.1", () => {
        server.close((error) => (error ? reject(error) : resolve(port)));
      });
    };
    tryPort();
  });
}

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  api?.kill();
  vite?.kill();
  process.exitCode = code;
}

async function start() {
  const apiPort = await findFreePort(5174);
  const webPort = await findFreePort(5173, new Set([apiPort]));
  const environment = {
    ...process.env,
    DEMO_API_PORT: String(apiPort),
    VITE_API_PORT: String(apiPort),
    VITE_PORT: String(webPort),
  };
  api = spawn(pythonCommand, [path.join(frontendDir, "api.py")], {
    cwd: repositoryDir,
    env: environment,
    stdio: "inherit",
  });
  vite = spawn(
    process.execPath,
    [path.join(frontendDir, "node_modules", "vite", "bin", "vite.js"), "--host", "127.0.0.1"],
    { cwd: frontendDir, env: environment, stdio: "inherit" },
  );

  for (const [child, label] of [[api, "the Python API"], [vite, "Vite"]]) {
    child.on("error", (error) => {
      console.error(`Unable to start ${label}:`, error);
      stop(1);
    });
    child.on("exit", (code) => {
      if (!stopping) {
        console.error(`${label} stopped unexpectedly (exit ${code}).`);
        stop(code ?? 1);
      }
    });
  }
}

start().catch((error) => {
  console.error("Unable to select local development ports:", error);
  stop(1);
});
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

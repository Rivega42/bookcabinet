/**
 * Main Express server entry point.
 * Initializes HTTP server, registers routes, sets up Vite for development.
 * Handles global NFC/PCSC error recovery.
 */
import { initSentry } from "./lib/sentry";
// Must be called before anything else that could throw.
initSentry();

import express, { type Request, Response, NextFunction } from "express";
import { registerRoutes } from "./routes";
import { setupVite, serveStatic, log } from "./vite";

// Global error handlers to prevent app crashes from NFC/PCSC errors
process.on('uncaughtException', (error) => {
  console.error('🚨 Uncaught Exception (NFC/PCSC):', error.message);
  if (error.message.includes('Cannot process ISO 14443-4 tag') || error.message.includes('AID')) {
    console.log('💡 ISO 14443-4 card detected but AID not configured - continuing...');
    return; // Don't crash the app
  }
  console.error('💥 Application will exit due to uncaught exception');
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('🚨 Unhandled Promise Rejection:', reason);
  console.log('📍 Promise:', promise);
});

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: false }));

app.use((req, res, next) => {
  const start = Date.now();
  const path = req.path;
  let capturedJsonResponse: Record<string, any> | undefined = undefined;

  const originalResJson = res.json;
  res.json = function (bodyJson, ...args) {
    capturedJsonResponse = bodyJson;
    return originalResJson.apply(res, [bodyJson, ...args]);
  };

  res.on("finish", () => {
    const duration = Date.now() - start;
    if (path.startsWith("/api")) {
      let logLine = `${req.method} ${path} ${res.statusCode} in ${duration}ms`;
      if (capturedJsonResponse) {
        logLine += ` :: ${JSON.stringify(capturedJsonResponse)}`;
      }

      if (logLine.length > 80) {
        logLine = logLine.slice(0, 79) + "…";
      }

      log(logLine);
    }
  });

  next();
});

(async () => {
  const server = await registerRoutes(app);

  app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
    const status = err.status || err.statusCode || 500;
    const message = err.message || "Internal Server Error";

    res.status(status).json({ message });
    console.error('[server]', err.stack || err);
  });

  // importantly only setup vite in development and after
  // setting up all the other routes so the catch-all route
  // doesn't interfere with the other routes
  if (app.get("env") === "development") {
    await setupVite(app, server);
  } else {
    serveStatic(app);
  }

  // ALWAYS serve the app on the port specified in the environment variable PORT
  // Other ports are firewalled. Default to 5000 if not specified.
  // this serves both the API and the client.
  // It is the only port that is not firewalled.
  const port = parseInt(process.env.PORT || '5000', 10);
  
  // HOST из окружения (systemd на Pi и docker ставят 0.0.0.0);
  // без него — localhost для Windows, 0.0.0.0 для Replit.
  const host = process.env.HOST || (process.env.REPLIT_DEPLOYMENT_ID ? "0.0.0.0" : "127.0.0.1");
  
  server.listen({
    port,
    host,
    reusePort: !process.platform.includes('win32'), // reusePort not supported on Windows
  }, () => {
    log(`serving on port ${port} (host: ${host})`);
  });
})();

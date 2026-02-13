// HACK in place instead of setting up nginx to route requests to api/ to the backend service
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import path from 'path';
import { handler } from './build/handler.js';

const app = express();
const PORT = parseInt(process.env.PORT, 10) || 3000;

// Proxy /api requests to backend service
app.use(
  '/api',
  createProxyMiddleware({
    target: 'http://' + process.env.VITE_SERVER_HOST,
    changeOrigin: true,
    ws: true,
  }),
);

app.use(handler);

// Serve Svelte app's static files
app.use(express.static(path.join(import.meta.url, 'build')));

app.listen(PORT, () => {
  console.log(`Server running on port http://0.0.0.0:${PORT}`);
});

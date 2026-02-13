import { defineConfig, loadEnv } from 'vite';
import { sveltekit } from '@sveltejs/kit/vite';
import path from 'path';

// https://vitejs.dev/config/
export default ({ mode }) => {
  process.env = { ...process.env, ...loadEnv(mode, process.cwd()) };

  return defineConfig({
    plugins: [sveltekit()],
    resolve: {
      alias: {
        '@src': path.resolve('./src'),
        '@shared': path.resolve('./src/routes/application/components/shared'),
        '@store': path.resolve('./src/routes/application/storage/store.js'),
        '@alert': path.resolve('./src/routes/application/storage/alert.js'),
        '$lib': path.resolve('./src/lib'),
        '@assets': path.resolve('./src/assets'),
        // TODO: unify $lib and @lib
        '@lib': path.resolve('./src/routes/application/lib'),
        '@sveltejs': path.resolve('./node_modules/@sveltejs'),
        '@icons': path.resolve('./src/icons'),
      },
    },
    server: {
      proxy: {
        // TODO: Setup vite as a proxy server so to not deal with CORS
        '/api': {
          target: `http://${process.env.VITE_SERVER_HOST}`,
          changeOrigin: true,
          secure: false,
          ws: true,
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('proxy error', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('Sending Request to the Target:', req.method, req.url);
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
            });
          },
        },
      },
    },
  });
};
import path from 'path';
import { build } from 'esbuild';

await build({
  entryPoints: {
    base_bundle: path.resolve('themes/bienensteff/assets_src/js/main.ts'),
    bundle: path.resolve('assets_src/js/main.ts'),
    base_style: path.resolve('themes/bienensteff/assets_src/css/main.css'),
    style: path.resolve('assets_src/css/style.css'),
  },
  outdir: 'assets',
  bundle: true,
  sourcemap: true,
  minify: false,
  target: 'es2024',
  format: 'esm',
  logLevel: 'info',
  loader: {
    '.woff': 'file',
    '.woff2': 'file'
  },
  assetNames: '[name]',
});

import fs from 'fs';
import path from 'path';
import * as esbuild from 'esbuild';

const args = process.argv.slice(2);
const isWatchMode = args.includes('--watch');

const outdir = 'assets/gen';

async function runBuild() {
  try {
    // Chunk names carry a content hash, so every change leaves the old ones
    // behind -- start from an empty outdir so Hugo doesn't publish stale
    // chunks (it publishes everything under gen/chunks/, see
    // themes/bienensteff/layouts/_partials/head/js.html).
    fs.rmSync(outdir, { recursive: true, force: true });

    const ctx = await esbuild.context({
      entryPoints: {
        base_bundle: path.resolve('themes/bienensteff/bundle_src/js/main.ts'),
        bundle: path.resolve('bundle_src/js/main.ts'),
        base_style: path.resolve('themes/bienensteff/bundle_src/css/main.css'),
        style: path.resolve('bundle_src/css/style.css'),
      },
      outdir,
      // Widget code is loaded via dynamic import() only on pages that need
      // it (see bundle_src/js/main.ts); shared and lazily loaded code ends
      // up in content-hashed chunks next to the entry bundles.
      splitting: true,
      chunkNames: 'chunks/[name]-[hash]',
      bundle: true,
      sourcemap: true,
      minify: true,
      target: 'es2024',
      format: 'esm',
      logLevel: 'info',
      loader: {
        '.woff': 'file',
        '.woff2': 'file'
      },
      assetNames: '[name]',
    });

    if (isWatchMode) {
      await ctx.watch();
    } else {
      const result = await ctx.rebuild();
      console.log('Build completed successfully:', result);

      await ctx.dispose();
      process.exit(0);
    }

  } catch (error) {
    console.error('Build failed:', error);
    process.exit(1);
  }
}

runBuild();
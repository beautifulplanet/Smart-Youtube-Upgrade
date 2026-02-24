/**
 * YouTube Safety Inspector — Cross-Browser Build Script
 * 
 * Usage:
 *   node build.js --target=chrome        Build for Chrome
 *   node build.js --target=firefox       Build for Firefox
 *   node build.js --target=edge          Build for Edge
 *   node build.js --target=all           Build for all browsers
 *   node build.js --target=chrome --dev  Build for Chrome (dev mode, keeps localhost)
 *   node build.js --target=chrome --watch  Watch mode (auto-rebuild on changes)
 * 
 * Output: dist/<browser>/
 */

const fs = require('fs-extra');
const path = require('path');

// --- Configuration ---

const ROOT = __dirname;
const EXT_SRC = path.join(ROOT, 'extension');
const DIST = path.join(ROOT, 'dist');
const MANIFESTS_DIR = path.join(EXT_SRC, 'manifests');
const POLYFILL_SRC = path.join(ROOT, 'node_modules', 'webextension-polyfill', 'dist', 'browser-polyfill.min.js');

const TARGETS = ['chrome', 'firefox', 'edge'];

// Files/folders to copy from extension/ to dist/<browser>/
const COPY_ITEMS = [
  'background',
  'content',
  'popup',
  'icons',
];

// Files/folders to SKIP (not part of the distributable)
const SKIP_ITEMS = [
  'manifests',
  'manifest.json',
  'manifest.prod.json',
];

// --- Parse CLI args ---

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {
    targets: [],
    dev: false,
    watch: false,
  };

  for (const arg of args) {
    if (arg.startsWith('--target=')) {
      const target = arg.split('=')[1];
      if (target === 'all') {
        config.targets = [...TARGETS];
      } else if (TARGETS.includes(target)) {
        config.targets.push(target);
      } else {
        console.error(`❌ Unknown target: ${target}. Valid targets: ${TARGETS.join(', ')}, all`);
        process.exit(1);
      }
    } else if (arg === '--dev') {
      config.dev = true;
    } else if (arg === '--watch') {
      config.watch = true;
    }
  }

  if (config.targets.length === 0) {
    config.targets = ['chrome']; // Default to Chrome
  }

  return config;
}

// --- Build Functions ---

/**
 * Build the extension for a specific browser target.
 * @param {string} target - Browser target (chrome, firefox, edge)
 * @param {boolean} isDev - Whether this is a dev build
 */
async function buildTarget(target, isDev) {
  const targetDir = path.join(DIST, target);
  const startTime = Date.now();

  console.log(`\n🔨 Building for ${target}${isDev ? ' (dev)' : ''}...`);

  // 1. Clean target directory
  await fs.remove(targetDir);
  await fs.ensureDir(targetDir);

  // 2. Copy extension source files
  for (const item of COPY_ITEMS) {
    const src = path.join(EXT_SRC, item);
    const dest = path.join(targetDir, item);

    if (await fs.pathExists(src)) {
      await fs.copy(src, dest);
      console.log(`  📁 Copied ${item}/`);
    } else {
      console.log(`  ⚠️  Skipped ${item}/ (not found)`);
    }
  }

  // 3. Copy the correct manifest for this browser
  const manifestSrc = path.join(MANIFESTS_DIR, `manifest.${target}.json`);
  const manifestDest = path.join(targetDir, 'manifest.json');

  if (await fs.pathExists(manifestSrc)) {
    let manifest = await fs.readJson(manifestSrc);

    // In production builds, remove localhost from host_permissions
    if (!isDev) {
      if (manifest.host_permissions) {
        manifest.host_permissions = manifest.host_permissions.filter(
          hp => !hp.includes('localhost') && !hp.includes('127.0.0.1')
        );
      }
    }

    await fs.writeJson(manifestDest, manifest, { spaces: 2 });
    console.log(`  📋 Manifest: manifest.${target}.json`);
  } else {
    console.error(`  ❌ Manifest not found: ${manifestSrc}`);
    process.exit(1);
  }

  // 4. Copy webextension-polyfill
  const libDir = path.join(targetDir, 'lib');
  await fs.ensureDir(libDir);

  if (await fs.pathExists(POLYFILL_SRC)) {
    await fs.copy(POLYFILL_SRC, path.join(libDir, 'browser-polyfill.min.js'));
    console.log('  📦 Copied browser-polyfill.min.js');
  } else {
    console.error('  ❌ webextension-polyfill not found. Run: npm install');
    process.exit(1);
  }

  // 5. Calculate build size
  const size = await getDirSize(targetDir);
  const elapsed = Date.now() - startTime;

  console.log(`  ✅ ${target} build complete (${formatSize(size)}, ${elapsed}ms)`);
}

/**
 * Get total size of a directory in bytes.
 */
async function getDirSize(dirPath) {
  let totalSize = 0;
  const items = await fs.readdir(dirPath, { withFileTypes: true });

  for (const item of items) {
    const fullPath = path.join(dirPath, item.name);
    if (item.isDirectory()) {
      totalSize += await getDirSize(fullPath);
    } else {
      const stat = await fs.stat(fullPath);
      totalSize += stat.size;
    }
  }

  return totalSize;
}

/**
 * Format bytes into human-readable string.
 */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

/**
 * Start watch mode — rebuild on source file changes.
 */
async function startWatch(config) {
  let chokidar;
  try {
    chokidar = require('chokidar');
  } catch {
    console.error('❌ chokidar not installed. Run: npm install');
    process.exit(1);
  }

  console.log('\n👀 Watch mode started. Watching extension/ for changes...');
  console.log('   Press Ctrl+C to stop.\n');

  const watcher = chokidar.watch(EXT_SRC, {
    ignored: [
      /(^|[\/\\])\../,       // dotfiles
      /node_modules/,
      /manifests/,           // Don't watch manifests dir (we read it during build)
    ],
    persistent: true,
    ignoreInitial: true,
  });

  let buildTimeout = null;
  const DEBOUNCE_MS = 300;

  const rebuild = () => {
    if (buildTimeout) clearTimeout(buildTimeout);
    buildTimeout = setTimeout(async () => {
      console.log('\n🔄 Change detected, rebuilding...');
      for (const target of config.targets) {
        await buildTarget(target, config.dev);
      }
      console.log('\n👀 Watching for changes...');
    }, DEBOUNCE_MS);
  };

  watcher
    .on('change', (filePath) => {
      console.log(`  📝 Changed: ${path.relative(EXT_SRC, filePath)}`);
      rebuild();
    })
    .on('add', (filePath) => {
      console.log(`  ➕ Added: ${path.relative(EXT_SRC, filePath)}`);
      rebuild();
    })
    .on('unlink', (filePath) => {
      console.log(`  ➖ Removed: ${path.relative(EXT_SRC, filePath)}`);
      rebuild();
    });
}

// --- Main ---

async function main() {
  const config = parseArgs();

  console.log('═══════════════════════════════════════════════');
  console.log('  YouTube Safety Inspector — Build System');
  console.log('═══════════════════════════════════════════════');
  console.log(`  Targets: ${config.targets.join(', ')}`);
  console.log(`  Mode:    ${config.dev ? 'Development' : 'Production'}`);
  console.log(`  Watch:   ${config.watch ? 'Yes' : 'No'}`);

  // Initial build
  for (const target of config.targets) {
    await buildTarget(target, config.dev);
  }

  console.log('\n═══════════════════════════════════════════════');
  console.log(`  Build complete: ${config.targets.length} target(s)`);
  console.log('═══════════════════════════════════════════════');

  // Start watch mode if requested
  if (config.watch) {
    await startWatch(config);
  }
}

main().catch((err) => {
  console.error('❌ Build failed:', err);
  process.exit(1);
});

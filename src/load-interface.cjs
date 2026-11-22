'use strict';

const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const { readFileSync, lstatSync } = require('node:fs');
const { homedir } = require('node:os');
const path = require('node:path');
const { setTimeout: wait } = require('node:timers/promises');

const [pid, viewerDir] = process.argv.slice(2);
assert.match(pid, /^[1-9]\d*$/);

const { createCdpClient, discoverAntigravityCdp } = require(path.join(viewerDir, 'local-api.js'));
const portFile = path.join(homedir(), 'Library/Application Support/Antigravity/DevToolsActivePort');
const asarPath = '/Applications/Antigravity.app/Contents/Resources/app.asar';

async function waitForMainPage() {
  for (let attempt = 0; attempt < 45; attempt++) {
    process.kill(Number(pid), 0);
    try {
      const file = lstatSync(portFile);
      assert(file.isFile() && file.uid === process.getuid());
      const [port] = readFileSync(portFile, 'utf8').split('\n');
      assert.match(port, /^[1-9]\d{0,4}$/);
      const listeners = execFileSync('/usr/sbin/lsof', [
        '-nP', '-a', '-p', pid, '-iTCP:' + port, '-sTCP:LISTEN', '-Fn'
      ], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 2000 })
        .split('\n').filter((line) => line.startsWith('n'));
      assert.deepEqual(listeners, ['n127.0.0.1:' + port]);
      return await discoverAntigravityCdp({ port, strictPort: true, timeoutMs: 1000 });
    } catch {
      await wait(500);
    }
  }
  throw new Error('官方窗口的回环调试端口未就绪');
}

async function main() {
  const { port, page } = await waitForMainPage();
  // 复用 Context Viewer 的简体中文词库和运行时，保护对话正文和输入区域。
  const dictionary = JSON.parse(readFileSync(path.join(viewerDir, 'i18n/zh-CN.json'), 'utf8'));
  const engine = readFileSync(path.join(viewerDir, 'i18n/i18n-runtime.js'), 'utf8');
  const anchor = "if (el.isContentEditable) return true;";
  assert(engine.includes(anchor), '汉化引擎版本需要重新核对');
  const protectedEngine = engine.replace(anchor, anchor +
    '\n    if (el.closest && el.closest("#ag-context-meter, [data-markdown-root], [contenteditable]")) return true;');
  const origin = new URL(page.url).origin;
  const websocket = new URL(page.webSocketDebuggerUrl);
  assert.equal(websocket.protocol, 'ws:');
  assert.equal(websocket.hostname, '127.0.0.1');
  assert.equal(websocket.port, String(port));
  const cdp = await createCdpClient(websocket.href);
  try {
    const source = [
      '(() => {',
      'if (location.origin !== ' + JSON.stringify(origin) + ' || window.top !== window) return false;',
      'window.__AGY_I18N_CONFIG__ = { enabled: true, language: "zh-CN", brandTitle: "english" };',
      'window.__AGY_I18N_DATA__ = ' + JSON.stringify(dictionary) + ';',
      protectedEngine,
      'return window.__AGY_TRANSLATE_UNIT__?.("New Conversation") === "新建会话";',
      '})()',
    ].join('\n');
    assert.equal(await cdp.evaluateValue(source), true);
    console.log('简体中文已挂载。');
  } finally {
    cdp.close();
  }

  execFileSync(process.execPath, [
    path.join(viewerDir, 'cli.js'), 'live', '--path', asarPath, '--port', String(port)
  ], { cwd: viewerDir, stdio: 'inherit', timeout: 30000 });
}

main().catch((error) => {
  console.error('增强加载停止：' + error.message);
  process.exitCode = 1;
});

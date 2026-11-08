// リプレイで起動した Day のツリーから、画面のスクショを撮る（A7a・R-10）。
// 標準入力に JSON: { base, shots: [{name, path, login}], login: {path, fields: {セレクタ: 値}, submit}, out, width, height }
// 配色はライトに固定する（v0.2 はダークモードを対象にしない。OS の設定でスクショと画面がずれないように）。
// 結果は標準出力に JSON: [{name, ok, status, file, error}]
const { chromium } = require("playwright");

async function main() {
  const input = JSON.parse(require("fs").readFileSync(0, "utf-8"));
  const browser = await chromium.launch();
  const results = [];
  try {
    const context = await browser.newContext({
      viewport: { width: input.width || 1280, height: input.height || 800 },
      colorScheme: "light",
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    let loggedIn = false;
    for (const shot of input.shots) {
      try {
        if (shot.login && !loggedIn) {
          const l = input.login;
          if (!l) throw new Error("login が要る画面なのに replay.login が無い");
          await page.goto(input.base + l.path);
          for (const [sel, val] of Object.entries(l.fields)) await page.fill(sel, val);
          await Promise.all([page.waitForLoadState("networkidle"), page.click(l.submit)]);
          loggedIn = true;
        }
        const resp = await page.goto(input.base + shot.path, { waitUntil: "networkidle" });
        const file = require("path").join(input.out, `${shot.name}.png`);
        await page.screenshot({ path: file, fullPage: true });
        const status = resp ? resp.status() : 0;
        results.push({ name: shot.name, ok: status === 200, status, file });
      } catch (e) {
        results.push({ name: shot.name, ok: false, status: 0, error: String(e && e.message ? e.message : e) });
      }
    }
  } finally {
    await browser.close();
  }
  process.stdout.write(JSON.stringify(results));
}

main().catch((e) => {
  process.stderr.write(String(e && e.stack ? e.stack : e));
  process.exit(1);
});

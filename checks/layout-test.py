import asyncio, json, os, time
from playwright.async_api import async_playwright

ROOT = "/workspace"
URL = "https://syd89111259-cpu.github.io/Sindonga-tools/"
OUT = os.path.join(ROOT, "work/shindonga-tools/checks")

async def main():
    rep = {"console": [], "pageerrors": []}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w, tag in [(1440, "pc"), (390, "mobile")]:
            ctx = await b.new_context(viewport={"width": w, "height": 1000})
            page = await ctx.new_page()
            page.on("console", lambda m, t=tag: rep["console"].append(f"[{t}] {m.type}: {m.text}") if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e, t=tag: rep["pageerrors"].append(f"[{t}] {e}"))
            await page.goto(URL + "?v=" + str(int(time.time())), wait_until="load")
            await page.wait_for_timeout(1200)
            # 직접 지정 모드로 펼친 뒤 레이아웃 측정
            await page.select_option("#apiMonths", "custom")
            await page.wait_for_timeout(400)
            rep[tag] = await page.evaluate("""() => {
                const out = {scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth, offenders: []};
                document.querySelectorAll('#pane-api *').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.right > window.innerWidth + 1) out.offenders.push({sel: el.tagName + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').join('.') : ''), right: Math.round(r.right), width: Math.round(r.width)});
                });
                const row = document.querySelector('#pane-api .row');
                out.rowChildren = Array.from(row.children).map(c => ({tag: c.tagName, cls: c.className, w: Math.round(c.getBoundingClientRect().width), top: Math.round(c.getBoundingClientRect().top)}));
                out.hint = (document.querySelector('#rangeHint').innerText||'').slice(0,80);
                return out;
            }""")
            await page.screenshot(path=os.path.join(OUT, f"layout-{tag}.png"), full_page=False)
            await ctx.close()
        await b.close()
    print(json.dumps(rep, ensure_ascii=False, indent=1))

asyncio.run(main())

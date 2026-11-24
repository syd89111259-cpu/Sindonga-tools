import asyncio, json, os, subprocess, time
from playwright.async_api import async_playwright

ROOT = "/workspace"
URL = "https://syd89111259-cpu.github.io/Sindonga-tools/"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--allow-file-access-from-files"])
        res = {}
        for label, url in [("new-live", URL + "?v=" + str(int(time.time()))), ("old-file", "file:///tmp/old.html")]:
            ctx = await b.new_context(viewport={"width": 390, "height": 1000})
            page = await ctx.new_page()
            await page.goto(url, wait_until="load")
            await page.wait_for_timeout(1500)
            res[label] = await page.evaluate("""() => {
                const out = {scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth, offenders: []};
                document.querySelectorAll('body *').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.right > window.innerWidth + 1 && r.width > 0) out.offenders.push({sel: el.tagName + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : ''), right: Math.round(r.right), w: Math.round(r.width)});
                });
                out.offenders = out.offenders.slice(0, 12);
                return out;
            }""")
            await page.screenshot(path=f"{ROOT}/work/shindonga-tools/checks/overflow-{label}.png", full_page=False)
            await ctx.close()
        await b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))

asyncio.run(main())

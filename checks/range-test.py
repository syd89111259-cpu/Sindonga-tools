import asyncio, json, os, sys, time
from playwright.async_api import async_playwright

ROOT = "/workspace"
URL = "https://syd89111259-cpu.github.io/Sindonga-tools/"
OUT = os.path.join(ROOT, "work/shindonga-tools/checks")
os.makedirs(OUT, exist_ok=True)

keydata = json.load(open(os.path.join(ROOT, "real_estate/data_go_kr.json")))
APIKEY = keydata["service_key"]


async def main():
    report = {"console": [], "pageerrors": [], "checks": {}}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 1200}, device_scale_factor=1)
        page = await ctx.new_page()
        page.on("console", lambda m: report["console"].append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: report["pageerrors"].append(str(e)))
        page.set_default_timeout(120000)

        await page.goto(URL + "?v=" + str(int(time.time())), wait_until="load")
        await page.wait_for_timeout(1500)

        # 1) 범위 옵션 구성
        report["checks"]["options"] = await page.evaluate(
            "() => Array.from(document.querySelectorAll('#apiMonths option')).map(o => [o.value, o.textContent.trim()])"
        )
        report["checks"]["initial_deals"] = await page.evaluate("() => window.__app.state.deals.length")

        # 2) API 키를 localStorage에 임시 저장 (이 테스트 브라우저에만)
        await page.evaluate("k => localStorage.setItem('shindonga.apiKey.dataGoKr', k)", APIKEY)
        await page.reload(wait_until="load")
        await page.wait_for_timeout(1500)
        report["checks"]["keySaved"] = await page.evaluate("() => !!window.__app.getApiKey()")
        await page.screenshot(path=os.path.join(OUT, "range-ui-initial.png"), full_page=False)

        async def fetch_with_progress(label, prepare):
            """prepare() 로 기간을 정하고 불러오기 → 진행표시 수집 → 결과 상태"""
            await prepare()
            await page.wait_for_timeout(300)
            progress = []
            await page.click("#btnFetch")
            for _ in range(120):
                txt = await page.evaluate("() => (document.querySelector('#apiStatus').innerText || '').replace(/\\s+/g,' ').trim()")
                if txt and txt not in progress:
                    progress.append(txt)
                done = await page.evaluate("() => !document.querySelector('#btnFetch').disabled")
                if done and "불러오는" not in txt:
                    break
                await page.wait_for_timeout(250)
            await page.wait_for_timeout(500)
            status = await page.evaluate("() => (document.querySelector('#apiStatus').innerText||'').replace(/\\s+/g,' ').trim()")
            info = await page.evaluate("""() => ({
                deals: window.__app.state.deals.length,
                selected: window.__app.state.deals.filter(d => d.selected).length,
                subtitle: document.querySelector('#inSubtitle').value,
                listCount: document.querySelector('#listCount').textContent,
                moreBtn: !!document.querySelector('#btnMoreRows'),
                rows: document.querySelectorAll('#dealList li.deal').length,
                canvas: [document.querySelector('#cardCanvas').width, document.querySelector('#cardCanvas').height]
            })""")
            return {"progress": progress[:14], "status": status, "info": info}

        # 3) 최근 1년(12개월)
        async def pick_year():
            await page.select_option("#apiMonths", "12")
        report["checks"]["year"] = await fetch_with_progress("1년", pick_year)
        await page.screenshot(path=os.path.join(OUT, "range-year-result.png"), full_page=False)

        # 4) 평형별 최고가 (1년 데이터 전체 기준)
        await page.click("#btnSelMax")
        await page.wait_for_timeout(800)
        report["checks"]["maxByPyeong"] = await page.evaluate("""() => ({
            selected: window.__app.state.deals.filter(d => d.selected).length,
            names: window.__app.state.deals.filter(d => d.selected).map(d => [d.name, d.area, d.amount, d.date]),
            sortBy: document.querySelector('#sortBy').value,
            sns: (document.querySelector('#snsText').value||'').slice(0, 160)
        })""")
        await page.screenshot(path=os.path.join(OUT, "range-year-max.png"), full_page=False)

        # 5) 기간 직접 지정 (2026-02 ~ 2026-07)
        async def pick_custom():
            await page.select_option("#apiMonths", "custom")
            await page.wait_for_timeout(200)
            await page.fill("#apiFromYm", "2026-02")
            await page.dispatch_event("#apiFromYm", "change")
            await page.fill("#apiToYm", "2026-07")
            await page.dispatch_event("#apiToYm", "change")
        report["checks"]["custom"] = await fetch_with_progress("직접", pick_custom)
        report["checks"]["custom_hint"] = await page.evaluate("() => (document.querySelector('#rangeHint').innerText||'').replace(/\\s+/g,' ').trim()")
        await page.screenshot(path=os.path.join(OUT, "range-custom-result.png"), full_page=False)

        # 6) 역전 입력 자동 보정 (시작 2026-09, 끝 2026-03)
        await page.fill("#apiFromYm", "2026-09")
        await page.dispatch_event("#apiFromYm", "change")
        await page.fill("#apiToYm", "2026-03")
        await page.dispatch_event("#apiToYm", "change")
        await page.wait_for_timeout(300)
        report["checks"]["swap"] = await page.evaluate("() => ({ from: document.querySelector('#apiFromYm').value, to: document.querySelector('#apiToYm').value, hint: (document.querySelector('#rangeHint').innerText||'').replace(/\\s+/g,' ').trim() })")

        # 7) 24개월 초과 상한 (2020-01 ~ 2026-11 → 끝월 기준 24개월)
        await page.fill("#apiFromYm", "2020-01")
        await page.dispatch_event("#apiFromYm", "change")
        await page.wait_for_timeout(300)
        report["checks"]["clamp"] = await page.evaluate("() => ({ from: document.querySelector('#apiFromYm').value, to: document.querySelector('#apiToYm').value, hint: (document.querySelector('#rangeHint').innerText||'').replace(/\\s+/g,' ').trim() })")

        # 8) 6개월 선택 + 목록 더 보기 동작
        await page.select_option("#apiMonths", "6")
        await page.wait_for_timeout(200)
        await page.click("#btnFetch")
        for _ in range(120):
            done = await page.evaluate("() => !document.querySelector('#btnFetch').disabled")
            if done:
                break
            await page.wait_for_timeout(250)
        await page.wait_for_timeout(500)
        report["checks"]["six"] = await page.evaluate("""() => ({
            deals: window.__app.state.deals.length,
            subtitle: document.querySelector('#inSubtitle').value,
            listCount: document.querySelector('#listCount').textContent,
            rows: document.querySelectorAll('#dealList li.deal').length,
            moreBtn: !!document.querySelector('#btnMoreRows'),
            status: (document.querySelector('#apiStatus').innerText||'').replace(/\\s+/g,' ').trim()
        })""")
        if await page.evaluate("() => !!document.querySelector('#btnMoreRows')"):
            await page.click("#btnMoreRows")
            await page.wait_for_timeout(600)
            report["checks"]["afterMore"] = await page.evaluate("""() => ({
                rows: document.querySelectorAll('#dealList li.deal').length,
                listCount: document.querySelector('#listCount').textContent
            })""")

        # 9) 단지명 필터(목련) + 기간 직접 지정 조합 — 실무 시나리오
        async def pick_mokryeon_year():
            await page.fill("#apiKw", "목련")
            await page.select_option("#apiMonths", "custom")
            await page.wait_for_timeout(200)
            await page.fill("#apiFromYm", "2025-12")
            await page.dispatch_event("#apiFromYm", "change")
            await page.fill("#apiToYm", "2026-11")
            await page.dispatch_event("#apiToYm", "change")
        report["checks"]["mokryeon_year"] = await fetch_with_progress("목련1년", pick_mokryeon_year)
        await page.screenshot(path=os.path.join(OUT, "range-mokryeon-year.png"), full_page=False)

        # 10) 모바일 폭에서 레이아웃 확인
        await page.set_viewport_size({"width": 390, "height": 900})
        await page.wait_for_timeout(600)
        report["checks"]["mobile"] = await page.evaluate("""() => {
            const row = document.querySelector('#customRangeRow');
            const r = row.getBoundingClientRect();
            return { visible: !row.hidden, width: Math.round(r.width), overflowX: document.documentElement.scrollWidth > window.innerWidth };
        }""")
        await page.screenshot(path=os.path.join(OUT, "range-mobile-custom.png"), full_page=False)

        # 임시 저장한 키 정리
        await page.evaluate("() => localStorage.removeItem('shindonga.apiKey.dataGoKr')")
        report["checks"]["keyCleared"] = await page.evaluate("() => !window.__app.getApiKey()")
        await ctx.close()
        await browser.close()

    print(json.dumps(report, ensure_ascii=False, indent=1))


asyncio.run(main())

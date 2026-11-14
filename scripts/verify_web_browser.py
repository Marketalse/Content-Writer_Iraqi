"""No-cost browser smoke checks. Requires playwright + Chromium; refuses non-demo servers."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8877')
    parser.add_argument('--chromium',default='/usr/bin/chromium')
    parser.add_argument('--out',default='test_reports/web')
    args=parser.parse_args()
    with urlopen(args.url+'/health') as response:health=json.load(response)
    if health.get('mode')!='demo':raise SystemExit('Browser smoke test requires explicit demo mode; no model calls allowed.')
    from playwright.sync_api import sync_playwright
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(args.url)
        page.wait_for_function("document.querySelector('#strategy').options.length===8")
        page.screenshot(path=str(out/'workshop-desktop.png'),full_page=True)
        page.locator('#topic').fill('زبونك كيان؛ ليش ترسل نفس الرسالة للكل؟')
        page.locator('#strategy').select_option('hot_take')
        page.locator('#generate').click()
        page.locator('#script').wait_for(state='visible')
        assert page.locator('#script').inner_text()
        assert page.locator('#demo-notice').is_visible()
        assert page.locator('#result-badge').inner_text()=='Sample output'
        assert page.locator('#result-score').inner_text()==''
        first=page.locator('#request-ref').inner_text()
        page.locator('#edit').fill('خلي البداية أقصر وأكثر مباشرة')
        page.locator('#edit-submit').click()
        page.wait_for_function('(first)=>document.querySelector("#request-ref").textContent!==first',arg=first)
        page.locator('#script').wait_for(state='visible')
        page.locator('[data-view="library"]').click()
        page.locator('.library-item').first.wait_for()
        assert page.locator('.library-item').count()>=2
        page.locator('.library-item').first.click()
        assert page.locator('#script').is_visible()
        page.screenshot(path=str(out/'workshop-result.png'),full_page=True)
        page.locator('[data-view="progress"]').click()
        page.locator('.milestone').first.wait_for()
        assert page.locator('.milestone').count()==6
        page.screenshot(path=str(out/'workshop-progress.png'),full_page=True)
        mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        phone=mobile.new_page();phone.on('pageerror',lambda error:errors.append(str(error)))
        phone.goto(args.url)
        phone.wait_for_function("document.querySelector('#strategy').options.length===8")
        assert phone.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        phone.locator('#topic').fill('شلون نخلي الرد واضح للزبون؟')
        phone.locator('#generate').click()
        phone.locator('#script').wait_for(state='visible')
        assert phone.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        phone.screenshot(path=str(out/'workshop-mobile.png'),full_page=True)
        assert not errors,errors
        browser.close()
    report={'mode':'demo','paid_model_calls':0,'passed':True,
        'checks':['desktop create','treatment selection','sample-only output','edit submission',
                  'library reopen','six milestones','mobile create','no horizontal overflow','no JavaScript errors']}
    (out/'browser.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()

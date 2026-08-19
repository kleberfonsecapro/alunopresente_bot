import asyncio
from playwright.async_api import async_playwright
from aluno_presente_sme.skills.auth_skill import get_storage_state

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=get_storage_state())
        page = await context.new_page()

        results = []
        page.on('response', lambda r: results.append(r))

        await page.goto('https://cba.alunopresente.srv.br/alunopresente/dashboard-secretario', timeout=30000)
        await page.wait_for_timeout(15000)

        # Find the analise diaria data in responses
        for r in results:
            url = r.url
            if r.status != 200:
                continue
            try:
                ct = r.headers.get('content-type', '')
                if 'json' not in ct:
                    continue
                body = await r.json()
                if isinstance(body, dict):
                    keys = list(body.keys())
                    if 'presentes' in str(body).lower() or 'ausentes' in str(body).lower() or 'alimentados' in str(body).lower():
                        print(f'URL: {url}')
                        print(f'Keys: {keys}')
                        print(f'Data: {body}')
                        print()
                    elif any(k in str(body) for k in ['comFoto', 'semFoto', 'presente', 'ausente', 'alimentado']):
                        print(f'URL: {url}')
                        print(f'Keys: {keys}')
                        print(f'Data: {body}')
                        print()
            except:
                pass

        await browser.close()

asyncio.run(main())

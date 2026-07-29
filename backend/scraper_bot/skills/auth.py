from pathlib import Path

from playwright.async_api import async_playwright

from scraper_bot.skills.auth_skill import get_storage_state, save_storage_state

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class AuthenticationSkill:

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def login(self, url: str, username: str, password: str) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                storage_state=get_storage_state()
            )
            page = await context.new_page()
            await page.goto(url)

            try:
                username_input = page.locator('input[type="text"], input[name="username"], input[name="email"], input[id*="user"]').first
                password_input = page.locator('input[type="password"]').first
                submit_button = page.locator('button[type="submit"], input[type="submit"]').first

                await username_input.fill(username)
                await password_input.fill(password)
                await submit_button.click()
                await page.wait_for_load_state('networkidle')

                success = 'login' not in page.url.lower()

                if success:
                    save_storage_state(await context.storage_state())

                await browser.close()
                return {
                    'success': success,
                    'message': 'Login realizado com sucesso' if success else 'Falha no login. Verifique as credenciais.'
                }

            except Exception as e:
                await browser.close()
                return {
                    'success': False,
                    'message': f'Erro durante o login: {str(e)}'
                }

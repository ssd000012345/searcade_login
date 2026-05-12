import os
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # 改为有头模式，减少 bot 检测
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            locale='en-US',
            timezone_id='America/New_York',
        )

        page = await context.new_page()
        await stealth_async(page)

        try:
            print("正在访问首页...")
            await page.goto(
                "https://searcade.com/en/",
                wait_until="networkidle",
                timeout=60000
            )
            await asyncio.sleep(2)
            await page.screenshot(path="before_login.png")

            print("点击登录按钮...")
            # 等待 Login 链接出现并点击
            await page.wait_for_selector("text=Login", timeout=15000)
            await page.click("text=Login")

            print("等待跳转到认证页面...")
            # 等待页面跳转到 userveria
            await page.wait_for_load_state("networkidle", timeout=30000)
            await asyncio.sleep(3)

            current_url = page.url
            print(f"当前 URL: {current_url}")
            await page.screenshot(path="after_click_login.png")

            # 打印页面内容用于调试
            content = await page.content()
            print(f"页面标题: {await page.title()}")
            print(f"页面内容片段: {content[:500]}")

            email = os.environ.get("SEARCADE_EMAIL")
            password = os.environ.get("SEARCADE_PASSWORD")

            if not email or not password:
                raise ValueError("未设置 SEARCADE_EMAIL 或 SEARCADE_PASSWORD")

            print("等待邮箱输入框...")
            # 尝试多种选择器
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="Email" i]',
                'input[id*="email" i]',
                '#email',
            ]

            email_input = None
            for selector in email_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    email_input = selector
                    print(f"✅ 找到邮箱输入框: {selector}")
                    break
                except Exception:
                    print(f"❌ 未找到: {selector}")
                    continue

            if not email_input:
                # 输出所有 input 元素的信息
                inputs = await page.query_selector_all('input')
                print(f"页面上共有 {len(inputs)} 个 input 元素:")
                for i, inp in enumerate(inputs):
                    inp_type = await inp.get_attribute('type')
                    inp_name = await inp.get_attribute('name')
                    inp_id = await inp.get_attribute('id')
                    inp_placeholder = await inp.get_attribute('placeholder')
                    print(f"  input[{i}]: type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")
                raise Exception("无法找到邮箱输入框，请查看截图和日志")

            print("填写邮箱...")
            await page.fill(email_input, email)
            await asyncio.sleep(1)

            # 查找并点击"继续"按钮
            continue_selectors = [
                "text=Continue with email",
                "text=Continue",
                "button[type='submit']",
                'button:has-text("Continue")',
            ]

            for selector in continue_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    await page.click(selector)
                    print(f"✅ 点击了继续按钮: {selector}")
                    break
                except Exception:
                    continue

            print("等待密码输入框...")
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(2)
            await page.screenshot(path="after_email.png")

            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password',
            ]

            password_input = None
            for selector in password_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    password_input = selector
                    print(f"✅ 找到密码输入框: {selector}")
                    break
                except Exception:
                    continue

            if not password_input:
                raise Exception("无法找到密码输入框")

            print("填写密码并登录...")
            await page.fill(password_input, password)
            await asyncio.sleep(1)

            login_selectors = [
                "button:has-text('Log in')",
                "button:has-text('Login')",
                "button:has-text('Sign in')",
                "button[type='submit']",
            ]

            for selector in login_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    await page.click(selector)
                    print(f"✅ 点击了登录按钮: {selector}")
                    break
                except Exception:
                    continue

            print("等待跳转到管理后台...")
            await page.wait_for_url("**/admin**", timeout=30000)
            await asyncio.sleep(6)

            await page.screenshot(path="after_login.png")
            print("✅ 登录成功！")

        except Exception as e:
            print(f"❌ 发生错误: {e}")
            try:
                await page.screenshot(path="error_state.png")
            except Exception:
                pass
            import traceback
            traceback.print_exc()
            raise

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

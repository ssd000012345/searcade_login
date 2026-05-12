import os
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async  # 导入 stealth 插件

async def run():
    async with async_playwright() as p:
        # 模拟真实的浏览器启动参数
        browser = await p.chromium.launch(headless=True) 
        
        # 创建 context 时建议伪装一个常见的 User-Agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        page = await context.new_page()

        # 对当前页面应用 stealth 插件
        await stealth_async(page)

        # 1. 访问首页
        print("正在访问首页...")
        await page.goto("https://searcade.com/en/", wait_until="networkidle")
        await page.screenshot(path="before_login.png")

        # 2. 点击登录并处理跳转
        await page.click("text=Login")
        
        # 3. 登录逻辑 (保持不变)
        email = os.environ.get("SEARCADE_EMAIL")
        password = os.environ.get("SEARCADE_PASSWORD")

        # 等待邮箱输入框出现
        await page.wait_for_selector('input[type="email"]')
        await page.fill('input[type="email"]', email)
        await page.click("text=Continue with email")
        
        # 等待密码输入框出现
        await page.wait_for_selector('input[type="password"]')
        await page.fill('input[type="password"]', password)
        await page.click("button:has-text('Log in')")

        # 4. 等待进入后台
        print("正在验证登录状态...")
        try:
            # 增加超时时间以应对网络波动
            await page.wait_for_url("**/admin**", timeout=30000)
            await page.wait_for_load_state("networkidle")
            
            # 登录后的截图
            await asyncio.sleep(5) 
            await page.screenshot(path="after_login.png")
            print("任务完成：登录成功并已截图。")
        except Exception as e:
            print(f"登录可能失败或超时: {e}")
            await page.screenshot(path="error_state.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

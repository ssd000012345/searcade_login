import os
import asyncio
from curl_cffi.requests import AsyncSession
from urllib.parse import urlencode, urlparse, parse_qs
import json

async def run():
    email = os.environ.get("SEARCADE_EMAIL")
    password = os.environ.get("SEARCADE_PASSWORD")

    if not email or not password:
        raise ValueError("未设置 SEARCADE_EMAIL 或 SEARCADE_PASSWORD")

    oauth_params = {
        "client_id": "8305d2e2-e91f-4deb-8909-f669259bc23f",
        "redirect_uri": "https://searcade.com/accounts/userveria/login/callback/",
        "scope": "profile",
        "response_type": "code",
    }

    # 使用 curl_cffi 模拟 Chrome124 TLS 指纹
    async with AsyncSession(impersonate="chrome124") as session:

        print("Step 1: 访问 searcade 首页建立 Cookie...")
        r0 = await session.get("https://searcade.com/en/")
        print(f"  状态码: {r0.status_code}")
        print(f"  Cookies: {dict(session.cookies)}")

        print("\nStep 2: 访问 OAuth 授权页获取 state...")
        authorize_url = f"https://userveria.com/authorize/?{urlencode(oauth_params)}"
        r1 = await session.get(authorize_url)
        print(f"  状态码: {r1.status_code}")
        print(f"  最终 URL: {r1.url}")
        print(f"  响应片段: {r1.text[:300]}")

        # 提取 state
        state = parse_qs(urlparse(str(r1.url)).query).get("state", [None])[0]
        print(f"  State: {state}")

        if r1.status_code == 403:
            print("  ❌ 仍被 Cloudflare 拦截，尝试等待后重试...")
            await asyncio.sleep(5)
            r1 = await session.get(authorize_url)
            print(f"  重试状态码: {r1.status_code}")
            state = parse_qs(urlparse(str(r1.url)).query).get("state", [None])[0]

        print("\nStep 3: 获取 userveria CSRF token...")
        # 访问登录页面获取必要的 token
        login_page_url = f"https://userveria.com/authorize/?{urlencode(oauth_params)}"
        r_page = await session.get(login_page_url)
        print(f"  页面状态码: {r_page.status_code}")

        # 尝试获取 payload.json（Nuxt 应用的数据）
        payload_url = f"https://userveria.com/authorize/_payload.json"
        r_payload = await session.get(payload_url)
        print(f"  Payload 状态码: {r_payload.status_code}")
        if r_payload.status_code == 200:
            print(f"  Payload: {r_payload.text[:500]}")

        print("\nStep 4: 登录 userveria...")
        login_headers = {
            "Content-Type": "application/json",
            "Origin": "https://userveria.com",
            "Referer": authorize_url,
        }

        # 构建登录请求
        login_data = {
            "email": email,
            "password": password,
        }

        # 尝试不同的登录端点
        endpoints = [
            "https://userveria.com/api/auth/login",
            "https://userveria.com/api/auth/email",
            "https://userveria.com/api/login",
            "https://userveria.com/auth/login",
        ]

        login_success = False
        for endpoint in endpoints:
            print(f"\n  尝试端点: {endpoint}")
            r_login = await session.post(
                endpoint,
                json=login_data,
                headers=login_headers,
            )
            print(f"  状态码: {r_login.status_code}")
            print(f"  响应: {r_login.text[:300]}")

            if r_login.status_code in (200, 201):
                login_success = True
                print(f"  ✅ 登录端点找到: {endpoint}")
                break

        print("\nStep 5: 完成 OAuth 授权并回调...")
        if state:
            # 授权
            r_auth = await session.post(
                f"https://userveria.com/api/authorize",
                json={
                    "state": state,
                    **oauth_params,
                },
                headers=login_headers,
            )
            print(f"  授权状态码: {r_auth.status_code}")
            print(f"  授权响应: {r_auth.text[:300]}")

            # 如果返回了 redirect_uri，手动跟随
            try:
                auth_data = r_auth.json()
                if "redirect_uri" in auth_data or "code" in auth_data:
                    code = auth_data.get("code", "")
                    callback_url = f"https://searcade.com/accounts/userveria/login/callback/?code={code}&state={state}"
                    print(f"\n  回调 URL: {callback_url}")
                    r_callback = await session.get(callback_url)
                    print(f"  回调状态码: {r_callback.status_code}")
                    print(f"  回调最终 URL: {r_callback.url}")
            except Exception as e:
                print(f"  解析授权响应失败: {e}")

        print("\nStep 6: 验证登录状态...")
        r_check = await session.get("https://searcade.com/en/admin/")
        print(f"  状态码: {r_check.status_code}")
        print(f"  最终 URL: {r_check.url}")
        print(f"  Cookies: {dict(session.cookies)}")

        # 正确判断是否登录成功
        final_url = str(r_check.url)
        if "/admin" in final_url and r_check.status_code == 200:
            print("\n✅ 登录成功！已进入 Admin 后台")
        elif "login" in final_url or r_check.status_code in (401, 403):
            print("\n❌ 登录失败，被重定向到登录页面")
        elif r_check.status_code == 404:
            print("\n⚠️ Admin 路径 404，尝试其他路径...")
            # 尝试其他 admin 路径
            for admin_path in ["/admin/", "/en/admin/", "/dashboard/", "/en/dashboard/"]:
                r_try = await session.get(f"https://searcade.com{admin_path}")
                print(f"  {admin_path}: {r_try.status_code} -> {r_try.url}")
        else:
            print(f"\n⚠️ 未知状态: {r_check.status_code} at {r_check.url}")

if __name__ == "__main__":
    asyncio.run(run())

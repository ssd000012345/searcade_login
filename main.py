import os
import asyncio
import httpx
from urllib.parse import urlencode, urlparse, parse_qs

async def run():
    email = os.environ.get("SEARCADE_EMAIL")
    password = os.environ.get("SEARCADE_PASSWORD")

    if not email or not password:
        raise ValueError("未设置 SEARCADE_EMAIL 或 SEARCADE_PASSWORD")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://userveria.com",
        "Referer": "https://userveria.com/",
    }

    # OAuth 参数（从 URL 中提取）
    oauth_params = {
        "client_id": "8305d2e2-e91f-4deb-8909-f669259bc23f",
        "redirect_uri": "https://searcade.com/accounts/userveria/login/callback/",
        "scope": "profile",
        "response_type": "code",
    }

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=30.0
    ) as client:

        print("Step 1: 访问 OAuth 授权页面获取 state...")
        authorize_url = f"https://userveria.com/authorize/?{urlencode(oauth_params)}"
        resp = await client.get(authorize_url)
        print(f"  状态码: {resp.status_code}")
        print(f"  最终 URL: {resp.url}")

        # 从 URL 中提取 state
        state = parse_qs(urlparse(str(resp.url)).query).get("state", [None])[0]
        print(f"  State: {state}")

        print("\nStep 2: 调用 userveria 登录 API...")
        login_payload = {
            "email": email,
            "password": password,
        }

        # 尝试 userveria 的登录接口
        login_resp = await client.post(
            "https://userveria.com/api/auth/login",
            json=login_payload,
            headers={
                **headers,
                "Content-Type": "application/json",
                "Referer": authorize_url,
            }
        )
        print(f"  登录状态码: {login_resp.status_code}")
        print(f"  登录响应: {login_resp.text[:500]}")

        if login_resp.status_code not in (200, 201, 302):
            # 尝试其他可能的 API 路径
            for api_path in [
                "/api/auth/signin",
                "/api/login",
                "/api/v1/auth/login",
                "/auth/login",
            ]:
                print(f"\n  尝试路径: {api_path}")
                r = await client.post(
                    f"https://userveria.com{api_path}",
                    json=login_payload,
                    headers={**headers, "Content-Type": "application/json"},
                )
                print(f"  状态码: {r.status_code}, 响应: {r.text[:200]}")
                if r.status_code in (200, 201):
                    login_resp = r
                    break

        print("\nStep 3: 完成 OAuth 授权回调...")
        # 携带 state 完成授权
        if state:
            authorize_payload = {
                "state": state,
                **oauth_params,
            }
            auth_resp = await client.post(
                "https://userveria.com/api/authorize",
                json=authorize_payload,
                headers={**headers, "Content-Type": "application/json"},
            )
            print(f"  授权状态码: {auth_resp.status_code}")
            print(f"  授权响应: {auth_resp.text[:300]}")

        print("\nStep 4: 验证登录状态...")
        check_resp = await client.get("https://searcade.com/en/admin/")
        print(f"  Admin 页面状态码: {check_resp.status_code}")
        print(f"  最终 URL: {check_resp.url}")

        if "/admin" in str(check_resp.url):
            print("✅ 登录成功！已进入 Admin 后台")
        else:
            print(f"⚠️ 当前 URL: {check_resp.url}")
            print("  需要查看日志进一步分析")

if __name__ == "__main__":
    asyncio.run(run())

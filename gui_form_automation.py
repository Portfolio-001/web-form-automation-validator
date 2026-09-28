import streamlit as st
import pandas as pd
import asyncio
import datetime
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ==========================================
# ポートフォリオ2：フォーム自動入力＆検証ダッシュボード (Streamlit版)
# ==========================================

# デモ用データ（実務ではCSV等から読み込む想定）
DEMO_CUSTOMERS = [
    {"id": "1", "name": "山田 太郎", "phone": "090-1234-5678", "email": "yamada@example.com"},
    {"id": "2", "name": "鈴木 花子", "phone": "080-8765-4321", "email": "suzuki@example.com"},
    {"id": "3", "name": "エラー 太郎", "phone": "090-0000-0000", "email": "invalid-email-address"}, # 不正データ
    {"id": "4", "name": "佐藤 次郎", "phone": "070-1111-2222", "email": "sato@example.com"}
]

async def run_form_automation_async(log_container):
    """Playwrightによるフォーム自動入力処理"""
    results = []
    
    async with async_playwright() as playwright:
        # Web公開・サーバー環境に対応するため headless=True
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for idx, row in enumerate(DEMO_CUSTOMERS):
            customer_name = row["name"]
            phone_raw = row["phone"]
            email = row["email"]

            # 1. データクレンジング（電話番号からハイフン等を除去）
            phone_clean = re.sub(r'\D', '', phone_raw)

            # 2. バリデーション（メールアドレス検証）
            if "@" not in email:
                msg = f"⚠️ [ID.{row['id']}] {customer_name}: メール形式不正（{email}）のためスキップしました。"
                log_container.warning(msg)
                results.append({
                    "ID": row["id"],
                    "氏名": customer_name,
                    "変換後電話番号": phone_clean,
                    "メールアドレス": email,
                    "ステータス": "スキップ（バリデーション除外）",
                    "処理日時": datetime.datetime.now().strftime("%H:%M:%S")
                })
                continue

            try:
                log_container.info(f"⏳ [ID.{row['id']}] {customer_name}: フォーム入力中...")
                await page.goto("https://httpbin.org/forms/post", timeout=10000)
                
                # 自動入力
                await page.fill("input[name='custname']", customer_name)
                await page.fill("input[name='custtel']", phone_clean)
                await page.fill("input[name='custemail']", email)
                await page.fill("textarea[name='comments']", "ポートフォリオ用自動入力テストデータ")
                
                # 送信実行
                await page.click("button")
                await asyncio.sleep(1) # 送信完了待機

                log_container.success(f"✅ [ID.{row['id']}] {customer_name}: 送信成功（電話番号整形: {phone_raw} ➔ {phone_clean}）")
                results.append({
                    "ID": row["id"],
                    "氏名": customer_name,
                    "変換後電話番号": phone_clean,
                    "メールアドレス": email,
                    "ステータス": "送信完了",
                    "処理日時": datetime.datetime.now().strftime("%H:%M:%S")
                })

            except PlaywrightTimeoutError:
                log_container.error(f"❌ [ID.{row['id']}] {customer_name}: タイムアウトが発生しました。")
                results.append({
                    "ID": row["id"],
                    "氏名": customer_name,
                    "変換後電話番号": phone_clean,
                    "メールアドレス": email,
                    "ステータス": "失敗（タイムアウト）",
                    "処理日時": datetime.datetime.now().strftime("%H:%M:%S")
                })
            except Exception as e:
                log_container.error(f"❌ [ID.{row['id']}] {customer_name}: エラー発生 ({e})")
                results.append({
                    "ID": row["id"],
                    "氏名": customer_name,
                    "変換後電話番号": phone_clean,
                    "メールアドレス": email,
                    "ステータス": "失敗（エラー）",
                    "処理日時": datetime.datetime.now().strftime("%H:%M:%S")
                })

        await browser.close()
    
    return results

# ==========================================
# 画面レイアウト
# ==========================================
st.set_page_config(page_title="フォーム自動入力＆データ検証ツール", layout="wide")

st.title("📝 フォーム自動入力＆データ検証ツール")
st.markdown("""
**QAエンジニア視点で設計された、誤送信を起こさない入力自動化ダッシュボードです。**  
CSV等の台帳からデータを自動読み込みし、入力形式の自動整形・不正データの除外・Webフォームへの送信までを全自動で行います。
""")

st.info("""
💡 **実務運用のフェイルセーフ仕様について**  
実務納品版では、システム障害やネットワーク切断に備えて**進捗状況（`progress.json`）を1件ごとに自動記録**します。万が一途中で中断した場合でも、再開時に未送信の行から自動的に処理を再開し、**二重送信による重大事故を100%防止**します。  
※本デモ画面では、動作検証用として何度でも繰り返しお試しいただけます。
""")

# 入力前データの確認
st.subheader("1. 処理対象リスト（事前データ検証）")
st.caption("3件目に意図的な不正データ（@抜きのメールアドレス）を仕込んでいます。")
st.dataframe(pd.DataFrame(DEMO_CUSTOMERS), use_container_width=True)

# 実行ボタン
st.subheader("2. 自動実行")
if st.button("🚀 自動入力を実行する", type="primary"):
    log_area = st.container()
    with st.spinner("ブラウザを起動し、順次フォーム入力とバリデーションを実行中..."):
        run_results = asyncio.run(run_form_automation_async(log_area))
    
    st.subheader("3. 処理結果レポート")
    res_df = pd.DataFrame(run_results)
    st.dataframe(res_df, use_container_width=True)
    st.success("全件の処理・検証が完了しました。")
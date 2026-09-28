import asyncio
import traceback
import datetime
import logging
import csv
import json
import os
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ==========================================
# ポートフォリオ：定型フォーム自動入力＆バリデーションツール
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app_form_automation.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

CSV_FILE = "dummy_customers.csv"
PROGRESS_FILE = "progress.json"

def create_dummy_csv():
    """テスト用のダミーCSVが存在しない場合、自動生成する"""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'name', 'phone', 'email'])
            writer.writeheader()
            writer.writerow({'id': '1', 'name': '山田 太郎', 'phone': '090-1234-5678', 'email': 'yamada@example.com'})
            writer.writerow({'id': '2', 'name': '鈴木 花子', 'phone': '080-8765-4321', 'email': 'suzuki@example.com'})
            writer.writerow({'id': '3', 'name': 'エラー 太郎', 'phone': '090-0000-0000', 'email': 'invalid-email-address'}) # バリデーションエラー用
            writer.writerow({'id': '4', 'name': '佐藤 次郎', 'phone': '070-1111-2222', 'email': 'sato@example.com'})
        logging.info("テスト用のダミーCSVファイルを作成しました。")

def load_progress():
    """どこまで処理したか（進捗）を読み込む"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('last_processed_index', 0)
        except Exception:
            return 0
    return 0

def save_progress(index):
    """進捗を保存する（フェイルセーフ用）"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump({'last_processed_index': index}, f)

async def handle_error(page, error, customer_name):
    """エラーハンドリングと証拠保全"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"error_form_{timestamp}.png"
    if page:
        try:
            await page.screenshot(path=screenshot_path, full_page=True)
            logging.info(f"【証拠保全】エラー画面のスクリーンショットを保存しました: {screenshot_path}")
        except Exception as ss_error:
            logging.error(f"スクリーンショットの保存に失敗: {ss_error}")
    logging.error(f"顧客「{customer_name}」の処理中にエラー発生: {error}")

async def run_form_automation(playwright):
    create_dummy_csv()
    start_index = load_progress()

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        customers = list(csv.DictReader(f))

    if start_index >= len(customers):
        logging.info("すべてのデータ処理が完了しています。最初からやり直す場合は progress.json を削除してください。")
        return

    logging.info(f"全{len(customers)}件中、{start_index + 1}件目から処理を開始（再開）します。")

    browser = None
    try:
        # 今回は動きをクライアントに見せる想定で headless=False にしています
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1000, 'height': 800})
        page = await context.new_page()

        for i in range(start_index, len(customers)):
            row = customers[i]
            logging.info(f"--- 処理開始: ID.{row['id']} {row['name']} ---")

            # ==========================================
            # QA目線: データクレンジング（バリデーション）
            # ==========================================
            # 電話番号のハイフンを除去し、数字だけにする
            phone_clean = re.sub(r'\D', '', row['phone']) 
            
            # メールアドレスの形式チェック（簡易的ですが '@' があるか確認）
            if "@" not in row['email']:
                logging.warning(f"【バリデーションエラー】不正なメールアドレスのため処理をスキップします: {row['email']}")
                save_progress(i + 1) # スキップして次の行の進捗を保存
                continue

            try:
                # ダミーの入力フォームサイトへアクセス
                await page.goto("https://httpbin.org/forms/post")
                await asyncio.sleep(1)

                # ==========================================
                # 自動入力処理
                # ==========================================
                logging.info(f"顧客情報を入力中... (変換後電話番号: {phone_clean})")
                await page.fill("input[name='custname']", row['name'])
                await page.fill("input[name='custtel']", phone_clean)
                await page.fill("input[name='custemail']", row['email'])
                await page.fill("textarea[name='comments']", "QAエンジニアによる自動入力とバリデーションのテストです。")

                # 送信ボタンをクリック
                await page.click("button")
                await asyncio.sleep(2) # 結果画面（JSON出力）の確認待機

                logging.info(f"送信完了: {row['name']}")
                
                # 成功したら進捗（インデックス）を上書き保存
                save_progress(i + 1)

            except PlaywrightTimeoutError as e:
                await handle_error(page, e, row['name'])
                logging.error("タイムアウトが発生したため、ツールを安全に中断します。次回起動時は失敗した行から再開されます。")
                break # エラー時はループを抜けてブラウザを閉じる（フェイルセーフ）
            except Exception as e:
                await handle_error(page, e, row['name'])
                logging.error("予期せぬエラーが発生したため中断します。")
                break

    finally:
        if browser:
            await browser.close()
            logging.info("ブラウザを終了しました。")

async def main():
    async with async_playwright() as playwright:
        await run_form_automation(playwright)

if __name__ == '__main__':
    asyncio.run(main())
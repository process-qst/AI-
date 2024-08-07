import os
import requests
from slack_sdk.web import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import signal
import sys
import threading
import json
import subprocess
import glob
import datetime

app_token = "xapp-1-xxx"
bot_token = "xoxb-xxx"

# Chatflow APIの設定
api_url = "http://localhost/v1/chat-messages"
api_key = "app-xxx"  # Chatflow
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# アプリレベルのトークンとWebClientを使用してSocketModeClientを初期化
client = SocketModeClient(
    app_token=app_token,
    web_client=WebClient(token=bot_token)
)


def save_file(file_info):
    """
    Slackから共有されたファイルをダウンロードし、ローカルに保存します。

    Args:
        file_info (dict): Slack APIから取得したファイル情報

    Returns:
        str: 保存されたファイルのパス。ダウンロードに失敗した場合は None を返します。
    """
    file_url = file_info['url_private']
    file_name = file_info['name']
    headers = {'Authorization': f'Bearer {bot_token}'}

    print(f"Attempting to download file: {file_name} from {file_url}")
    response = requests.get(file_url, headers=headers)
    if response.status_code == 200:
        with open(file_name, 'wb') as file:
            file.write(response.content)
        print(f"File saved: {file_name}")
        return file_name
    else:
        print(
            f"Failed to download file: {file_name}, status code: {response.status_code}")
        return None


def process_file(file_path, channel_id, ts):
    """
    ダウンロードしたmp4ファイルを処理し、Chatflow APIに送信します。

    Args:
        file_path (str): 処理対象のmp4ファイルのパス
        channel_id (str): SlackチャンネルID
        ts (str): 更新対象のメッセージのタイムスタンプ

    Returns:
        tuple: Chatflow APIからの応答と文字起こし結果。エラーが発生した場合は (None, None) を返します。
    """
    # wavファイルのパス
    wav_file = "meeting_audio.wav"

    # メッセージリスト
    messages = [f"[{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 要約を開始します。しばらくお待ちください: {file_path}"]  # 最初のメッセージを固定で追加

    # Slackに処理状況を更新: ファイルダウンロード完了
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    messages.append(f"[{timestamp}] File saved: {file_path}")
    client.web_client.chat_update(
        channel=channel_id,
        ts=ts,
        text="\n".join(messages)
    )
    print(messages[-1]) # 追加したメッセージをprint

    # ffmpegを使ってmp4からwavに変換 (-y オプションを追加)
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    messages.append(f"[{timestamp}] ffmpegによる音声変換開始: {file_path} -> {wav_file}")
    client.web_client.chat_update(
        channel=channel_id,
        ts=ts,
        text="\n".join(messages)
    )
    print(messages[-1]) # 追加したメッセージをprint
    command = f"ffmpeg -y -i {file_path} -vn -acodec pcm_s16le -ar 16000 {wav_file}"
    subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # 出力を抑制
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    messages.append(f"[{timestamp}] ffmpegによる音声変換完了")
    client.web_client.chat_update(
        channel=channel_id,
        ts=ts,
        text="\n".join(messages)
    )
    print(messages[-1]) # 追加したメッセージをprint

    # whisperを使ってwavファイルから文字起こし
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    messages.append(f"[{timestamp}] whisperによる文字起こし開始: {wav_file}")
    client.web_client.chat_update(
        channel=channel_id,
        ts=ts,
        text="\n".join(messages)
    )
    print(messages[-1]) # 追加したメッセージをprint
    command = f"whisper {wav_file}"
    result = subprocess.run(command, shell=True,
                            capture_output=True, text=True)
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    messages.append(f"[{timestamp}] whisperによる文字起こし完了")
    client.web_client.chat_update(
        channel=channel_id,
        ts=ts,
        text="\n".join(messages)
    )
    print(messages[-1]) # 追加したメッセージをprint

    # 文字起こし結果を取得
    minutes = result.stdout

    # リクエストボディの設定
    data = {
        "query": minutes,
        "inputs": {
            # 必要に応じて入力パラメータを追加してください
            "param1": "value1",
            "param2": "value2"
        },
        "response_mode": "blocking",  # streaming or blocking
        "user": "abc-123",
        "conversation_id": "",  # 継続する会話がある場合はそのIDを入力
        "files": [
            {
                "type": "image",
                "transfer_method": "remote_url",
                "url": "https://cloud.dify.ai/logo/logo-site.png"
            }
        ]
    }

    # チャットメッセージ送信リクエストを送信
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    messages.append(f"[{timestamp}] Dify APIリクエスト送信: {api_url}")
    client.web_client.chat_update(
        channel=channel_id,
        ts=ts,
        text="\n".join(messages)
    )
    print(messages[-1]) # 追加したメッセージをprint
    response = requests.post(api_url, headers=headers, json=data)
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    messages.append(f"[{timestamp}] Dify APIレスポンス受信: status_code={response.status_code}")
    client.web_client.chat_update(
        channel=channel_id,
        ts=ts,
        text="\n".join(messages)
    )
    print(messages[-1]) # 追加したメッセージをprint

    # レスポンスの表示
    if response.status_code == 200:
        print(f"[{timestamp}] Chat message sent successfully")
        # Slackに処理状況を更新: Chat message sent successfully
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        messages.append(f"[{timestamp}] Chat message sent successfully")
        client.web_client.chat_update(
            channel=channel_id,
            ts=ts,
            text="\n".join(messages)
        )
        print(messages[-1]) # 追加したメッセージをprint
        try:
            response_data = response.json()
            answer = response_data['answer']  # 'answer' フィールドを想定
            return answer, minutes  # answer と minutes を返す

        except requests.exceptions.JSONDecodeError:
            print("Response content is not in JSON format")
            print(response.text)
            return None, None  # エラーの場合は None を返す

    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None, None  # エラーの場合は None を返す


def process(client: SocketModeClient, req: SocketModeRequest):
    """
    Slackからのイベントを処理します。

    Args:
        client (SocketModeClient): Slack Socket Mode Client
        req (SocketModeRequest): Slackからのリクエスト
    """
    print(f"Received request: {req.type}")

    if req.type == "events_api":
        # イベントリクエストを確認（acknowledge）
        response = SocketModeResponse(envelope_id=req.envelope_id)
        client.send_socket_mode_response(response)

        # イベントのペイロードを取得
        event = req.payload.get("event", {})

        # type が file_shared の場合の処理
        if event.get("type") == "file_shared":
            file_id = event.get("file_id", "")
            user_id = event.get("user_id", "")
            channel_id = event.get("channel_id", "")
            print(f"File shared by {user_id} in {channel_id} with file ID {file_id}")

            # ファイル情報を取得
            file_info = client.web_client.files_info(file=file_id)['file']

            # ファイルのダウンロード成功をSlackチャンネルに通知する。
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            response_message = f"[{timestamp}] 要約を開始します。しばらくお待ちください: {file_info['name']}"
            download_success_response = client.web_client.chat_postMessage(
                channel=channel_id, text=response_message
            )

            file_path = save_file(file_info)

            if file_path:
                # process_file に channel_id と ts を渡す
                chatflow_response, minutes = process_file(
                    file_path, channel_id, download_success_response['ts']
                )
                if chatflow_response:
                    # Chatflow APIからの要約文をSlackに投稿 (ダウンロード成功メッセージへの返信として)
                    client.web_client.chat_postMessage(
                        channel=channel_id,
                        text=f"Chatflowからの要約:\n{chatflow_response}",
                        thread_ts=download_success_response['ts']  # ダウンロード成功メッセージのタイムスタンプを指定
                    )

                    # 文字起こし結果をSlackに投稿(ダウンロード成功メッセージへの返信として)
                    client.web_client.chat_postMessage(
                        channel=channel_id,
                        text=f"文字起こし結果:\n{minutes}",
                        thread_ts=download_success_response['ts']  # ダウンロード成功メッセージのタイムスタンプを指定
                    )

            # 不要なファイルを削除
            for file in glob.glob("meeting_audio.*"):
                os.remove(file)
            if file_path:
                os.remove(file_path)
        else:
            print(f"Skipped processing for event type: {event.get('type')}")
    else:
        print(f"Skipped processing for request type: {req.type}")


# 新しいリスナーを追加してSlackからのメッセージを受信
client.socket_mode_request_listeners.append(process)


def signal_handler(sig, frame):
    """
    Ctrl+Cが押されたときにクライアントを切断します。
    """
    print('Ctrl+Cが押されました！')
    client.close()
    print('クライアントが切断されました')
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def start_client():
    """
    Slack Socket Mode Client を起動します。
    """
    client.connect()
    print('クライアントが接続されました')
    # クライアントを実行し続ける
    threading.Event().wait()


# クライアントを別のスレッドで実行
thread = threading.Thread(target=start_client)
thread.start()

# メインスレッドを生かしてシグナルをキャッチする
while thread.is_alive():
    thread.join(timeout=1)
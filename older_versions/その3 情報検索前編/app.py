# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
	ApiClient, Configuration, MessagingApi,
	ReplyMessageRequest, PushMessageRequest,
	TextMessage, PostbackAction
)
from linebot.v3.webhooks import (
	FollowEvent, MessageEvent, PostbackEvent, TextMessageContent
)
import os, random, re
import pandas as pd

## .env ファイル読み込み
from dotenv import load_dotenv
load_dotenv()

## 環境変数を変数に割り当て
CHANNEL_ACCESS_TOKEN = os.environ["CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["CHANNEL_SECRET"]

## データ読み込み
DATA = pd.read_csv('data/beatles.csv', index_col='song') ## 曲名をプライマリキーに設定
SONGS = DATA.index  ## 曲名のリスト

## 使用関数もろもろ
def levenshtein(str1, str2):
	str1 = '^' + str1
	str2 = '^' + str2
	distances = [list(range(len(str2)))]
	for i in range(1, len(str1)):
		row = [i]
		for j in range(1, len(str2)):
			insert = row[j-1] + 1
			delete = distances[i-1][j] + 1
			replace = distances[i-1][j-1] + int(str1[i]!=str2[j])
			row.append(min(insert, delete, replace))
		distances.append(row)
	return distances[-1][-1]

## function to tokenize text
def tokenize(text:str) -> set:
	rough_tokens = re.split(r'[\s;:,\-\(\)\"!?]', text.lower())
	tokens = set()
	for token in rough_tokens:
		if token == '':
			continue
		if token.endswith("\'s"):
			tokens.add(token.replace("\'s", ''))  ## day's - > day
		if "\'" in token:
			tokens.add(token.replace("\'", ''))  ## don't -> dont
		tokens.add(token)
	return tokens

## function to remove whitespaces/punctuations
## e.g. A Hard Day's Night -> aharddaysnight
def remove_punct(text:str) -> str:
	return ''.join(c for c in text if c.isalnum()).lower()

INVERTED_INDEX_SONGTITLE = {}
for song in SONGS:
    for token in tokenize(song):
        INVERTED_INDEX_SONGTITLE[token] = INVERTED_INDEX_SONGTITLE.get(token, set()) | {song}
        
def search_song_title(query:str) -> str:
	query_lower = re.sub(r'\s\s+', ' ', query).strip().lower()  ## shrink space & lowercase 
	query_no_punct = remove_punct(query_lower)  ## a hard day's -> aharddays
	query_tokens = query_lower.split(' ')

	partial_match = []

	for song in SONGS:
		song_lower = song.lower()  ## lowercase song title
		song_no_punct = remove_punct(song)  ## remove punct 

		### 1. EXACT MATCH ###
		if query_lower==song_lower or query_no_punct==song_no_punct:
			return song
		
		### 2. PARTIAL MATCH ###
		if query_lower in song_lower or query_no_punct in song_no_punct:
			partial_match.append(song)

		### 3. TOKEN MATCH ###
		song_intersection = set(SONGS)
		for token in query_tokens:
			song_intersection &= INVERTED_INDEX_SONGTITLE.get(token, set())

	if len(partial_match) == 1:
		return partial_match[0]
	elif len(song_intersection) > 0:
		return random.sample(list(song_intersection), 1)[0]
	elif len(partial_match) > 0:
		return random.sample(partial_match, 1)[0]
	return None


## Flask アプリのインスタンス化
app = Flask(__name__)

## LINE のアクセストークン読み込み
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

## コールバックのおまじない
@app.route("/callback", methods=['POST'])
def callback():
	# get X-Line-Signature header value
	signature = request.headers['X-Line-Signature']

	# get request body as text
	body = request.get_data(as_text=True)
	app.logger.info("Request body: " + body)

	# handle webhook body
	try:
		handler.handle(body, signature)
	except InvalidSignatureError:
		app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
		abort(400)

	return 'OK'

## 友達追加時のメッセージ送信
@handler.add(FollowEvent)
def handle_follow(event):
	## APIインスタンス化
	with ApiClient(configuration) as api_client:
		line_bot_api = MessagingApi(api_client)

	## 返信
	line_bot_api.reply_message(ReplyMessageRequest(
		replyToken=event.reply_token,
		messages=[TextMessage(text='Thank You!')]
	))

## 返信メッセージ
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
	## APIインスタンス化
	with ApiClient(configuration) as api_client:
		line_bot_api = MessagingApi(api_client)

	## 受信メッセージの中身を取得
	received_message = event.message.text

	## 曲名取得
	songtitle = search_song_title(received_message)

	## 返信
	if songtitle != None:
		reply = 'https://www.youtube.com/watch?v=' + DATA.loc[songtitle, 'official_youtube']
	else:
		reply = 'NOT FOUND'
	line_bot_api.reply_message(ReplyMessageRequest(
		replyToken=event.reply_token,
		messages=[TextMessage(text=reply)]
	))

## 起動確認用ウェブサイトのトップページ
@app.route('/', methods=['GET'])
def toppage():
	return 'Hello world!'

## ボット起動時のコード
if __name__ == "__main__":
	## ローカルでテストする時のために、`debug=True` にしておく
	app.run(host="0.0.0.0", port=8000, debug=True)
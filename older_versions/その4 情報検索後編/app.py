# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
	ApiClient, Configuration, MessagingApi,
	ReplyMessageRequest, PushMessageRequest,
	TextMessage, QuickReply, QuickReplyItem, MessageAction
)
from linebot.v3.webhooks import (
	FollowEvent, MessageEvent, PostbackEvent, TextMessageContent
)
import os, random, re
import pandas as pd
from collections import Counter

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
        
def search_song_title(query:str, min_partial_len=4, distance_threshold=0.5):
	query_lower = re.sub(r'\s\s+', ' ', query).strip().lower()  ## shrink space & lowercase 
	query_no_punct = remove_punct(query_lower)  ## a hard day's -> aharddays
	query_tokens = query_lower.split(' ')

	partial_match_songs = []
	min_distance = 1000
	min_distance_songs = []

	for song in SONGS:
		song_lower = song.lower()  ## lowercase song title
		song_no_punct = remove_punct(song)  ## remove punct 

		### EXACT MATCH ###
		if query_lower==song_lower or query_no_punct==song_no_punct:
			return [song]
		
		### PARTIAL MATCH - 4 chars or more ###
		if (query_lower in song_lower and len(query_lower) >= min_partial_len) or\
			(query_no_punct in song_no_punct and len(query_no_punct) >= min_partial_len):
			partial_match_songs.append(song)

		### LEVENSHTEIN DISTANCE ###
		if len(query_no_punct) < len(song_no_punct):  ##  
			window_len = len(query_no_punct)  
			distance = min(levenshtein(query_no_punct, song_no_punct[i:i+window_len])
				for i in range(0, len(song_no_punct)-window_len+1))
		else:	
			distance = levenshtein(query_no_punct, song_no_punct)

		if distance < min_distance and distance / len(query_no_punct) < distance_threshold:
			min_distance = distance
			min_distance_songs = [song]
		elif distance == min_distance and distance / len(query_no_punct) < distance_threshold:
			min_distance_songs.append(song)

	### NUM OF MATCHED TOKEN ###
	token_counter = Counter()
	for token in query_tokens:
		if token in INVERTED_INDEX_SONGTITLE:
			token_counter.update(INVERTED_INDEX_SONGTITLE[token])
			
	if len(token_counter) == 0:
		max_token_count, token_match_songs = 0, []
	else:
		max_token_count = token_counter.most_common()[0][1]
		token_match_songs = [song for song, count in token_counter.most_common() if count==max_token_count]
	
	## 部分一致が1曲のみの時
	if len(partial_match_songs) == 1:
		return partial_match_songs
	## 単語一致した曲がある時
	elif max_token_count >= 1:
		return token_match_songs
	## 単語一致がなく、部分一致が2曲以上の時
	elif len(partial_match_songs) >= 2:
		return partial_match_songs
	## それ以外の時は最小レーベンシュタイン距離
	else:
		return min_distance_songs

##################################################

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

	## 曲名リスト取得
	songtitle = search_song_title(received_message)

	## 返信
	if len(songtitle) == 0:  ## 候補なし
		reply = 'NOT FOUND:\nPlease try again with a different words.'
		reply = [TextMessage(text=reply)]
	elif len(songtitle) == 1:  ## 候補1曲のみ
		reply = 'https://www.youtube.com/watch?v=' + DATA.loc[songtitle[0], 'official_youtube']
		reply = [TextMessage(text=reply)]
	else:
		quickreply = QuickReply(items=[])  ## クイックリプライインスタンス化
		for song in songtitle:
			if len(song) > 20:  ## ラベル文字最大数
				item = QuickReplyItem(action=MessageAction(label=song[:19]+'…', text=song))
			else:
				item = QuickReplyItem(action=MessageAction(label=song, text=song))
			quickreply.items.append(item)
		reply = [TextMessage(text='candidate songs:', quickReply=quickreply)]

	line_bot_api.reply_message(ReplyMessageRequest(
		replyToken=event.reply_token,
		messages=reply
	))

## 起動確認用ウェブサイトのトップページ
@app.route('/', methods=['GET'])
def toppage():
	return 'Hello world!'

## ボット起動時のコード
if __name__ == "__main__":
	## ローカルでテストする時のために、`debug=True` にしておく
	app.run(host="0.0.0.0", port=8000, debug=True)
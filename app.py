# -*- coding: utf-8 -*-
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
	ApiClient, Configuration, MessagingApi,
	ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import (
	FollowEvent, MessageEvent, PostbackEvent, TextMessageContent
)
import os, re

## load `.env` file
## if test bot, use `load_dotenv('test.env')` instead 
from dotenv import load_dotenv
load_dotenv()

## environment variables
CHANNEL_ACCESS_TOKEN = os.environ["CHANNEL_ACCESS_TOKEN"]
CHANNEL_SECRET = os.environ["CHANNEL_SECRET"]

## Flask instantiation
app = Flask(__name__)

## LINE instantiation
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

## callback function (copied from official GitHub)
@app.route("/callback", methods=['POST'])
def callback():
	signature = request.headers['X-Line-Signature']
	body = request.get_data(as_text=True)
	app.logger.info("Request body: " + body)
	try:
		handler.handle(body, signature)
	except InvalidSignatureError:
		app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
		abort(400)
	return 'OK'

##################################################

## When someone follows the bot
@handler.add(FollowEvent)
def handle_follow(event):
	## API instantiation
	with ApiClient(configuration) as api_client:
		line_bot_api = MessagingApi(api_client)
	## send reply message
	line_bot_api.reply_message(ReplyMessageRequest(
		replyToken=event.reply_token,
		messages=[TextMessage(text='Thank You!')]
	))

## When received TEXT MESSAGE
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
	with ApiClient(configuration) as api_client:
		line_bot_api = MessagingApi(api_client)
	## get the text content
	received_message = event.message.text.strip() ## remove spaces

	## send reply message
	print(event)
	line_bot_api.reply_message(ReplyMessageRequest(
		replyToken=event.reply_token,
		messages=[TextMessage(text='Thank You!'),TextMessage(text='Thank You2!')]
	))

## When received POSTBACK EVENT - lyrics quiz
@handler.add(PostbackEvent)
def handle_postback(event):
	with ApiClient(configuration) as api_client:
		line_bot_api = MessagingApi(api_client)
	
	## get the postback data
	postback_data = event.postback.data

	# get replay message - Postback or Message
	messages=[TextMessage(text='Thank You!'),TextMessage(text='Thank You2!')]

	## send reply message
	line_bot_api.reply_message(ReplyMessageRequest(
		replyToken=event.reply_token,
		messages=messages
	))

##################################################

## toppage of website - Hello world!
@app.route('/', methods=['GET'])
def toppage():
	return 'Hello world!'

if __name__ == "__main__":
	app.run(host="0.0.0.0", port=8000, debug=True)
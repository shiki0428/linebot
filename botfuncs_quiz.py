
from utils import *
import random

from linebot.v3.messaging import (
	TextMessage, QuickReply, QuickReplyItem,
	PostbackAction
)

def create_lyrics_quiz():
	selected_song = DATA.drop(index=['Flying', 'Revolution 9'])['lyrics'].sample(4)
	answer_title = selected_song.index[0]
	wrong_titles = selected_song.index[1:]
	selected_song_tokens = selected_song[0].split()
	token_length = random.randint(5, 9)
	start_token_index = random.randint(0, len(selected_song_tokens)-token_length)
	partial_lyrics = ' '.join(selected_song_tokens[start_token_index:start_token_index+token_length])
	
	return partial_lyrics.lower(), answer_title, wrong_titles

def create_postback_reply(postback):
	postback_dict = parse_postback(postback)
	postback_dict['question'] += 1

	reply_message = []

	if postback_dict['answer'] != 'NONE':
		reply_message.append(f'Answer : {postback_dict["answer"]}')

	if postback_dict['question'] <= 5:
		partial_lyrics, answer_title, wrong_titles = create_lyrics_quiz()
		reply_message.append(f'QUESTION {postback_dict["question"]} :\n' + partial_lyrics)
		postback_dict['answer'] = answer_title
		quickreply_buttons = []
		## add wrong answer
		for title in wrong_titles:
			label = get_label(title)
			item = QuickReplyItem(action=PostbackAction(label=label, displayText=title, data=encode_postback(postback_dict)))
			quickreply_buttons.append(item)

		## add correct answer
		postback_dict['score'] += 1
		label = get_label(answer_title)
		item = QuickReplyItem(action=PostbackAction(label=label, displayText=answer_title, data=encode_postback(postback_dict)))
		quickreply_buttons.append(item)

		## shuffle items
		quickreply = QuickReply(items=random.sample(quickreply_buttons, 4))
		return [TextMessage(text='\n\n'.join(reply_message), quickReply=quickreply)]
	else:
		reply_message.append(f'SCORE : {postback_dict["score"]} / 5')
		if postback_dict['score'] == 5:
			reply_message.append('PERFECT!!')
		return [TextMessage(text='\n\n'.join(reply_message))]
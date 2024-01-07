# -*- coding: utf-8 -*-
import re
import pandas as pd
from collections import Counter

from linebot.v3.messaging import (
	TextMessage, FlexMessage, QuickReply, QuickReplyItem, MessageAction,
	FlexBubble, FlexBox, FlexText
)

from utils import levenshtein, tokenize, remove_punct

## LOAD DATA
DATA = pd.read_csv('data/beatles.csv', index_col='song') ## set song title as index 
DATA['lyrics'] = DATA['lyrics'].apply(lambda x: x.replace('<br>', '\n'))
SONGS = DATA.index  ## list of song title
ALBUM_YEAR = pd.read_csv('data/album_year.csv', index_col='album')['year'] ## pd.Series

## CLASS FOR GET INFORMATION BY SONG TITLE
class _GetBySongTitle:
	def __init__(self, col_name, mode_prefix='', decorate=lambda x: x):
		self.data = DATA[col_name] ## pd.Series : index - song title
		self.prefix = mode_prefix
		self.decorate = decorate  ## function to add sth to reply message

	def get(self, query:str) -> list:
		songtitles = search_song_title(query)
		if len(songtitles) == 0:  ## no candidate
			reply = 'NOT FOUND:\nPlease try again with different words.'
			messages = [TextMessage(text=reply)]
		elif len(songtitles) == 1:  ## only one candidate -> return URL
			songtitle = songtitles[0]
			reterieved = self.data[songtitle]  ## retrieve data 
			reply = self.decorate(reterieved, songtitle)
			if type(reply) == str:
				messages = [TextMessage(text=reply)]
			else:
				messages = [FlexMessage(altText=songtitle, contents=reply)]
		else:
			quickreply = QuickReply(items=[])  ## instantiation 
			for song in songtitles:
				if len(song) > 20:  ## max characters : 20
					label = song[:19] + '…'
				else:
					label = song
				item = QuickReplyItem(action=MessageAction(label=label, text=self.prefix+song))
				quickreply.items.append(item)
			messages = [TextMessage(text='candidate songs:', quickReply=quickreply)]
		return messages

_GetYoutube = _GetBySongTitle(
	col_name='official_youtube',
	mode_prefix='',
	decorate=lambda youtubeID, songtitle: 'https://www.youtube.com/watch?v=' + youtubeID)  ## add YouTube URL
get_official_youtube = _GetYoutube.get

_GetLyrics = _GetBySongTitle(
	col_name='lyrics',
	mode_prefix='lyrics ',
	decorate=lambda lyrics, songtitle: create_flex_lyrics(lyrics, songtitle))
get_lyrics = _GetLyrics.get

def create_flex_lyrics(lyrics, songtitle):
	## GET SONG INFO
	album = DATA.loc[songtitle, 'album']
	year = ALBUM_YEAR[album]
	if year >= 1967:
		color = '#0367D3' ## blue
	else:
		color = '#CB444A' ## red

	## PREPARE BUBBLE CONTAINER
	bubble_container = FlexBubble(size='giga')

	## ADD HEADER WITH SONG TITLE, ALBUM, YEAR
	song_title_text = FlexText(text=songtitle, color='#FFFFFF', size='xl', weight='bold')
	song_album_text = FlexText(text=f'{album} ({year})', color='#FFFFFF66', size='lg') 
	header_box = FlexBox(
		layout='vertical',
		contents=[song_title_text, song_album_text],
		spacing='sm',
		backgroundColor=color,
		paddingAll='xxl'
	)
	bubble_container.header = header_box

	## ADD EMPTY BOX TO BODY
	bubble_container.body = FlexBox(
		layout='vertical',
		spacing='xxl', ## space between each paragraph 
		contents=[]
	)

	## INSERT EACH LINE TO PARAGRAPH BOX
	## paragraphs = list of list of lines e.g [[Jojo was..., But he...], [Get Back, ...]]
	paragraphs = [paragraph.split('\n') for paragraph in lyrics.split('\n\n')]
	for paragraph in paragraphs:
		para_box = FlexBox(layout="vertical", contents=[], spacing='sm')
		for line in paragraph:
			para_box.contents.append(FlexText(text=line, size='lg', wrap=True))
		bubble_container.body.contents.append(para_box)

	return bubble_container

##################################################

## CREATE INVERTED INDEX FOR SONG TITLE
## { token : {set of songs that contain the word} }
INVERTED_INDEX_songtitles= {'64': {"When I'm Sixty-Four"}}
for song in SONGS:
	for token in tokenize(song):
		INVERTED_INDEX_songtitles	[token] = INVERTED_INDEX_songtitles	.get(token, set()) | {song}

## FUNCTION TO FIND THE MOST SIMILAR SONG TITLE
def search_song_title(query:str, min_partial_len=4, distance_threshold=0.5) -> list:
	"""
	find song title from input text
	ambiguous matching ranked by
		1. exact match
		2. partial match (if only one song)
		3. token match - refer INVERTED_INDEX_songtitles	
		4. Levenshtein Distance

	output is LIST regardless of the number of matched songs (0 or more)
	"""
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
		if token in INVERTED_INDEX_songtitles	:
			token_counter.update(INVERTED_INDEX_songtitles	[token])
			
	if len(token_counter) == 0:
		max_token_count, token_match_songs = 0, []
	else:
		max_token_count = token_counter.most_common()[0][1]
		token_match_songs = [song for song, count in token_counter.most_common() if count==max_token_count]
	
	## only one partial match
	if len(partial_match_songs) == 1:
		return partial_match_songs
	## if token match exists
	elif max_token_count >= 1:
		return token_match_songs
	## no token match AND multiple partial match
	elif len(partial_match_songs) >= 2:
		return partial_match_songs
	## else, minimum Levenshtein distance
	else:
		return min_distance_songs
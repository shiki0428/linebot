import re

## function to get Levenshtein distance between 2 strings
def levenshtein(str1, str2) -> int:
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

## function to tokenize English text
## full stop . is excluded as word boundary (due to song title)
def tokenize(text:str) -> set:
	## rough_token includes empty string ''
	rough_tokens = re.split(r'[\s;:,\-\(\)\"!?]', text.lower())
	tokens = set()  ## Bag of Words (i.e. order is ignored) 
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
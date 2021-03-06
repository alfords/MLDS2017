import config
import json
import numpy as np
import os
import pickle
import re
from collections import defaultdict

class ReadUtil:

	MARKER_PAD = '<pad>'
	MARKER_BOS = '<s>'
	MARKER_EOS = '</s>'
	marker_list = [MARKER_PAD, MARKER_BOS, MARKER_EOS]

	train_caption_list = None
	train_feat_list = None
	test_feat_list = None
	test_id_list = None
	test_limited_feat_list = None
	val_caption_list = None
	val_caption_str_list = None
	val_feat_list = None
	word_freq_dict = None
	word_list = None
	word_index_dict = None
	word_vec_dict = None
	
	def __init__(self):
		print 'Initializing ReadUtil...'
		self.__readTrain()
		self.__readTest()
		self.__readTestLimited()
		self.__readVal()
		self.__genWordList()
		self.__genWordVecDict()

	def __readTrain(self):
		if not os.path.isfile(config.train_label_path):
			return

		## Read train label
		with open(config.train_label_path, 'r') as file:
			content = file.read()
		train_label = json.loads(content)

		## Generate caption list
		self.train_caption_list = []
		for video in train_label:
			caption_list = video['caption']
			self.train_caption_list.append([])
			for caption in caption_list:
				if not all(ord(c) < 128 for c in caption):
					continue
				token_list = self.captionToTokenList(caption)
				self.train_caption_list[-1].append(token_list)

		## Generate feature list
		self.train_feat_list = []
		for video in train_label:
			video_id = video['id']
			feat = np.load(config.train_feat_folder_path + video_id + '.npy')
			self.train_feat_list.append(feat)

	def __readTest(self):
		if not os.path.isfile(config.test_id_path):
			return

		## Read test id
		with open(config.test_id_path, 'r') as file:
			content = file.read()
		self.test_id_list = test_id_list = content.split()

		## Generate feature list
		self.test_feat_list = []
		for video_id in test_id_list:
			feat = np.load(config.test_feat_folder_path + video_id + '.npy')
			self.test_feat_list.append(feat)
	
	def __readTestLimited(self):
		if not os.path.isfile(config.test_limited_id_path):
			return

		## Read test id
		with open(config.test_limited_id_path, 'r') as file:
			content = file.read()
		test_limited_id_list = content.split()

		## Generate feature list
		self.test_limited_feat_list = []
		for video_id in test_limited_id_list:
			feat = np.load(config.test_limited_feat_folder_path + video_id + '.npy')
			self.test_limited_feat_list.append(feat)
	
	def __readVal(self):
		if not os.path.isfile(config.test_public_label_path):
			return

		## Read val label
		with open(config.test_public_label_path, 'r') as file:
			content = file.read()
		val_label = json.loads(content)

		## Generate caption list
		self.val_caption_list = []
		self.val_caption_str_list = []
		for video in val_label:
			caption_list = video['caption']
			self.val_caption_list.append([])
			self.val_caption_str_list.append([])
			for caption in caption_list:
				if not all(ord(c) < 128 for c in caption):
					continue
				token_list = self.captionToTokenList(caption)
				self.val_caption_list[-1].append(token_list)
				self.val_caption_str_list[-1].append(caption)

		## Generate feature list
		self.val_feat_list = []
		for video in val_label:
			video_id = video['id']
			feat = np.load(config.test_public_feat_folder_path + video_id + '.npy')
			self.val_feat_list.append(feat)

	@staticmethod
	def captionToTokenList(caption):
		# Remove trailing punctuations, e.g. '.'
		caption = re.sub('\W+$', '', caption)
		
		# Convert to lowercase
		caption = caption.lower()

		# "blabla" -> blabla
		caption = re.sub('"(?P<bla>([a-zA-Z]+))"', lambda m: m.group('bla'), caption)

		# Isolate comma
		caption = re.sub('(?P<letter>\w),', lambda m: m.group('letter') + ' , ', caption)

		# Isolate 's
		caption = re.sub("(?P<letter>\w)'s", lambda m: m.group('letter') + " 's ", caption)

		# Tokenize
		token_list = re.split('\s+', caption)

		# Add EOS
		token_list.append(ReadUtil.MARKER_EOS)

		return token_list

	@staticmethod
	def tokenListToCaption(token_list):
		# Trim words after EOS
		if ReadUtil.MARKER_EOS in token_list:
			token_list = token_list[:token_list.index(ReadUtil.MARKER_EOS)]
		if token_list == []:
			return ''

		# Convert back to sentence
		caption = reduce(lambda s, term: s + ' ' + term, token_list[1:], token_list[0])
		
		# Captalize the first letter
		caption = caption[0:1].upper() + caption[1:]

		# Remove space before comma
		caption = re.sub(' , ', ', ', caption)

		# Remove space before 's
		caption = re.sub(" 's ", "'s ", caption)

		return caption

	def __genWordList(self):
		self.word_freq_dict = defaultdict(int)
		total_word_count = 0.0
		for video in self.train_caption_list:
			for caption in video:
				for token in caption:
					self.word_freq_dict[token] += 1
					total_word_count += 1.0
		for word in self.word_freq_dict:
			self.word_freq_dict[word] /= total_word_count

		word_freq_list = sorted(self.word_freq_dict.iteritems(), key=lambda (k, v): v, reverse=True)
		self.word_list = self.marker_list + [k for (k, v) in word_freq_list]
		self.word_index_dict = dict([(self.word_list[i], i) for i in range(len(self.word_list))])

	def __genWordVecDict(self):
		if not os.path.isfile(config.word_vec_path):
			return

		self.word_vec_dict = dict()
		with open(config.word_vec_path, 'r') as file:
			for line in file:
				content = line.split()
				vec = [float(elem) for elem in content[1:]]
				self.word_vec_dict[content[0]] = np.array(vec, dtype=np.float32)
		for marker in self.marker_list:
			self.word_vec_dict[marker] = np.zeros([300], dtype=np.float32)

if __name__ == '__main__':
	util = ReadUtil()


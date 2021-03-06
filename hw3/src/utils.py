import config
import numpy as np
import os
import re
import scipy.misc
import skimage.exposure
import pickle

class Utils:

	TRAIN_IMAGE_SHAPE = [64, 64, 3]
	COLOR_UNSPECIFIED = '<un>'
	COLOR_EXCLUSION_LIST = ['long', 'short', 'pubic', 'damage', 'bicolored']
	COLOR_ALIAS = {'blonde': 'yellow'}

	color_list = None
	train_image_list = None
	train_hair_color_list = None
	train_eyes_color_list = None
	color_index_dict = None
	test_list = None

	def __init__(self, test_mode=False):
		print 'Initializing...'
		self.__readTags()
		if not test_mode:
			self.__readImages()
			assert len(self.train_image_list) == len(self.train_hair_color_list)
		else:
			self.color_list = ['<un>', 'yellow', 'pink', 'purple', 'aqua', 'black', 'blue', 'red', 'green', 'orange', 'white', 'gray', 'brown']
			self.color_index_dict = dict([(self.color_list[i], i) for i in range(len(self.color_list))])
			for key in self.COLOR_ALIAS:
				self.color_index_dict[key] = self.color_index_dict[self.COLOR_ALIAS[key]]
		self.__readTest()

	def __readImages(self):
		if os.path.isfile(config.IMAGES_CACHED_PATH):
			file = open(config.IMAGES_CACHED_PATH, 'r')
			self.train_image_list = pickle.load(file)
			return

		if not os.path.isdir(config.IMAGES_PATH):
			os.system('tar xf data/faces.tar.gz -C data/') 

		self.train_image_list = []
		i = 0
		def image_path(i):
			return '{}{}.jpg'.format(config.IMAGES_PATH, str(i))
		while os.path.isfile(image_path(i)):
			#img = skimage.io.imread(image_path(i))
			img = scipy.misc.imread(image_path(i))
			img = skimage.exposure.equalize_adapthist(img)
			if img.shape != self.TRAIN_IMAGE_SHAPE:
				img = scipy.misc.imresize(img, self.TRAIN_IMAGE_SHAPE, interp='bicubic')
			self.train_image_list.append(img)
			i += 1

		file = open(config.IMAGES_CACHED_PATH, 'w')
		pickle.dump(self.train_image_list, file)

	def __readTags(self):
		self.color_list = [self.COLOR_UNSPECIFIED]
		self.train_hair_color_list = []
		self.train_eyes_color_list = []

		with open(config.TAGS_PATH, 'r') as file:
			for i, row in enumerate(file):
				row = row.replace('\n', '')
				conflict = False
				hair_color = self.COLOR_UNSPECIFIED
				eyes_color = self.COLOR_UNSPECIFIED

				tag_list = row.split(',')[1]
				for tag_pair in tag_list.split('\t'):
					tag = tag_pair.split(':')[0]
					if re.match('[a-z]+ hair', tag):
						color = tag.split(' ')[0]
						if color in self.COLOR_EXCLUSION_LIST:
							continue
						if color in self.COLOR_ALIAS:
							color = self.COLOR_ALIAS[color]
						if hair_color != self.COLOR_UNSPECIFIED:
							conflict = True
						hair_color = color
						if hair_color not in self.color_list:
							self.color_list.append(hair_color)
					if re.match('[a-z]+ eyes', tag):
						color = tag.split(' ')[0]
						if color in self.COLOR_EXCLUSION_LIST:
							continue
						if color in self.COLOR_ALIAS:
							color = self.COLOR_ALIAS[color]
						if eyes_color != self.COLOR_UNSPECIFIED:
							conflict = True
						eyes_color = color
						if eyes_color not in self.color_list:
							self.color_list.append(eyes_color)

				if conflict:
					self.train_hair_color_list.append(self.COLOR_UNSPECIFIED)
					self.train_eyes_color_list.append(self.COLOR_UNSPECIFIED)
				else:
					self.train_hair_color_list.append(hair_color)
					self.train_eyes_color_list.append(eyes_color)

		self.color_index_dict = dict([(self.color_list[i], i) for i in range(len(self.color_list))])
		for key in self.COLOR_ALIAS:
			self.color_index_dict[key] = self.color_index_dict[self.COLOR_ALIAS[key]]
		print 'Color List: {}'.format(self.color_list)

	def __readTest(self):
		self.test_list = dict()
		
		with open(config.TESTING_PATH, 'r') as file:
			for line in file:
				line = line.replace('\n', '')
				testing_text_id = line.split(',')[0]
				assert re.match('[a-z]+ hair [a-z]+ eyes', line.split(',')[1])
				hair_color = line.split(',')[1].split(' ')[0]
				if hair_color in self.COLOR_ALIAS:
					hair_color = self.COLOR_ALIAS[hair_color]
				if hair_color not in self.color_list:
					hair_color = self.COLOR_UNSPECIFIED
				eyes_color = line.split(',')[1].split(' ')[2]
				if eyes_color not in self.color_list:
					eyes_color = self.COLOR_UNSPECIFIED
				if eyes_color in self.COLOR_ALIAS:
					eyes_color = self.COLOR_ALIAS[eyes_color]
				self.test_list[testing_text_id] = {'hair': hair_color, 'eyes': eyes_color}

	@staticmethod
	def saveImage(testing_text_id, sample_id, tensor):
		if tensor.shape != (64, 64, 3):
			tensor = scipy.misc.imresize(tensor, [64, 64, 3], interp='bicubic')
		#skimage.io.imsave('{}/sample_{}_{}.jpg'.format(config.OUTPUT_PATH, testing_text_id, sample_id), tensor)
		scipy.misc.imsave('{}/sample_{}_{}.jpg'.format(config.OUTPUT_PATH, testing_text_id, sample_id), tensor)

	@staticmethod
	def saveImageTile(testing_text_id, sample_id, tensors):
		newTensor = np.zeros([tensors.shape[0], 64, 64, 3])
		for i, tensor in enumerate(tensors):
			if tensor.shape != (64, 64, 3):
				tensor = scipy.misc.imresize(tensor, [64, 64, 3], interp='bicubic')
			newTensor[i] = tensor

		tiled = np.hstack(newTensor)

		#skimage.io.imsave('{}/sample_{}_{}.jpg'.format(config.OUTPUT_PATH, testing_text_id, sample_id), tensor)
		scipy.misc.imsave('{}/sample_{}_{}.jpg'.format(config.OUTPUT_PATH, testing_text_id, sample_id), tiled)

if __name__ == '__main__':
	utils = Utils()
	utils.saveImage(1, 0, utils.train_image_list[0])

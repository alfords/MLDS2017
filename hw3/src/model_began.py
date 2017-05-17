import numpy as np
import os
import sys
import random
import tensorflow as tf
import time
import utils
import gc

class ModelBEGAN:
	
	## Config
	batch_size = 16
	filter_dim = 128
	latent_dim = 64
	gamma = 0.5
	lambda_k = 0.001
	lr_init = 0.00005
	lr_decay_steps = 10000
	lr_decay_rate = 0.5
	num_sample = 5
	real_image_threshold = 1.5

	model_name = 'began'
	save_dir = 'data/model_' + model_name
	save_path = save_dir + '/model.ckpt'

	## Constants
	data = None
	num_color = None

	## Placeholder tensors
	real_image = None
	hair_color = None
	eyes_color = None
	training = None

	## Variable
	loss_real_image_threshold = None
	lr = None

	## Output tensors
	update_k = None
	convergence_measure = None
	train_step = None
	gen_image_uint8 = None
	loss_gen_image_batch = None

	def __init__(self):
		if not os.path.exists(self.save_dir):
			os.makedirs(self.save_dir)

		self.__fillConstants()
		self.__defineModel()

	def __fillConstants(self):
		self.data = utils.Utils()
		self.num_color = len(self.data.color_list)

	def __defineModel(self):
		print 'Defining model...'

		## Global step
		global_step = tf.get_variable('global_step', shape=[], dtype=tf.int32, initializer=tf.constant_initializer(0), trainable=False)

		## Real image loss threshold
		self.loss_real_image_threshold = loss_real_image_threshold = tf.get_variable('loss_real_image_threshold', shape=[], dtype=tf.float32, initializer=tf.constant_initializer(1.0), trainable=False)

		## Input placeholders
		self.training = training = tf.placeholder(tf.bool, shape=[], name='training')
		self.real_image = real_image = tf.placeholder(tf.uint8, shape=[self.batch_size]+self.data.TRAIN_IMAGE_SHAPE, name='real_image')
		real_image = tf.image.convert_image_dtype(real_image, tf.float32, saturate=True)
		self.hair_color = hair_color = tf.placeholder(tf.int32, shape=[self.batch_size], name='hair_color')
		self.eyes_color = eyes_color = tf.placeholder(tf.int32, shape=[self.batch_size], name='eyes_color')
		
		## Generator
		z = tf.random_uniform([self.batch_size, self.latent_dim], minval=-1.0, maxval=1.0, dtype=tf.float32, name='z')
		z_for_d = tf.random_uniform([self.batch_size, self.latent_dim], minval=-1.0, maxval=1.0, dtype=tf.float32, name='z_for_d')
		gen_image = self.__defineGenerator(z)
		gen_image_for_d = self.__defineGenerator(z_for_d, reuse_scope=True)
		self.gen_image_uint8 = gen_image_uint8 = tf.image.convert_image_dtype(gen_image, tf.uint8, saturate=True, name='gen_image_uint8')
		
		## Discriminator
		restored_real_image = self.__defineDiscriminator(real_image)
		restored_gen_image = self.__defineDiscriminator(gen_image, reuse_scope=True)
		restored_gen_image_for_d = self.__defineDiscriminator(gen_image_for_d, reuse_scope=True)
		
		## Define reconstruction loss
		def reconLoss(img, restored_img, scope, reserve_batch=False):
			with tf.variable_scope(scope):
				recon_loss = tf.abs(img - restored_img)
				#recon_loss = recon_loss * tf.norm(tf.constant(
				#	[4.0 * 0.299 - 0.169 + 0.5, 4.0 * 0.587 - 0.331 - 0.419, 4.0 * 0.114 + 0.5- 0.081]))
				recon_loss = recon_loss * tf.constant([0.299, 0.587, 0.114])
				if reserve_batch:
					recon_loss = tf.reshape(recon_loss, [self.batch_size, -1])
					recon_loss = tf.reduce_mean(recon_loss, axis=1, name='recon_loss')
				else:
					recon_loss = tf.reduce_mean(recon_loss, name='recon_loss')
			return recon_loss
		
		## Loss
		self.k = k = tf.get_variable('k', shape=[], dtype=tf.float32, initializer=tf.constant_initializer(0.0), trainable=False)

		#self.loss_real_image = loss_real_image = reconLoss(real_image, restored_real_image, 'real_image')
		loss_real_image_batch = reconLoss(real_image, restored_real_image, 'real_image_batch', reserve_batch=True)
		qualified_mask = tf.less(loss_real_image_batch, loss_real_image_threshold)
		self.loss_real_image_batch = loss_real_image_batch = tf.boolean_mask(loss_real_image_batch, qualified_mask)
		self.loss_real_image = loss_real_image = tf.reduce_mean(loss_real_image_batch, name='loss_real_image')

		self.loss_gen_image = loss_gen_image = reconLoss(gen_image, restored_gen_image, 'gen_image')
		self.loss_gen_image_batch = reconLoss(gen_image, restored_gen_image, 'gen_image_batch', reserve_batch=True)
		loss_gen_image_for_d = reconLoss(gen_image_for_d, restored_gen_image_for_d, 'gen_image_for_d')
		loss_generator = loss_gen_image
		loss_discriminator = loss_real_image - k * loss_gen_image_for_d
		
		self.update_k = update_k = tf.assign_add(k, self.lambda_k * (self.gamma * loss_real_image - loss_gen_image), name='update_k')
		self.convergence_measure = convergence_measure = tf.add(loss_real_image, tf.abs(self.gamma * loss_real_image - loss_gen_image), name='convergence_measure')
		
		## Optimization
		#lr = tf.train.exponential_decay(self.lr_init, global_step, self.lr_decay_steps, self.lr_decay_rate)
		self.lr = lr = tf.get_variable('lr', shape=[], dtype=tf.float32, initializer=tf.constant_initializer(self.lr_init))
		optimizer = tf.train.AdamOptimizer(lr, beta1=0.5, beta2=0.999)
		#optimizer = tf.train.GradientDescentOptimizer(lr)
		grad_loss_generator = optimizer.compute_gradients(loss_generator, var_list=tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'generator/'))
		grad_loss_discriminator = optimizer.compute_gradients(loss_discriminator, var_list=tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, 'discriminator/'))
		self.train_step = train_step = optimizer.apply_gradients(grad_loss_generator + grad_loss_discriminator, global_step=global_step, name='train_step')
		
		## Print trainable variables
		print 'Variables:'
		for i in tf.global_variables():
			print i.name, i.get_shape()

	def __defineGenerator(self, z, reuse_scope=False):
		with tf.variable_scope('generator') as scope:
			if reuse_scope:
				scope.reuse_variables()

			def doConv(input, filters):
				output = tf.layers.conv2d(input, filters, [3, 3], kernel_initializer=tf.contrib.layers.xavier_initializer(), padding='SAME')
				#output = tf.layers.batch_normalization(output, training=self.training)
				output = tf.nn.elu(output, name='output')
				return output

			def doUpscaling(input, size):
				output = tf.image.resize_bilinear(input, size, name='output')
				#output = tf.image.resize_nearest_neighbor(input, size, name='output')
				return output

			with tf.variable_scope('layer1'):
				w = tf.get_variable('w', shape=[self.latent_dim, 8 * 8 * self.filter_dim], dtype=tf.float32, initializer=tf.contrib.layers.xavier_initializer())
				b = tf.get_variable('b', shape=[8 * 8 * self.filter_dim], dtype=tf.float32, initializer=tf.constant_initializer(0.0))
				layer1 = tf.reshape(tf.add(tf.matmul(z, w), b), [self.batch_size, 8, 8, self.filter_dim], name='output')

			with tf.variable_scope('conv1_1'):
				conv1_1 = doConv(layer1, self.filter_dim)

			with tf.variable_scope('conv1_2'):
				conv1_2 = doConv(conv1_1, self.filter_dim)

			with tf.variable_scope('layer2'):
				layer2 = doUpscaling(conv1_2, [16, 16])

			with tf.variable_scope('conv2_1'):
				conv2_1 = doConv(layer2, self.filter_dim)

			with tf.variable_scope('conv2_2'):
				conv2_2 = doConv(conv2_1, self.filter_dim)

			with tf.variable_scope('layer3'):
				layer3 = doUpscaling(conv2_2, [32, 32])

			with tf.variable_scope('conv3_1'):
				conv3_1 = doConv(layer3, self.filter_dim)

			with tf.variable_scope('conv3_2'):
				conv3_2 = doConv(conv3_1, self.filter_dim)

			with tf.variable_scope('layer4'):
				layer4 = doUpscaling(conv3_2, [64, 64])

			with tf.variable_scope('conv4_1'):
				conv4_1 = doConv(layer4, self.filter_dim)

			with tf.variable_scope('conv4_2'):
				conv4_2 = doConv(conv4_1, self.filter_dim)

			with tf.variable_scope('output'):
				output = tf.layers.conv2d(conv4_2, 3, [3, 3], kernel_initializer=tf.contrib.layers.xavier_initializer(), bias_initializer=tf.constant_initializer(0.5), padding='SAME')
				#output = 1.0 / (1.0 + tf.exp(-4.0 * output))
				#output = tf.nn.sigmoid(output, name='output')

		return output
				
	def __defineDiscriminator(self, image, reuse_scope=False):
		
		with tf.variable_scope('discriminator') as scope:
			if reuse_scope:
				scope.reuse_variables()

			def doConv(input, filters):
				output = tf.layers.conv2d(input, filters, [3, 3], kernel_initializer=tf.contrib.layers.xavier_initializer(), padding='SAME')
				#output = tf.layers.batch_normalization(output, training=self.training)
				output = tf.nn.elu(output, name='output')
				return output

			def doUpscaling(input, size):
				#output = tf.image.resize_nearest_neighbor(input, size, name='output')
				output = tf.image.resize_bilinear(input, size, name='output')
				return output

			def doDownscaling(input, size):
				#output = tf.layers.average_pooling2d(input, [2, 2], [2, 2], name='output')
				#assert size == output.shape.as_list()[1:3]
				output = tf.image.resize_bilinear(input, size, name='output')
				return output
			
			with tf.variable_scope('encoder'):
				with tf.variable_scope('conv1_1'):
					conv1_1 = doConv(image, self.filter_dim)

				with tf.variable_scope('conv1_2'):
					conv1_2 = doConv(conv1_1, self.filter_dim)

				with tf.variable_scope('layer2'):
					layer2 = doDownscaling(conv1_2, [32, 32])

				with tf.variable_scope('conv2_1'):
					conv2_1 = doConv(layer2, self.filter_dim * 2)

				with tf.variable_scope('conv2_2'):
					conv2_2 = doConv(conv2_1, self.filter_dim * 2)

				with tf.variable_scope('layer3'):
					layer3 = doDownscaling(conv2_2, [16, 16])

				with tf.variable_scope('conv3_1'):
					conv3_1 = doConv(layer3, self.filter_dim * 3)

				with tf.variable_scope('conv3_2'):
					conv3_2 = doConv(conv3_1, self.filter_dim * 3)

				with tf.variable_scope('layer4'):
					layer4 = doDownscaling(conv3_2, [8, 8])

				with tf.variable_scope('conv4_1'):
					conv4_1 = doConv(layer4, self.filter_dim * 4)

				with tf.variable_scope('conv4_2'):
					conv4_2 = doConv(conv4_1, self.filter_dim * 4)

				with tf.variable_scope('z'):
					conv4_2 = tf.reshape(conv4_2, [self.batch_size, 8 * 8 * self.filter_dim * 4])
					w = tf.get_variable('w', shape=[8 * 8 * self.filter_dim * 4, self.latent_dim], dtype=tf.float32, initializer=tf.contrib.layers.xavier_initializer())
					b = tf.get_variable('b', shape=[self.latent_dim], dtype=tf.float32, initializer=tf.constant_initializer(0.0))
					z = tf.add(tf.matmul(conv4_2, w), b, name='z')

			with tf.variable_scope('decoder'):
				with tf.variable_scope('layer1'):
					w = tf.get_variable('w', shape=[self.latent_dim, 8 * 8 * self.filter_dim], dtype=tf.float32, initializer=tf.contrib.layers.xavier_initializer())
					b = tf.get_variable('b', shape=[8 * 8 * self.filter_dim], dtype=tf.float32, initializer=tf.constant_initializer(0.0))
					dec_layer1 = tf.reshape(tf.add(tf.matmul(z, w), b), [self.batch_size, 8, 8, self.filter_dim], name='output')

				with tf.variable_scope('conv1_1'):
					dec_conv1_1 = doConv(dec_layer1, self.filter_dim)

				with tf.variable_scope('conv1_2'):
					dec_conv1_2 = doConv(dec_conv1_1, self.filter_dim)

				with tf.variable_scope('layer2'):
					dec_layer2 = doUpscaling(dec_conv1_2, [16, 16])

				with tf.variable_scope('conv2_1'):
					dec_conv2_1 = doConv(dec_layer2, self.filter_dim)

				with tf.variable_scope('conv2_2'):
					dec_conv2_2 = doConv(dec_conv2_1, self.filter_dim)

				with tf.variable_scope('layer3'):
					dec_layer3 = doUpscaling(dec_conv2_2, [32, 32])

				with tf.variable_scope('conv3_1'):
					dec_conv3_1 = doConv(dec_layer3, self.filter_dim)

				with tf.variable_scope('conv3_2'):
					dec_conv3_2 = doConv(dec_conv3_1, self.filter_dim)

				with tf.variable_scope('layer4'):
					dec_layer4 = doUpscaling(dec_conv3_2, [64, 64])

				with tf.variable_scope('conv4_1'):
					dec_conv4_1 = doConv(dec_layer4, self.filter_dim)

				with tf.variable_scope('conv4_2'):
					dec_conv4_2 = doConv(dec_conv4_1, self.filter_dim)

				with tf.variable_scope('output'):
					output = tf.layers.conv2d(dec_conv4_2, 3, [3, 3], kernel_initializer=tf.contrib.layers.xavier_initializer(), bias_initializer=tf.constant_initializer(0.5), padding='SAME')
					#output = 1.0 / (1.0 + tf.exp(-4.0 * output))
					#output = tf.nn.sigmoid(output, name='output')
			
		return output

	def __prepareTrainPairList(self):
		train_pair_list = []
		for idx in range(len(self.data.train_image_list)):
			train_pair_list.append((self.data.train_image_list[idx], self.data.train_hair_color_list[idx], self.data.train_eyes_color_list[idx]))
		random.shuffle(train_pair_list)

		return train_pair_list

	def __prepareTrainFeedDictList(self, pair_list, index):
		real_image_data = np.zeros(shape=[self.batch_size]+self.data.TRAIN_IMAGE_SHAPE, dtype=np.uint8)
		hair_color_data = np.zeros(shape=(self.batch_size), dtype=np.int32)
		eyes_color_data = np.zeros(shape=(self.batch_size), dtype=np.int32)

		for i in range(self.batch_size):
			# If the index is out of range, shift the cursor back to the beginning
			while index + i >= len(pair_list):
				index -= len(pair_list)
			real_image_data[i] = pair_list[index + i][0]
			hair_color_data[i] = self.data.color_index_dict[pair_list[index + i][1]]
			eyes_color_data[i] = self.data.color_index_dict[pair_list[index + i][2]]
				

		feed_dict = {
			self.training: True,
			self.real_image: real_image_data,
			self.hair_color: hair_color_data,
			self.eyes_color: eyes_color_data
			}

		return feed_dict

	def __prepareTestFeedDictList(self, testing_id):
		hair_color_data = np.zeros(shape=(self.batch_size), dtype=np.int32)
		eyes_color_data = np.zeros(shape=(self.batch_size), dtype=np.int32)

		for i in range(self.batch_size):
			hair_color_data[i] = self.data.color_index_dict[self.data.test_list[testing_id]['hair']]
			eyes_color_data[i] = self.data.color_index_dict[self.data.test_list[testing_id]['eyes']]

		feed_dict = {
			self.training: False,
			self.hair_color: hair_color_data,
			self.eyes_color: eyes_color_data
			}

		return feed_dict

	def __testFast(self, sess):
		feed_dict = {
			self.training: False,
			self.hair_color: np.zeros(shape=(self.batch_size), dtype=np.int32),
			self.eyes_color: np.zeros(shape=(self.batch_size), dtype=np.int32)
			}
		for i in range(self.num_sample):
			gen_image, loss = sess.run([self.gen_image_uint8, self.loss_gen_image_batch], feed_dict=feed_dict)
			index = np.argmin(loss)
			self.data.saveImage('training', str(i), gen_image[index])

	def train(self, savepoint=None):
		print 'Start training...'

		gc.disable()
		with tf.device('/cpu:0'):
			saver = tf.train.Saver()

		config = tf.ConfigProto()
		config.gpu_options.allow_growth = True
		with tf.Session(config=config) as sess:
			init = tf.global_variables_initializer()
			sess.run(init)
			if savepoint != None:
				saver.restore(sess, savepoint)

			global_convergence_measure_history = []
			last_convergence_measure = 1.0
			lr = self.lr_init
			for epoch in range(0, 1000, 1):
				print '[Epoch #{}]'.format(str(epoch))

				train_pair_list = self.__prepareTrainPairList()
				
				convergence_measure_history = []
				loss_real_image_history = np.array([], dtype=np.float32)
				percent = 1
				for step in range(0, len(train_pair_list), self.batch_size):
					feed_dict = self.__prepareTrainFeedDictList(train_pair_list, step)
					#_, _, convergence_measure, loss_real_image = sess.run([self.train_step, self.update_k, self.convergence_measure, self.loss_real_image_batch], feed_dict=feed_dict)
					_, _, convergence_measure, loss_real_image, k, loss_real, loss_gen = sess.run([self.train_step, self.update_k, self.convergence_measure, self.loss_real_image_batch, self.k, self.loss_real_image, self.loss_gen_image], feed_dict=feed_dict)
					print 'step: {}, k: {}, real loss: {}, gen loss: {}'.format(step, k, loss_real, loss_gen)
					convergence_measure_history.append(convergence_measure)
					loss_real_image_history = np.concatenate((loss_real_image_history, loss_real_image))
					
					if step > percent * len(train_pair_list) / 100:
						print 'Progress: {}%, Convergence measure: {}'.format(percent, np.mean(convergence_measure_history))
						global_convergence_measure_history += convergence_measure_history
						convergence_measure_history = []
						self.__testFast(sess)
						
						percent += 1

				## Update threshold
				loss_real_image_threshold = np.mean(loss_real_image_history) + self.real_image_threshold * np.std(loss_real_image_history)
				update_threshold = tf.assign(self.loss_real_image_threshold, tf.constant(loss_real_image_threshold, dtype=tf.float32))
				sess.run([update_threshold])
				print 'Real Image Threshold: {}'.format(loss_real_image_threshold)

				## Update LR
				new_convergence_measure = np.mean(global_convergence_measure_history)
				print 'Avg Convergence Measure: {}'.format(new_convergence_measure)
				if new_convergence_measure > last_convergence_measure:
					lr = lr * self.lr_decay_rate
					update_lr = tf.assign(self.lr, tf.constant(lr, dtype=tf.float32))
					sess.run([update_lr])
					print 'LR change to: {}'.format(lr)
				last_convergence_measure = new_convergence_measure
				global_convergence_measure_history = []

				saver.save(sess, self.save_path)
			
		
if __name__ == '__main__':
	model = ModelBEGAN()
	#model.train('data/model_began/model.ckpt')
	model.train()
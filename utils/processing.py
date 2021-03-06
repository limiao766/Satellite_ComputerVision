# -*- coding: utf-8 -*-
"""
Created on Fri Mar 20 10:50:44 2020

@author: MEvans
"""
import tensorflow as tf

def aug_color(img):
    n_ch = tf.shape(img)[-1]
    contra_adj = 0.05
    bright_adj = 0.05

    ch_mean = tf.math.reduce_mean(img, axis = (0,1), keepdims = True)
    #ch_mean = np.mean(img, axis=(0, 1), keepdims=True).astype(np.float32)

    contra_mul = tf.random.uniform(shape = (1, 1, n_ch),
                                   minval = 1-contra_adj,
                                   maxval = 1+contra_adj)
    # contra_mul = np.random.uniform(1 - contra_adj, 1 + contra_adj, (1, 1, n_ch)).astype(
    #     np.float32
    # )

    bright_mul = tf.random.uniform(shape = (1, 1, n_ch),
                                   minval = 1 - bright_adj,
                                   maxval = 1+bright_adj)
    # bright_mul = np.random.uniform(1 - bright_adj, 1 + bright_adj, (1, 1, n_ch)).astype(
    #     np.float32
    # )

    recolored = (img - ch_mean) * contra_mul + ch_mean * bright_mul
    return recolored

def augColor(x):
    """Color augmentation

    Args:
        x: Image

    Returns:
        Augmented image
    """
    x = tf.image.random_hue(x, 0.08)
    x = tf.image.random_saturation(x, 0.6, 1.6)
    x = tf.image.random_brightness(x, 0.05)
    x = tf.image.random_contrast(x, 0.7, 1.3)
    return x
  
def augImg(img):
    """
    Perform image augmentation on tfRecords
    Parameters:
        img (TFRecord): 4D tensor
    Returns:
        3D tensor: 
    """
    outDims = tf.shape(img)[0:1]
    x = tf.image.random_flip_left_right(img)
    x = tf.image.random_flip_up_down(x)
    x = tf.image.rot90(x, tf.random.uniform(shape=[], minval=0, maxval=4, dtype=tf.int32))
      #x = zoom(x, outDims)
      #since were gonna map_fn this on a 4d image, output must be 3d, so squeeze the artificial 'sample' dimension
    return tf.squeeze(x)

def normalize(x, axes=[0, 1, 2], epsilon=1e-8):
  """
  Standardize incoming image patches by mean and variance
  
  To standardize each pixel use axes = [2]
  To standardize each channel use axes = [0, 1]
  To standardize globally use axes = [0, 1, 2]
    
  Parameters:
    x (tensor): nD image tensor
    axes (array): Array of ints. Axes along which to compute mean and variance, usually length n-1
    epsilon (float): small number to avoid dividing by zero
  Return:
    tensor: nD image tensor normalized by channels
  """
  mean, variance = tf.nn.moments(x, axes=axes)
  x_normed = (x - mean) / tf.sqrt(variance + epsilon) # epsilon to avoid dividing by zero
  return x_normed

def rescale(img, axes = [2]):
    """
    Standardize incoming image patch to [0,1] based on min and max values
    
    To standardize each pixel use axes = [2]
    To standardize each channel use axes = [0, 1]
    To standardize globally use axes = [0, 1, 2]
    
    Args:
        img (tensor): 3D (H,W,C) image tensor
        axes (list): axes along which to calculate min/max for rescaling
    Return:
        tensor: 3D tensor of same shape as input, with values [0,1]
    """
    minimum = tf.math.reduce_min(img, axis = axes, keepdims = True)
    maximum = tf.math.reduce_max(img, axis = axes, keepdims = True)
    scaled = tf.divide(tf.subtract(img, minimum), tf.subtract(maximum, minimum))
    return scaled

#def parse_tfrecord(example_proto, ftDict):
#    """The parsing function.
#    Read a serialized example into the structure defined by FEATURES_DICT.
#    Args:
#      example_proto: a serialized Example.
#    Returns: 
#      A dictionary of tensors, keyed by feature name.
#    """
#    return tf.io.parse_single_example(example_proto, ftDict)


def to_tuple(inputs, features, response):
    """Function to convert a dictionary of tensors to a tuple of (inputs, outputs).
    Turn the tensors returned by parse_tfrecord into a stack in HWC shape.
    Args:
      inputs (dict): A dictionary of tensors, keyed by feature name. Response
      variable must be the last item.
      features (list): List of input feature names
      respones (str): response name(s)
    Returns: 
      A dtuple of (inputs, outputs).
    """
    inputsList = [inputs.get(key) for key in features + [response]]
    stacked = tf.stack(inputsList, axis=0)
    # Convert from CHW to HWC
    stacked = tf.transpose(stacked, [1, 2, 0])
    stacked = augImg(stacked)
    #split input bands and labels
    bands = stacked[:,:,:len(features)]
    labels = stacked[:,:,len(features):]
    # in case labels are >1
    labels = tf.where(tf.greater(labels, 1.0), 1.0, labels)
    # perform color augmentation on input features
    bands = aug_color(bands)
    # standardize each patch of bands
    bands = normalize(bands, [0,1])
    # return the features and labels
    return bands, labels

def get_dataset(files, ftDict):
  """Function to read, parse and format to tuple a set of input tfrecord files.
  Get all the files matching the pattern, parse and convert to tuple.
  Args:
    files (list): A list of filenames storing tfrecords
    FtDict (dic): Dictionary of input features in tfrecords
  Returns: 
    A tf.data.Dataset
  """
  keys = list(ftDict.keys())
  features = keys[:-1]
  response = keys[-1]
  
  def parse_tfrecord(example_proto):
      return tf.io.parse_single_example(example_proto, ftDict)
  
  def tupelize(inputs):
      return to_tuple(inputs, features, response)
  
  dataset = tf.data.TFRecordDataset(files, compression_type='GZIP')
  dataset = dataset.map(parse_tfrecord, num_parallel_calls=5)
  dataset = dataset.map(tupelize, num_parallel_calls=5)
  return dataset

def get_training_dataset(files, ftDict, buff, batch):
	"""
    Get the preprocessed training dataset
    Args:
        files (list): list of tfrecord files to be used for training
        buffer (int): buffer size for shuffle
        batch (int): batch size for training
    Returns: 
      A tf.data.Dataset of training data.
    """
	dataset = get_dataset(files, ftDict)
	dataset = dataset.shuffle(buff).batch(batch).repeat()
	return dataset

def get_eval_dataset(files, ftDict):
	"""
    Get the preprocessed evaluation dataset
    Args:
        files (list): list of tfrecords to be used for evaluation
    Returns: 
      A tf.data.Dataset of evaluation data.
    """
	dataset = get_dataset(files, ftDict)
	dataset = dataset.batch(1)
	return dataset
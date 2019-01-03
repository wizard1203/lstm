from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import torch
from torch.utils import data as data_
from torch.utils.data import Dataset
import torch.utils.data.distributed
import torchvision.datasets as datasets
import torchvision.models as models
# from data import util
import collections
import os
import numpy as np
import tensorflow as tf

def _read_words(filename):
  with open(filename, "r") as f:
  #with tf.gfile.GFile(filename, "r") as f:
    return f.read().replace("\n", "<eos>").split()


def _build_vocab(filename):
  data = _read_words(filename)

  counter = collections.Counter(data)
  count_pairs = sorted(counter.items(), key=lambda x: (-x[1], x[0]))

  words, _ = list(zip(*count_pairs))
  word_to_id = dict(zip(words, range(len(words))))
  id_to_word = dict((v, k) for k, v in word_to_id.items())

  return word_to_id, id_to_word


def _file_to_word_ids(filename, word_to_id):
  data = _read_words(filename)
  return [word_to_id[word] for word in data if word in word_to_id]


def ptb_raw_data(data_path=None, prefix="ptb"):
  """Load PTB raw data from data directory "data_path".
  Reads PTB text files, converts strings to integer ids,
  and performs mini-batching of the inputs.
  The PTB dataset comes from Tomas Mikolov's webpage:
  http://www.fit.vutbr.cz/~imikolov/rnnlm/simple-examples.tgz
  Args:
    data_path: string path to the directory where simple-examples.tgz has
      been extracted.
  Returns:
    tuple (train_data, valid_data, test_data, vocabulary)
    where each of the data objects can be passed to PTBIterator.
  """

  train_path = os.path.join(data_path, prefix + ".train.txt")
  valid_path = os.path.join(data_path, prefix + ".valid.txt")
  test_path = os.path.join(data_path, prefix + ".test.txt")

  word_to_id, id_2_word = _build_vocab(train_path)
  train_data = _file_to_word_ids(train_path, word_to_id)
  valid_data = _file_to_word_ids(valid_path, word_to_id)
  test_data = _file_to_word_ids(test_path, word_to_id)
  return train_data, valid_data, test_data, word_to_id, id_2_word


def ptb_iterator(raw_data, batch_size, num_steps, idx):
  """Iterate on the raw PTB data.
  This generates batch_size pointers into the raw PTB data, and allows
  minibatch iteration along these pointers.
  Args:
    raw_data: one of the raw data outputs from ptb_raw_data.
    batch_size: int, the batch size.
    num_steps: int, the number of unrolls.
  Yields:
    Pairs of the batched data, each a matrix of shape [batch_size, num_steps].
    The second element of the tuple is the same data time-shifted to the
    right by one.
  Raises:
    ValueError: if batch_size or num_steps are too high.
  """
  print(raw_data)
  raw_data = np.array(raw_data, dtype=np.int32)

  data_len = len(raw_data)
  batch_len = data_len // batch_size
  data = np.zeros([batch_size, batch_len], dtype=np.int32)
  for i in range(batch_size):
    data[i] = raw_data[batch_len * i:batch_len * (i + 1)]


  epoch_size = (batch_len - 1) // num_steps

  if epoch_size == 0:
    raise ValueError("epoch_size == 0, decrease batch_size or num_steps")
  
  # for i in range(epoch_size):
  #   #   x = data[:, i*num_steps:(i+1)*num_steps]
  #   #   y = data[:, i*num_steps+1:(i+1)*num_steps+1]
  #   #   yield (x, y)
  
  x = data[:, idx*num_steps:(idx+1)*num_steps]
  y = data[:, idx*num_steps+1:(idx+1)*num_steps+1]
  return (x, y)




class TrainDataset(Dataset):
    def __init__(self, raw_data, batch_size, num_steps, split='train'):
        """Iterate on the raw PTB data.
        This generates batch_size pointers into the raw PTB data, and allows
        minibatch iteration along these pointers.
        Args:
          raw_data: one of the raw data outputs from ptb_raw_data.
          batch_size: int, the batch size.
          num_steps: int, the number of unrolls.
        Yields:
          Pairs of the batched data, each a matrix of shape [batch_size, num_steps].
          The second element of the tuple is the same data time-shifted to the
          right by one.
        Raises:
          ValueError: if batch_size or num_steps are too high.
        """
        #print(raw_data)
        self.raw_data = np.array(raw_data, dtype=np.int64)
        #print(self.raw_data.shape)
        #print(self.raw_data.ndim)
        #print(self.raw_data.size)
        self.batch_size = batch_size
        self.num_steps = num_steps
        self.data_len = len(self.raw_data)
        self.batch_len = self.data_len // batch_size
        # self.data = np.zeros([batch_size, self.batch_len], dtype=np.int64)
        # for i in range(batch_size):
        #     self.data[i] = self.raw_data[self.batch_len * i:self.batch_len * (i + 1)]
        self.loadid = 0
        self.epoch_size = (self.batch_len - 1) // num_steps
    
        if self.epoch_size == 0:
            raise ValueError("epoch_size == 0, decrease batch_size or num_steps")
    
    def __getitem__(self, idx):
        # x = self.data[:, idx * self.num_steps:(idx + 1) * self.num_steps]
        # y = self.data[:, idx * self.num_steps + 1:(idx + 1) * self.num_steps + 1]
        
        batchindex = self.batch_size * idx
        #print("idx:%d , batch_len:%d, data_len:%d == ", idx, self.batch_len, self.data_len)
        #print("batchindex  :  %d== ",batchindex)
        num_steps_begin_index = self.num_steps * self.loadid
        #print("num_steps_begin_index  :  %d== ",num_steps_begin_index)
        num_steps_end_index = self.num_steps * (self.loadid + 1)
        #print("num_steps_end_index  :  %d== ",num_steps_end_index)
        x = self.raw_data[batchindex + num_steps_begin_index : batchindex + num_steps_end_index]
        y = self.raw_data[batchindex + num_steps_begin_index + 1: batchindex + num_steps_end_index + 1]
        #print(x)
        #print(type(x))
        self.loadid += 1
        if self.loadid == self.epoch_size - 1 :
            self.loadid = 0
        
        return (x, y)
    
    def __len__(self):
        return self.batch_len




class TestDataset(Dataset):
    def __init__(self, config, split='test'):
        self.config = config
        self.db = WaterDataset(config.data_dir, split=split)
        self.tsf = Transform(config.norm_mean, config.norm_std)
    
    def __getitem__(self, idx):
        label, datas = self.db.get_example(idx)
        label = t.from_numpy(np.array(label))
        datas = np.array(datas)
        # datas = self.tsf(datas)
        datas = t.from_numpy(datas)
        datas = datas.contiguous().view(1, 96, 16)
        # TODO: check whose stride is negative to fix this instead copy all
        
        return label, datas
    
    def __len__(self):
        return len(self.db)
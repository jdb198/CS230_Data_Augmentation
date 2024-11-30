# -*- coding: utf-8 -*-
"""Conditional_GAN_Run_On_EEG.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1QDRzNrEPaAMTH5pa8G91NPgWPlrpG6U6

Vanilla GAN from this website

https://github.com/Yangyangii/GAN-Tutorial/blob/master/MNIST/VanillaGAN.ipynb

https://github.com/Yangyangii/GAN-Tutorial/blob/master/MNIST/Conditional-GAN.ipynb


Combine into a DCGAN - 1D

https://github.com/LixiangHan/GANs-for-1D-Signal/blob/main/dcgan.py
"""

#!pip install torch torchvision

import torch
import torchvision
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision import transforms
from torchvision.utils import save_image
import matplotlib.pyplot as plt

import numpy as np
import datetime
import os, sys

import scipy.io
import tensorflow as tf
import os

from numpy import savetxt
import pandas as pd

# Commented out IPython magic to ensure Python compatibility.
from matplotlib.pyplot import imshow, imsave
# %matplotlib inline

import matplotlib.pyplot as plt
import time

start_time = time.time()

batch_size = 512
condition_size = 2
learning_rate = 0.00001

criterion = nn.BCELoss()

max_epoch = 300 # need more than 10 epochs for training generator
step = 0
n_critic = 2 # for training more k steps about Discriminator
num_created=3240


"""# All Samples"""

# Commented out IPython magic to ensure Python compatibility.
# %cd /content/drive/MyDrive/CS230/GAN/EEG_2B_Data/
data =  np.empty((1000, 3, 3240)) # empty np array that concatenates all of the trials
label = [] #np.empty((3240,1))
list_of_files = ['B0901T.mat', 'B0902T.mat', 'B0903T.mat', 'B0801T.mat', 'B0802T.mat', 'B0803T.mat','B0701T.mat', 'B0702T.mat', 'B0703T.mat',
                 'B0601T.mat', 'B0602T.mat', 'B0603T.mat', 'B0501T.mat', 'B0502T.mat', 'B0503T.mat', 'B0401T.mat', 'B0402T.mat', 'B0403T.mat',
                 'B0301T.mat', 'B0302T.mat', 'B0303T.mat', 'B0201T.mat', 'B0202T.mat', 'B0203T.mat', 'B0101T.mat', 'B0102T.mat', 'B0103T.mat']

for idx in range(len(list_of_files)):
  target_tmp = scipy.io.loadmat(list_of_files[idx])
  data_tmp = target_tmp['data']
  label_tmp = target_tmp['label']
  data[:,:, idx*120:(idx+1)*120] = data_tmp
  for i in range(len(label_tmp)):
    if label_tmp[i] == 1.0:
      label.append(0)
    else:
      label.append(1)


data = np.transpose(data, (2, 1, 0))  # (trials, channels, ms of data )
labels = np.array(label).reshape(3240, 1)

"""# Just one Sample"""

# normalize the data to be between [0, 1]
mins = []
maxes = []

for i in range(data.shape[0]):
  for j in range(data.shape[1]):
    mins.append(np.min(data[i, j, :]))
    maxes.append(np.max(data[i, j, :]))
max_data = np.average(maxes)
min_data = np.average(mins)
for i in range(data.shape[0]):
  for j in range(data.shape[1]):
    data[i, j, :] = (data[i, j, :] - min_data) / (max_data - min_data)

MODEL_NAME = 'ConditionalGAN'
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

def to_onehot(x, num_classes=2):
    assert isinstance(x, int) or isinstance(x, (torch.LongTensor, torch.cuda.LongTensor))
    if isinstance(x, int):
        c = torch.zeros(1, num_classes).long()
        c[0][x] = 1
    else:
        x = x.cpu()
        c = torch.LongTensor(x.size(0), num_classes)
        c.zero_()
        c.scatter_(1, x, 1) # dim, index, src value
    return c

def get_sample_image(G, num_created, n_noise=100):
    """
        save sample 100 images
    """
    #img = np.zeros([280, 280])
    for j in range(2):
        c = torch.zeros([num_created, 2]).to(DEVICE)
        c[:, j] = 1
        z = torch.randn(num_created, n_noise).to(DEVICE) # number of random noise vectors created = 10
        y_hat = G(z,c).view(num_created, 3, 1000)
        #result = y_hat.cpu().data.numpy()
        if j == 0: # this is a left movement
          data_left = y_hat.cpu().data.numpy()
        else:
          data_right = y_hat.cpu().data.numpy()
    return data_left, data_right

class Discriminator(nn.Module):
    """
        Simple Discriminator w/ MLP
    """
    def __init__(self, input_size=3000, condition_size=2, num_classes=1):
        super(Discriminator, self).__init__()
        self.layer = nn.Sequential(
            nn.Linear(input_size+condition_size, 1024),
#            nn.LeakyReLU(0.2),
#            nn.Linear(4096, 2048),
            #nn.LeakyReLU(0.2),
            #nn.Linear(2048, 1024),
            nn.LeakyReLU(0.2),
            nn.Linear(1024, 512),
            nn.LeakyReLU(0.2),
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2),
            nn.Linear(256, num_classes),
            nn.Sigmoid(),
        )

    def forward(self, x, c):
        x, c = x.view(x.size(0), -1), c.view(c.size(0), -1).float()
        v = torch.cat((x, c), 1) # v: [input, label] concatenated vector
        y_ = self.layer(v)
        return y_

class Generator(nn.Module):
    """
        Simple Generator w/ MLP
    """
    def __init__(self, input_size=100, condition_size=2, num_classes=3000):
        super(Generator, self).__init__()
        self.layer = nn.Sequential(
            nn.Linear(input_size+condition_size, 128),
            nn.LeakyReLU(0.2),
            nn.Linear(128, 256),
            nn.BatchNorm1d(256),
            nn.LeakyReLU(0.2),
            nn.Linear(256, 512),
            nn.BatchNorm1d(512),
            nn.LeakyReLU(0.2),
            nn.Linear(512, 1024),
            nn.BatchNorm1d(1024),
            nn.LeakyReLU(0.2),
            #nn.Linear(1024, 2048),
            #nn.BatchNorm1d(2048),
            #nn.LeakyReLU(0.2),
           # nn.Linear(2048, 4096),
           # nn.BatchNorm1d(4096),
           # nn.LeakyReLU(0.2),
            nn.Linear(1024, num_classes),
            nn.Tanh()
        )

    def forward(self, x, c):
        x, c = x.view(x.size(0), -1), c.view(c.size(0), -1).float()
        v = torch.cat((x, c), 1) # v: [input, label] concatenated vector
        y_ = self.layer(v)
        y_ = y_.view(x.size(0), 1, 3, 1000)
        return y_

n_noise = 100

D = Discriminator().to(DEVICE)
G = Generator(n_noise).to(DEVICE)



class Sine_Cosine_Dataset(Dataset):
  def __init__(self, data, labels, transform=None):
    self.data = data
    self.labels = labels
    self.transform=transform

  def __len__(self):
    return len(self.data)

  def __getitem__(self, index):
    data = self.data[index]
    label = self.labels[index]

    if self.transform:
      data = self.transform(data)

    return data, label

dataset = Sine_Cosine_Dataset(data, labels)

data_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)

D_opt = torch.optim.Adam(D.parameters(), lr=learning_rate, betas=(0.5, 0.999))
G_opt = torch.optim.Adam(G.parameters(), lr=learning_rate, betas=(0.5, 0.999))

D_labels = torch.ones(batch_size, 1).to(DEVICE) # Discriminator Label to real
D_fakes = torch.zeros(batch_size, 1).to(DEVICE) # Discriminator Label to fake

if not os.path.exists('samples'):
    os.makedirs('samples')

Discriminator_loss = []
Generator_loss = []
steps = []
for epoch in range(max_epoch):
    for idx, (images, labels) in enumerate(data_loader):
        # Training Discriminator
        x = images.to(DEVICE).float()
        y = labels.view(batch_size, 1)
        y = y.long()
        #print(y)
        y = to_onehot(y).to(DEVICE)
        x_outputs = D(x, y)
        D_x_loss = criterion(x_outputs, D_labels)

        z = torch.randn(batch_size, n_noise).to(DEVICE)
        z_outputs = D(G(z, y), y)
        D_z_loss = criterion(z_outputs, D_fakes)
        D_loss = D_x_loss + D_z_loss

        D.zero_grad()
        D_loss.backward()
        D_opt.step()

        if step % n_critic == 0:
            # Training Generator
            z = torch.randn(batch_size, n_noise).to(DEVICE)
            z_outputs = D(G(z, y), y)
            G_loss = criterion(z_outputs, D_labels)

            G.zero_grad()
            G_loss.backward()
            G_opt.step()

        step += 1
    print('Epoch: {}/{}, Step: {}, D Loss: {}, G Loss: {}'.format(epoch, max_epoch, step, D_loss.item(), G_loss.item()))
    Discriminator_loss.append(D_loss.item())
    Generator_loss.append(G_loss.item())
    steps.append(step)
end_time = time.time()

elapsed_time = end_time - start_time

plt.figure(1)
plt.plot(Discriminator_loss)
plt.plot(Generator_loss)
plt.xlabel('Epochs')
plt.ylabel('loss')
plt.title('Conditional GAN Losses')
plt.legend(['Discriminator Loss', 'Generator Loss'])
plt.show()

print(f"Computation Time: {elapsed_time}")

G.eval()
data_left, data_right = get_sample_image(G, num_created, n_noise)

# Reshape the 3d array into a 2d array
left_2d = data_left.reshape(data_left.shape[0], -1)
right_2d = data_right.reshape(data_right.shape[0], -1)

file_name_right = 'Conditional_GAN_Data/data_right' + str(num_created) + '.csv'
file_name_left = 'Conditional_GAN_Data/data_left' + str(num_created) + '.csv'
os.makedirs('Conditional_GAN_Data', exist_ok =True)
savetxt(file_name_left, left_2d, delimiter=',')
savetxt(file_name_right, right_2d, delimiter=',')

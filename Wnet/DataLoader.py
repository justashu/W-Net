from PIL import Image
import torch
import torch.utils.data as Data
import os
import glob
import numpy as np
import pdb
from configure import Config
import math
import cupy as cp

config = Config()

class DataLoader():
    #initialization
    #datapath : the data folder of bsds500
    #mode : train/test/val
    def __init__(self, datapath,mode):
        #image container
        self.raw_data = []
        self.mode = mode
        #navigate to the image directory
        #images_path = os.path.join(datapath,'images')
        train_image_path = os.path.join(datapath,mode)
        file_list = []
        if(mode != "train"):
            test_image_folder = '/content/drive/MyDrive/DexiNed/opt/dataset/BIPED/edges/imgs/train/rgbr/real'
            # Get a list of all image files in the folder
            image_files = [file for file in os.listdir(test_image_folder) if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
            image_folder = test_image_folder
        #find all the images
        else:
            train_image_folder = '/content/drive/MyDrive/DexiNed/opt/dataset/BIPED/edges/imgs/train/rgbr/real'
            # Get a list of all image files in the folder
            image_files = [file for file in os.listdir(train_image_folder) if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
            image_folder = train_image_folder
        # Load the images
        for file_name in image_files:
            file_path = os.path.join(image_folder, file_name)
            with Image.open(file_path) as image:
                if image.mode != "RGB":
                    image = image.convert("RGB")
                self.raw_data.append(np.array(image.resize((config.inputsize[0], config.inputsize[1]), Image.BILINEAR)))

        #resize and align
        self.scale()
        #normalize
        self.transfer()
        
        #calculate weights by 2
        if(mode == "train"):
            self.dataset = self.get_dataset(self.raw_data, self.raw_data.shape,75)
        else:
            self.dataset = self.get_dataset(self.raw_data, self.raw_data.shape,75)
    
    def scale(self):
        for i in range(len(self.raw_data)):
            image = self.raw_data[i]
            self.raw_data[i] = np.stack((image[:,:,0],image[:,:,1],image[:,:,2]),axis = 0)
        self.raw_data = np.stack(self.raw_data,axis = 0)

    def transfer(self):
        #just for RGB 8-bit color
        self.raw_data = self.raw_data.astype(np.float)
        #for i in range(self.raw_data.shape[0]):
        #    Image.fromarray(self.raw_data[i].swapaxes(0,-1).astype(np.uint8)).save("./reconstruction/input_"+str(i)+".jpg")

    def torch_loader(self):
        return Data.DataLoader(
                                self.dataset,
                                batch_size = config.BatchSize,
                                shuffle = config.Shuffle,
                                num_workers = config.LoadThread,
                                pin_memory = True,
                            )

    def cal_weight(self,raw_data,shape):
        #According to the weight formula, when Euclidean distance < r,the weight is 0, so reduce the dissim matrix size to radius-1 to save time and space.
        print("calculating weights.")

        dissim = cp.zeros((shape[0],shape[1],shape[2],shape[3],(config.radius-1)*2+1,(config.radius-1)*2+1))
        data = cp.asarray(raw_data)
        padded_data = cp.pad(data,((0,0),(0,0),(config.radius-1,config.radius-1),(config.radius-1,config.radius-1)),'constant')
        for m in range(2*(config.radius-1)+1):
            for n in range(2*(config.radius-1)+1):
                dissim[:,:,:,:,m,n] = data-padded_data[:,:,m:shape[2]+m,n:shape[3]+n]
        #for i in range(dissim.shape[0]):
        #dissim = -cp.power(dissim,2).sum(1,keepdims = True)/config.sigmaI/config.sigmaI
        temp_dissim = cp.exp(-cp.power(dissim,2).sum(1,keepdims = True)/config.sigmaI**2)
        dist = cp.zeros((2*(config.radius-1)+1,2*(config.radius-1)+1))
        for m in range(1-config.radius,config.radius):
            for n in range(1-config.radius,config.radius):
                if m**2+n**2<config.radius**2:
                    dist[m+config.radius-1,n+config.radius-1] = cp.exp(-(m**2+n**2)/config.sigmaX**2)
        #for m in range(0,config.radius-1):
        #    temp_dissim[:,:,m,:,0:config.radius-1-m,:]=0.0
        #    temp_dissim[:,:,-1-m,:,m-config.radius+1:-1,:]=0.0
        #    temp_dissim[:,:,:,m,:,0:config.radius-1-m]=0.0
        #    temp_dissim[:,:,:,-1-m,:,m-config.radius+1:-1]=0.0
        print("weight calculated.")
        res = cp.multiply(temp_dissim,dist)
        #for m in range(50,70):

        #    print(m)
        #    for n in range(50,70):
        #        print(dissim[5,0,m,n])
        #print(dist)
        return res

    def get_dataset(self,raw_data,shape,batch_size):
        dataset = []
        for batch_id in range(0,shape[0],batch_size):
            print(batch_id)
            batch = raw_data[batch_id:min(shape[0],batch_id+batch_size)]
            if(self.mode == "train"):
                tmp_weight = self.cal_weight(batch,batch.shape)
                weight = cp.asnumpy(tmp_weight)
                dataset.append(Data.TensorDataset(torch.from_numpy(batch/256).float(),torch.from_numpy(weight).float()))
                del tmp_weight
            else:
                dataset.append(Data.TensorDataset(torch.from_numpy(batch/256).float()))
        cp.get_default_memory_pool().free_all_blocks()
        return Data.ConcatDataset(dataset)




import torch
import numpy as np
from configure import Config
from model import WNet
from Ncuts import NCutsLoss
from DataLoader import DataLoader

config = Config()

if __name__ == '__main__':
    cuda_device = torch.cuda.device(1)
    dataset = DataLoader(config.datapath,"train")
    dataloader = dataset.torch_loader()
    model = WNet()
    model.cuda()
    #optimizer
    optimizer = torch.optim.SGD(model.parameters(),lr = config.init_lr)
    reconstr = torch.nn.MSELoss(size_average = False).cuda()
    Ncuts = NCutsLoss().cuda()
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=config.lr_decay_iter, gamma=config.lr_decay)
    for epoch in range(config.max_iter):
        print("Epoch: "+str(epoch))
        scheduler.step()
        for step,(x,w) in enumerate(dataloader):
            
            #NCuts Loss
            x = x.cuda()
            w = w.cuda()
            x.requires_grad = False
            pred,rec_image = model(x)
            #pred.cuda()
            print("forward finished")
            ncuts_loss = Ncuts(pred,w)
            print("NCuts Loss: " + str(ncuts_loss.data))
            optimizer.zero_grad()
            ncuts_loss.backward()
            optimizer.step()
            
            #Reconstruction Loss
            pred,rec_image = model(x)
            rec_loss = reconstr(rec_image,x)
            print("Reconstruction Loss: " + str(rec_loss.data))
            optimizer.zero_grad()
            rec_loss.backward()
            optimizer.step()
    

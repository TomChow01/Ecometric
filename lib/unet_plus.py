"""Pytorch models for UNet and UNet++ with added non-convolutional input.

Adapted from https://github.com/4uiiurz1/pytorch-nested-unet"""

import torch
from torch import nn


class VGGBlock(nn.Module):
    def __init__(self, in_channels, middle_channels, out_channels):
        super().__init__()
        self.relu = nn.ReLU(inplace=True)
        self.conv1 = nn.Conv2d(in_channels, middle_channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(middle_channels)
        self.conv2 = nn.Conv2d(middle_channels, out_channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_channels)

    def forward(self, x):
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        return out


class FCBlock(nn.Module):
    def __init__(self, in_features, out_features):
        super(FCBlock, self).__init__()
        block= []

        block.append(nn.Linear(in_features, out_features))
        block.append(nn.ReLU())
        block.append(nn.BatchNorm1d(out_features))

        block.append(nn.Linear(out_features, out_features))
        block.append(nn.ReLU())
        block.append(nn.BatchNorm1d(out_features))

        self.block = nn.Sequential(*block)

    def forward(self, x):
        out = self.block(x)
        return out


class NestedUNet(nn.Module):
    def __init__(self,
                num_classes,
                input_channels=3,
                input_1d_features=0,
                nb_filter = [32, 64, 128, 256, 512],
                deep_supervision=False,
                ):
        super().__init__()
        
        self.flat_features = (input_1d_features>0)
        self.deep_supervision = deep_supervision

        self.pool = nn.MaxPool2d(2, 2)
        self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        
        if self.flat_features:
            self.linear1d = FCBlock(input_1d_features, nb_filter[0])

        self.conv0_0 = VGGBlock(input_channels, nb_filter[0], nb_filter[0])
        self.conv1_0 = VGGBlock(nb_filter[0], nb_filter[1], nb_filter[1])
        self.conv2_0 = VGGBlock(nb_filter[1], nb_filter[2], nb_filter[2])
        self.conv3_0 = VGGBlock(nb_filter[2], nb_filter[3], nb_filter[3])
        self.conv4_0 = VGGBlock(nb_filter[3], nb_filter[4], nb_filter[4])

        self.conv0_1 = VGGBlock(nb_filter[0]+nb_filter[1], nb_filter[0], nb_filter[0])
        self.conv1_1 = VGGBlock(nb_filter[1]+nb_filter[2], nb_filter[1], nb_filter[1])
        self.conv2_1 = VGGBlock(nb_filter[2]+nb_filter[3], nb_filter[2], nb_filter[2])
        self.conv3_1 = VGGBlock(nb_filter[3]+nb_filter[4], nb_filter[3], nb_filter[3])

        self.conv0_2 = VGGBlock(nb_filter[0]*2+nb_filter[1], nb_filter[0], nb_filter[0])
        self.conv1_2 = VGGBlock(nb_filter[1]*2+nb_filter[2], nb_filter[1], nb_filter[1])
        self.conv2_2 = VGGBlock(nb_filter[2]*2+nb_filter[3], nb_filter[2], nb_filter[2])

        self.conv0_3 = VGGBlock(nb_filter[0]*3+nb_filter[1], nb_filter[0], nb_filter[0])
        self.conv1_3 = VGGBlock(nb_filter[1]*3+nb_filter[2], nb_filter[1], nb_filter[1])

        self.conv0_4 = VGGBlock(nb_filter[0]*4+nb_filter[1], nb_filter[0], nb_filter[0])

        if self.deep_supervision:
            self.final1 = nn.Sequential(nn.Conv2d(nb_filter[0], num_classes, kernel_size=1), nn.ReLU())
            self.final2 = nn.Sequential(nn.Conv2d(nb_filter[0], num_classes, kernel_size=1), nn.ReLU())
            self.final3 = nn.Sequential(nn.Conv2d(nb_filter[0], num_classes, kernel_size=1), nn.ReLU())
            self.final4 = nn.Sequential(nn.Conv2d(nb_filter[0], num_classes, kernel_size=1), nn.ReLU())
        else:
            self.final = nn.Sequential(nn.Conv2d(nb_filter[0], num_classes, kernel_size=1), nn.ReLU())

    def forward(self, input):

        if self.flat_features:
            x_2d = self.conv0_0(input[0])
            x_flat = self.linear1d(input[1])
            x0_0 = torch.add(x_2d, x_flat.view(-1, x_flat.shape[1], 1, 1 ))
        else:
            x0_0 = self.conv0_0(input)

        x1_0 = self.conv1_0(self.pool(x0_0))
        x0_1 = self.conv0_1(torch.cat([x0_0, self.up(x1_0)], 1))

        x2_0 = self.conv2_0(self.pool(x1_0))
        x1_1 = self.conv1_1(torch.cat([x1_0, self.up(x2_0)], 1))
        x0_2 = self.conv0_2(torch.cat([x0_0, x0_1, self.up(x1_1)], 1))

        x3_0 = self.conv3_0(self.pool(x2_0))
        x2_1 = self.conv2_1(torch.cat([x2_0, self.up(x3_0)], 1))
        x1_2 = self.conv1_2(torch.cat([x1_0, x1_1, self.up(x2_1)], 1))
        x0_3 = self.conv0_3(torch.cat([x0_0, x0_1, x0_2, self.up(x1_2)], 1))

        x4_0 = self.conv4_0(self.pool(x3_0))
        x3_1 = self.conv3_1(torch.cat([x3_0, self.up(x4_0)], 1))
        x2_2 = self.conv2_2(torch.cat([x2_0, x2_1, self.up(x3_1)], 1))
        x1_3 = self.conv1_3(torch.cat([x1_0, x1_1, x1_2, self.up(x2_2)], 1))
        x0_4 = self.conv0_4(torch.cat([x0_0, x0_1, x0_2, x0_3, self.up(x1_3)], 1))
        
        if self.deep_supervision:
            output1 = self.final1(x0_1)
            output2 = self.final2(x0_2)
            output3 = self.final3(x0_3)
            output4 = self.final4(x0_4)
            return [output1, output2, output3, output4]

        else:
            output = self.final(x0_4)
            return output

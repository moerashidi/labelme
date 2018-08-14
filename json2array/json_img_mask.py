import numpy as np
import json
import matplotlib.pylab as plt
from matplotlib.path import Path
import base64
import io
import PIL.Image
import cv2
from skimage.transform import resize
import matplotlib.patches as patches
import matplotlib.cm as cm
import matplotlib.gridspec as gridspec



class Labelme_json_convertor():
    """
    Takes json file created by Labelme program and outputs 
    * data as dict
    * ploygons
    * labels array
    * label names
    * image 2D array
    * mask 2D array
    """
     

    def __init__(self,file_path):
        


        self.data=json.load((open(file_path))) # outputs json file as a dictionary


        # outputs the poygons, labels and label names as numpy arrays
        polys=[]
        labels=[]
        label_n=[]

        for i in range(len(self.data['shapes'])):
            polys.append(np.array(self.data['shapes'][i]['points']))
        polys=np.array(polys)

        for i in range(len(self.data['shapes'])):
            labels.append(self.data['shapes'][i]['label'])
        label_names=list(sorted(set(labels)))

        for label in labels:
            for idx,uni_label in enumerate(label_names):
                if label==uni_label:
                    label_n.append(idx)
        labels=np.asarray(label_n)
        label_names=['Background']+label_names
        self.polys=polys
        self.labels=labels
        self.label_names=label_names
        
    
    def img_mask(self,resize_factor=.25): # outputs image and mask as 2D numpy arrays
        img_b64=self.data['imageData']
        f = io.BytesIO()
        f.write(base64.b64decode(img_b64))
        img_array = np.array(PIL.Image.open(f))
        img_array=resize(img_array,(int(img_array.shape[0]*resize_factor),int(img_array.shape[1]*resize_factor)),mode='constant',anti_aliasing=True)
        polys=self.polys*resize_factor
        nx, ny = img_array.shape[1], img_array.shape[0]
        mask=np.zeros((ny,nx))
        
        for i in range(len(self.labels)):
            poly_verts =polys[i]
            x, y = np.meshgrid(np.arange(nx), np.arange(ny))
            x, y = x.flatten(), y.flatten()
            points = np.vstack((x,y)).T
            path = Path(poly_verts,closed=False)
            grid = path.contains_points(points)
            grid = grid.reshape((ny,nx))
            mask[grid]=self.labels[i]+1
            
        return img_array, mask
            
        

def plot_image_mask(img,mask,filename,label_names,show=True,save=True):
    """
    takes the image and the mask array and dispplay mask on top of the STM image.
    """
    fig, ax = plt.subplots(figsize=(10,10))
    ax.imshow(img,cmap='Greys')
    cax2=ax.imshow(mask, alpha=.5,cmap=plt.cm.get_cmap('jet', len(label_names)))
    ax.set_axis_off()
    cbar = fig.colorbar(cax2,aspect=5)
    cbar.ax.get_yaxis().set_ticks([])
    for j, lab in enumerate(label_names):
        cbar.ax.text(.5, (2 * j + 1) / (len(label_names)*2), lab,
                     ha='center', va='center',rotation=0,fontsize=10,weight='black')
    if save:
        plt.savefig('{}.png'.format(filename))
    if show:
        plt.show()
        


if __name__=='__main__':

    file_name='bee_flower.json'

    file1=Labelme_json_convertor(file_name)
    label_names=file1.label_names
    img,mask=file1.img_mask()
    plot_image_mask(img,mask,'imag_mask',label_names,show=True,save=False)
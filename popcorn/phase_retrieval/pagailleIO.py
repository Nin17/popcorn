
import fabio
import fabio.edfimage as edf
import fabio.tifimage as tif
#import edfimage

#from PIL import Image
import numpy as np
import os



def openImage(filename):
    filename=str(filename)
    im=fabio.open(filename)
    imarray=im.data
    return imarray

def getHeader(filename):
    im = fabio.open(filename)
    header= im.header
    return header



def saveTiff16bit(data,filename,minIm=0,maxIm=0,header=None):
    if(minIm==maxIm):
        minIm=np.amin(data)
        maxIm= np.amax(data)
    datatoStore=65536*(data-minIm)/(maxIm-minIm)
    datatoStore[datatoStore>65635]=65535
    datatoStore[datatoStore <0] = 0
    datatoStore=np.asarray(datatoStore,np.uint16)

    if(header!=None):
        tif.TifImage(data=datatoStore,header=header).write(filename)
    else:
        tif.TifImage(data=datatoStore).write(filename)





def openSeq(filenames):
    if len(filenames) >0 :
        data=openImage(str(filenames[0]))
        height,width=data.shape
        toReturn = np.zeros((len(filenames), height, width),dtype=np.float32)
        i=0
        for file in filenames:
            data=openImage(str(file))
            toReturn[i,:,:]=data
            i+=1
        return toReturn
    raise Exception('spytlabIOError')


def makeDarkMean(Darkfiedls):
    nbslices, height, width = Darkfiedls.shape
    meanSlice = np.mean(Darkfiedls, axis=0)
    print ('-----------------------  mean Dark calculation done ------------------------- ')
    OutputFileName = '/Users/helene/PycharmProjects/spytlab/meanDarkTest.edf'
    outputEdf = edf.EdfFile(OutputFileName, access='wb+')
    outputEdf.WriteImage({}, meanSlice)
    return meanSlice


def remove_filename_in_path(path):
    """remove the file name from a path

    Args:
        path (str): complete path

    Returns:
        complete path without the file name
    """
    if len(path.split("\\")) > 1:
        splitter = "\\"
    else:
        splitter = "/"
    path_list = path.split(splitter)[:-1]
    new_path = ""
    for elt in path_list:
        new_path += elt + splitter

    return new_path

def create_directory(path):
    """creates a directory at the specified path

    Args:
        path (str): complete path

    Returns:
        None
    """
    if not os.path.exists(path):
        os.makedirs(path)
        
def save_tif_image(image, filename, bit=32, header=None):
    """saves an image to .tif format (either int16 or float32)

    Args:
        image (numpy.ndarray): 2D image
        filename (str):        file name
        bit (int):             16: int16, 32: float32
        header (str):          header

    Returns:
        None
    """
    create_directory(remove_filename_in_path(filename))

    if header:
        if bit == 32:
            tif.TifImage(data=image.astype(np.float32), header=header).write(filename)
        else:
            tif.TifImage(data=image.astype(np.uint16), header=header).write(filename)
    else:
        if bit == 32:
            tif.TifImage(data=image.astype(np.float32)).write(filename)
        else:
            tif.TifImage(data=image.astype(np.uint16)).write(filename)

def save_image(data,filename):
    if filename.split(".")[-1]=="tif":
        save_tif_image(data, filename)
    if filename.split(".")[-1]=="edf":
        saveEdf(data, filename)

def saveEdf(data,filename):
    print(filename)
    dataToStore=data.astype(np.float32)
    edf.EdfImage(data=dataToStore).write(filename)


def save3D_Edf(data,filename):
    nbslices,height,width=data.shape
    for i in range(nbslices):
        textSlice='%4.4d'%i
        dataToSave=data[i,:,:]
        filenameSlice=filename+textSlice+'.edf'
        saveEdf(dataToSave,filenameSlice)



#def savePNG(data,filename,min=0,max=0):
    #if min == max:
    #    min=np.amin(data)
    #    max= np.amax(data)
    #data16bit=data-min/(max-min)
    #data16bit=np.asarray(data16bit,dtype=np.uint16)

    #scipy.misc.imsave(filename,data16bit)




if __name__ == "__main__":

    # filename='ref1-1.edf'
    # filenames=glob.glob('*.edf')
    # data=openImage(filename)
    # savePNG(data,'ref.png',100,450)
    # print( data.shape)
    #
    #
    # rootfolder = '/Volumes/VISITOR/md1097/id17/Phantoms/TwoDimensionalPhantom/GrilleFils/Absorption52keV/'
    # referencesFilenames = glob.glob(rootfolder + 'Projref/*.edf')
    # sampleFilenames = glob.glob(rootfolder + 'Proj/*.edf')
    # referencesFilenames.sort()
    # sampleFilenames.sort()
    # print(' lalalal ')
    # print (referencesFilenames)
    # print (sampleFilenames)

    inputImageFilename = '/Volumes/ID17/speckle/md1097/id17/Phantoms/ThreeDimensionalPhantom/OpticalFlow/dx32/dx_Speckle_Foam1_52keV_6um_xss_bis_012_0000.edf'
    data=openImage(inputImageFilename)
    print(data.dtype)
    print(data)
    outputImageFilename = '/Volumes/ID17/speckle/md1097/id17/Phantoms/ThreeDimensionalPhantom/OpticalFlowTest26Apr/dx0001_32bit.edf'
    saveEdf(data,outputImageFilename)
    print(data)
    print('At the end '+str(data.dtype))


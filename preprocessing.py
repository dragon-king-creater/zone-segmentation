import os
import numpy as np
import SimpleITK as sitk
import utils
import math



def getIsotropicImgs(inputDir):

    files = os.listdir(inputDir)

    for file in files:

        # load images
        if 'tra.nrrd' in file:
            img_tra = sitk.ReadImage(os.path.join(inputDir, file))
        if 'cor.nrrd' in file:
            img_cor = sitk.ReadImage(os.path.join(inputDir, file))
        if 'sag.nrrd' in file:
            img_sag = sitk.ReadImage(os.path.join(inputDir, file))


        # upsample transversal image to isotropic voxel size (isotropic transversal image coordinate system is used as reference coordinate system)
        tra_HR = utils.resampleImage(img_tra, [0.5, 0.5, 0.5], sitk.sitkLinear,0)

        # resample coronal and sagittal to tra_HR space
        # resample coronal to tra_HR and obtain mask (voxels that are defined in coronal image )
        cor_toTraHR = utils.resampleImage(img_cor, [0.5, 0.5, 0.5], sitk.sitkLinear,0)

        # resample sagittal to tra_HR and obtain mask (voxels that are defined in sagittal image )
        sag_toTraHR = utils.resampleImage(img_sag, [0.5, 0.5, 0.5], sitk.sitkLinear,0)

        return tra_HR, cor_toTraHR, sag_toTraHR



# crop images to overlapping ROI and resample to isotropic transversal space
# input order of imgs: tra, cor, sag
def getCroppedIsotropicImgs(*imgs):

    img_tra = imgs[0]
    img_cor = imgs[1]
    img_sag = imgs[2]

    # normalize intensities
    print('... normalize intensities ...')
    img_tra, img_cor, img_sag = utils.normalizeIntensitiesPercentile(img_tra, img_cor, img_sag)

    # get intersecting region (bounding box)
    print('... get intersecting region (ROI) ...')

    # upsample transversal image to isotropic voxel size (isotropic transversal image coordinate system is used as reference coordinate system)
    tra_HR = utils.resampleImage(img_tra, [0.5, 0.5, 0.5], sitk.sitkLinear,0)
    tra_HR = utils.sizeCorrectionImage(tra_HR, factor=6, imgSize=168)

    # resample coronal and sagittal to tra_HR space
    # resample coronal to tra_HR and obtain mask (voxels that are defined in coronal image )
    cor_toTraHR = utils.resampleToReference(img_cor, tra_HR, sitk.sitkLinear,-1)
    cor_mask = utils.binaryThresholdImage(cor_toTraHR, 0)

    tra_HR_Float = utils.castImage(tra_HR, sitk.sitkFloat32)
    cor_mask_Float = utils.castImage(cor_mask, sitk.sitkFloat32)
    # mask transversal volume (set voxels, that are defined only in transversal image but not in coronal image, to 0)
    coronal_masked_traHR = sitk.Multiply(tra_HR_Float, cor_mask_Float)

    # resample sagittal to tra_HR and obtain mask (voxels that are defined in sagittal image )
    sag_toTraHR = utils.resampleToReference(img_sag, tra_HR, sitk.sitkLinear,-1)
    sag_mask = utils.binaryThresholdImage(sag_toTraHR, 0)
    # mask sagittal volume
    sag_mask_Float = utils.castImage(sag_mask, sitk.sitkFloat32)

    # masked image contains voxels, that are defined in tra, cor and sag images
    maskedImg = sitk.Multiply(sag_mask_Float, coronal_masked_traHR)
    boundingBox = utils.getBoundingBox(maskedImg)

    # correct the size and start position of the bounding box according to new size
    start, size = sizeCorrectionBoundingBox(boundingBox, newSize=168, factor=6)
    start[2] = 0
    size[2] = tra_HR.GetSize()[2]

    # resample cor and sag to isotropic transversal image space
    cor_traHR = utils.resampleToReference(img_cor, tra_HR, sitk.sitkLinear, -1)
    sag_traHR = utils.resampleToReference(img_sag, tra_HR, sitk.sitkLinear,-1)

    ## extract bounding box for all planes
    region_tra = sitk.RegionOfInterest(tra_HR, [size[0], size[1], size[2]],
                                       [start[0], start[1], start[2]])
    maxVal = utils.getMaximumValue(region_tra)
    region_tra = utils.thresholdImage(region_tra, 0, maxVal, 0)

    region_cor = sitk.RegionOfInterest(cor_traHR, [size[0], size[1], size[2]],
                                       [start[0], start[1], start[2]])
    maxVal = utils.getMaximumValue(region_cor)
    region_cor = utils.thresholdImage(region_cor, 0, maxVal, 0)

    region_sag = sitk.RegionOfInterest(sag_traHR, [size[0], size[1], size[2]],
                                       [start[0], start[1], start[2]])
    maxVal = utils.getMaximumValue(region_sag)
    region_sag = utils.thresholdImage(region_sag, 0, maxVal, 0)

    return region_tra, region_cor, region_sag, start, size



# adapt the start index of the ROI to the manual bounding box size
# (assumes that all ROIs are smaller than newSize pixels in length and width)
def sizeCorrectionBoundingBox(boundingBox, newSize, factor):
    # correct the start index according to the new size of the bounding box
    start = boundingBox[0:3]
    start = list(start)
    size = boundingBox[3:6]
    size = list(size)
    start[0] = start[0] - math.floor((newSize - size[0]) / 2)
    start[1] = start[1] - math.floor((newSize - size[1]) / 2)

    # check if BB start can be divided by the factor (essential if ROI needs to be extracted from non-isotropic image)
    if (start[0]) % factor != 0:
        cX = (start[0] % factor)
        newStart = start[0] - cX
        start[0] = int(newStart)

    # y-direction
    if (start[1]) % factor != 0:
        cY = (start[1] % factor)
        start[1] = int(start[1] - cY)

    size[0] = newSize
    size[1] = newSize

    return start, size


def getROI(inputDir):

    files = os.listdir(inputDir)

    for file in files:

        # load images
        if 'tra.nrrd' in file:
            img_tra = sitk.ReadImage(os.path.join(inputDir, file))
        if 'cor.nrrd' in file:
            img_cor = sitk.ReadImage(os.path.join(inputDir, file))
        if 'sag.nrrd' in file:
            img_sag = sitk.ReadImage(os.path.join(inputDir, file))

    # preprocess and save to numpy array
    print('... preprocess images and save to array...')
    roi_tra, roi_cor, roi_sag, start, size = getCroppedIsotropicImgs(img_tra,
                                                                     img_cor, img_sag)


    #### included for zone segmentation (not upsampled transversal image as input)
    tra_orig_roi = getROIFromOriginalTra(img_tra, size=size, start=start)

    print('... normalize intensities ...')
    tra_orig_roi = utils.normalizeIntensitiesPercentile(tra_orig_roi)[0]

    # pad z-axis of transversal image to size of 32
    filter = sitk.ConstantPadImageFilter()
    filter.SetPadLowerBound([0, 0, 2])
    filter.SetPadUpperBound([0, 0, 2])
    filter.SetConstant(0)
    tra_orig_roi = filter.Execute(tra_orig_roi)

    # save image
    sitk.WriteImage(tra_orig_roi, os.path.join(inputDir, 'roi_tra.nrrd'))

    return tra_orig_roi



def getROIFromOriginalTra(original_tra, size, start):

    tra = original_tra
    tra = utils.resampleImage(tra, [0.5,0.5,3], sitk.sitkLinear,0)
    tra = utils.sizeCorrectionImage(tra, factor=6, imgSize=28)
    print('tra size: ', tra.GetSize())
    tra = sitk.RegionOfInterest(tra, [size[0], size[1], int(size[2]/6)],
                               [start[0], start[1], int(start[2]/6)])

    return tra



def createAnisotropicArray(input_img):

    arr = sitk.GetArrayFromImage(input_img)
    out_arr= np.zeros([1, 32, 168, 168, 1])
    out_arr[0, :, :, :, 0] = arr

    return out_arr


def preprocessImage(imgDir):

    roi_tra = getROI(imgDir)
    arr = createAnisotropicArray(input_img= roi_tra)

    return arr

def maskImage(upsampled_tra, cor, sag, GT):

    res_cor = utils.resampleToReference(cor, upsampled_tra, sitk.sitkLinear, defaultValue=-1)
    res_sag = utils.resampleToReference(sag, upsampled_tra, sitk.sitkLinear, defaultValue=-1)
    mask_cor = sitk.BinaryThreshold(res_cor, -1, 0.01, 1, 0)
    mask_sag = sitk.BinaryThreshold(res_sag, -1, 0.01, 1, 0)

    # mask images
    tra = sitk.Multiply(upsampled_tra, mask_cor)
    tra = sitk.Multiply(tra, mask_sag)

    cor = sitk.Multiply(res_cor, mask_sag)
    sag = sitk.Multiply(res_sag, mask_cor)

    GT = sitk.Multiply(GT, mask_cor)
    GT = sitk.Multiply(GT, mask_sag)



    return tra, cor, sag, GT

def resample_segmentations(pred_img, ref_image):

    pz = sitk.BinaryThreshold(pred_img, 1,1)
    cz = sitk.BinaryThreshold(pred_img, 2,2)
    us = sitk.BinaryThreshold(pred_img, 3,3)
    afs = sitk.BinaryThreshold(pred_img, 4,4)
    bg = sitk.BinaryThreshold(pred_img, 0,0)

    # calculate distance transformations for segments and resample to reference space
    pz_dis = utils.resampleToReference(sitk.SignedMaurerDistanceMap(pz, insideIsPositive=True, squaredDistance=False,
                                          useImageSpacing=True), ref_image, sitk.sitkLinear, -3000)
    pz_dis = sitk.DiscreteGaussian(pz_dis, 1.0)

    cz_dis = utils.resampleToReference(sitk.SignedMaurerDistanceMap(cz, insideIsPositive=True, squaredDistance=False,
                                          useImageSpacing=True), ref_image, sitk.sitkLinear, -3000)
    cz_dis = sitk.DiscreteGaussian(cz_dis, 1.0)

    us_dis = utils.resampleToReference(sitk.SignedMaurerDistanceMap(us, insideIsPositive=True, squaredDistance=False,
                                          useImageSpacing=True), ref_image, sitk.sitkLinear, -3000)
    us_dis = sitk.DiscreteGaussian(us_dis, 1.0)

    afs_dis = utils.resampleToReference(sitk.SignedMaurerDistanceMap(afs, insideIsPositive=True, squaredDistance=False,
                                          useImageSpacing=True), ref_image, sitk.sitkLinear, -3000)
    afs_dis = sitk.DiscreteGaussian(afs_dis, 1.0)

    bg_dis = utils.resampleToReference(sitk.SignedMaurerDistanceMap(bg, insideIsPositive=True, squaredDistance=False,
                                           useImageSpacing=True), ref_image, sitk.sitkLinear,-3000)
    bg_dis = sitk.DiscreteGaussian(bg_dis, 1.0)

    ref_size = ref_image.GetSize()
    final_GT = np.zeros([ref_size[2], ref_size[1], ref_size[0]])

    for x in range(0, ref_image.GetSize()[0]):
        for y in range(0, ref_image.GetSize()[1]):
            for z in range(0, ref_image.GetSize()[2]):
                array = [bg_dis.GetPixel(x, y, z), pz_dis.GetPixel(x, y, z), cz_dis.GetPixel(x, y, z), us_dis.GetPixel(x, y, z),
                         afs_dis.GetPixel(x, y, z)]
                maxValue = max(array)
                if maxValue == -3000:
                    final_GT[z, y, x]=5
                else:
                    max_index = array.index(maxValue)
                    final_GT[z, y, x] = max_index
                    # print(x,y,z)
                    # print( maxValue)
    final_GT_img = sitk.GetImageFromArray(final_GT)
    final_GT_img = sitk.Threshold(final_GT_img, 1,5,0)
    final_GT_img.CopyInformation(ref_image)

    sitk.WriteImage(final_GT_img, 'prediction.nrrd')

    return final_GT_img


if __name__ == '__main__':

    preprocessImage('data-test/ProstateX-0227')



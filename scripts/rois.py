import omero
import omero.cli
from omero.gateway import BlitzGateway
from omero_rois import mask_from_binary_image
import sys
from skimage.io import imread
from omero.model import RoiI, MaskI


"""
This script has a lot of dependencies, best create a micromamba env for it:

# install micromamba
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)

# add alias
echo "alias mm=micromamba" >> ~/.bashrc
source ~/.bashrc

# create env and install stuff
mm env create -n cli python=3.10
mm activate cli
mm install omero-py
pip install ome_model omero-rois scikit-image
"""


PROJECT_NAME = "idr0163-greenwald-tnbc/experimentA"

# /bia-idr/S-BIAD1288/TONIC/segmentation_data/deepcell_output/TONIC_TMA10_R10C6_nuclear.tiff
# /bia-idr/S-BIAD1288/TONIC/segmentation_data/deepcell_output/TONIC_TMA10_R10C6_whole_cell.tiff

def read_label_image(file):
    image_name = file[file.rfind("/")+1:]
    if "nuclear" in image_name:
        image_name = image_name.replace("_nuclear.tiff", "")
        roi_name = "nuclear"
    elif "_whole_cell" in image_name:
        image_name = image_name.replace("_whole_cell.tiff", "")
        roi_name = "whole cell"
    else:
        print(f"Can't handle {file}.")
        exit(1)
    return image_name, roi_name, imread(file)


def load_images(conn):
    project = conn.getObject("Project", attributes={"name": PROJECT_NAME})
    images = dict()
    for dataset in project.listChildren():
        for image in dataset.listChildren():
            images[image.getName()] = image
    return images


def masks_from_label_image(
        labelim, rgba=None, z=None, c=None, t=None, text=None,
        raise_on_no_mask=True):
    """
    Create mask shapes from a label image (background=0)

    :param numpy.array labelim: 2D label array
    :param rgba int-4-tuple: Optional (red, green, blue, alpha) colour
    :param z: Optional Z-index for the mask
    :param c: Optional C-index for the mask
    :param t: Optional T-index for the mask
    :param text: Optional text for the mask
    :param raise_on_no_mask: If True (default) throw an exception if no mask
           found, otherwise return an empty Mask
    :return: A list of OMERO masks in label order ([] if no labels found)

    """
    masks = []
    for i in range(1, labelim.max() + 1):
        if text:
            name = f"{text} {i}"
        else:
            name = None
        bin_image = labelim == i
        bin_image = bin_image[0]
        mask = mask_from_binary_image(bin_image, rgba, z, c, t, name,
                                      raise_on_no_mask)
        masks.append(mask)
    return masks


def create_rois(image, roi_name, image_data):
    masks = masks_from_label_image(image_data, rgba=(255, 255, 255, 128), text=roi_name)
    rois = []
    for mask in masks:
        roi = omero.model.RoiI()
        roi.setImage(image._obj)
        roi.addShape(mask)
        rois.append(roi)
    return rois


def save_rois(conn, rois):
    us = conn.getUpdateService()
    for roi in rois:
        roi1 = us.saveAndReturnObject(roi)
        assert roi1
    print(f"Saved {len(rois)} ROIs.")


def delete_rois(conn, image):
    result = conn.getRoiService().findByImage(image.id, None)
    roi_ids = [x.getId().getValue() for x in result.rois]
    if roi_ids:
        conn.deleteObjects("Roi", roi_ids, deleteChildren=True, wait=True)
        print(f"Deleted {len(roi_ids)} ROIs.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python rois.py <MASK_IMAGE>")
        print("e. g. python rois.py /bia-idr/S-BIAD1288/TONIC/segmentation_data/deepcell_output/TONIC_TMA10_R10C6_nuclear.tiff")
        exit(1)

    with omero.cli.cli_login() as c:
        conn = BlitzGateway(client_obj=c.get_client())
        images = load_images(conn)
        image_name, roi_name, data = read_label_image(sys.argv[1])
        if image_name not in images:
            print(f"Can't find image {image_name}.")
            exit(1)
        print(f"Processing {roi_name} ROIs for {image_name}.")
        rois = create_rois(images[image_name], roi_name, data)
        if len(sys.argv) == 3 and sys.argv[2] == "d":
            delete_rois(conn, images[image_name])
        save_rois(conn, rois)


if __name__ == "__main__":
    main()

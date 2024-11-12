import csv
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
PROCESSED_NAME = "/tmp/idr0163-experimentA-processed.csv"
PROCESSED_IMAGE_COL = "fov"
PROCESSED_CELL_LABEL_COL = "label"
PROCESSED_NUC_LABEL_COL = "label_nuclear"

TYPE_NUCLEAR = "nuclear"
TYPE_WHOLE_CELL = "whole cell"

# /bia-idr/S-BIAD1288/TONIC/segmentation_data/deepcell_output/TONIC_TMA10_R10C6_nuclear.tiff
# /bia-idr/S-BIAD1288/TONIC/segmentation_data/deepcell_output/TONIC_TMA10_R10C6_whole_cell.tiff

def extract_processed_data(image_name):
    data = []
    with open(PROCESSED_NAME, mode="r") as csvfile:
        reader = csv.DictReader(csvfile)
        fnames = reader.fieldnames.copy()
        fnames.insert(0, "Image")
        fnames.insert(0, "Roi")
        for row in reader:
            if row[PROCESSED_IMAGE_COL] != image_name:
                continue
            row["Image"] = -1
            row["Roi"] = -1
            data.append(row)
    return fnames, data


def save_processed(image_name, roi_type, fnames, data):
    filename = f"{image_name}-{roi_type}_processed.csv"
    with open(filename, mode="w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    print(f"Saved {filename}.")


def read_label_image(file):
    image_name = file[file.rfind("/")+1:]
    if "nuclear" in image_name:
        image_name = image_name.replace("_nuclear.tiff", "")
        roi_type = TYPE_NUCLEAR
    elif "_whole_cell" in image_name:
        image_name = image_name.replace("_whole_cell.tiff", "")
        roi_type = TYPE_WHOLE_CELL
    else:
        print(f"Can't handle {file}.")
        exit(1)
    return image_name, roi_type, imread(file)


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
    masks = dict()
    for i in range(1, labelim.max() + 1):
        if text:
            name = f"{text} {i}"
        else:
            name = None
        bin_image = labelim == i
        bin_image = bin_image[0]
        mask = mask_from_binary_image(bin_image, rgba, z, c, t, name,
                                      raise_on_no_mask)
        masks[str(i)] = mask
    return masks


def create_rois(image, roi_type, image_data):
    masks = masks_from_label_image(image_data, rgba=(255, 255, 255, 128), text=roi_type)
    rois = dict()
    for label, mask in masks.items():
        roi = omero.model.RoiI()
        roi.setImage(image._obj)
        roi.addShape(mask)
        rois[label] = roi
    return rois


def save_rois(conn, rois, roi_type, proc_data):
    us = conn.getUpdateService()
    for label, roi in rois.items():
        saved = us.saveAndReturnObject(roi)
        if roi_type == TYPE_NUCLEAR:
            key = PROCESSED_NUC_LABEL_COL
        else:
            key = PROCESSED_CELL_LABEL_COL
        for row in proc_data:
            if int(float(row[key])) == int(label):
                row["Roi"] = saved.getId().getValue()
                row["Image"] = saved.getImage().getId().getValue()
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
        image_name, roi_type, data = read_label_image(sys.argv[1])
        if image_name not in images:
            print(f"Can't find image {image_name}.")
            exit(1)
        print(f"Processing {roi_type} ROIs for {image_name}.")
        rois = create_rois(images[image_name], roi_type, data)
        if len(sys.argv) == 3 and sys.argv[2] == "d":
            delete_rois(conn, images[image_name])
        fnames, proc_data = extract_processed_data(image_name)
        save_rois(conn, rois, roi_type, proc_data)
        save_processed(image_name, roi_type, fnames, proc_data)


if __name__ == "__main__":
    main()

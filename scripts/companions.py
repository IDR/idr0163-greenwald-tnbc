import pathlib
import sys
import subprocess
from ome_model.experimental import Image, create_companion
from tifffile import tifffile
import csv


def get_dimensions(img_file, order="xyczt"):
    try:
        img = tifffile.imread(img_file)
        res = dict()
        for i, d in enumerate(order):
            if i < len(img.shape):
                res[d] = img.shape[i]
            else:
                res[d] = 1
        return res
    except Exception:
        print(f"WARN: {img_file} not readable by tifffile!")
        return None


def write_companion(img, img_name, dir):
    companion_file = f"{dir}/{img_name}.companion.ome"
    create_companion(images=[img], out=companion_file)

    # Indent XML for readability
    proc = subprocess.Popen(
        ['xmllint', '--format', '-o', companion_file, companion_file],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE)
    (output, error_output) = proc.communicate()
    print(f"Created {companion_file}")


def get_channel_order(file):
    with open(file, mode='r') as input_file:
        csv_reader = csv.DictReader(input_file)
        order = dict()
        for row in csv_reader:
            order[row['Channel']] = int(row['Order'])
        return order

def process_img_dir(img_dir):
    x = 0
    y = 0
    z = 1
    c = 0
    t = 1
    files = []
    for img_file in img_dir.iterdir():
        if not img_file.is_file():
            continue

        name = pathlib.Path(img_file).stem
        if name not in channel_order:
            print(f"WARN: Can't get channel index for {name}, excluding {img_file}.")
            continue

        dims = get_dimensions(img_file)
        if not dims:
            continue
        img_name = img_dir.stem
        img_file = f"{img_file.parent.name}/{img_file.name}"
        if x == 0:
            x = dims['x']
        elif x != dims['x']:
            print(f"Image {img_dir}/{img_file} has different dimensions!")
            return False

        if y == 0:
            y = dims['y']
        elif y != dims['y']:
            print(f"Image {img_dir}/{img_file} has different dimensions!")
            return False

        if dims['c'] > 1:
            print(f"Image {img_dir}/{img_file} has more than one channel!")
            return False

        files.append(img_file)
        c += 1

    img = Image(img_name, x, y, z, c, t)
    for i, file in enumerate(files):
        name = pathlib.Path(file).stem
        channel_index = channel_order[name] - 1
        img.add_channel(name=name)
        img.add_plane(c=channel_index)
        img.add_tiff(file, c=channel_index)

    write_companion(img, img_name, out_dir)
    return True


if len(sys.argv) < 4:
    print("Usage: python companions.py IMAGE_ROOT_DIR CHANNEL_MAPPING.csv .")
    print("(Directory layout is supposed to be: IMAGE_ROOT_DIR/IMAGE_NAME/CHANNEL_NAME.tif")
    exit(1)

sample_dir = pathlib.Path(sys.argv[1])
channel_order = get_channel_order(pathlib.Path(sys.argv[2]))
out_dir = pathlib.Path(sys.argv[3])

for img_dir in sample_dir.iterdir():
    if not img_dir.is_dir():
        continue
    try:
        success = process_img_dir(img_dir)
        if not success:
            print(f"Skipped {img_dir} due to errors.")
    except Exception as e:
        print(f"{e}")
        print(f"Skipped {img_dir} due to errors.")

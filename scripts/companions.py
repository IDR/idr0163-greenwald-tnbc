import pathlib
import sys
import subprocess
from ome_model.experimental import Image, create_companion
from tifffile import tifffile


def get_dimensions(img_file, order="xyczt"):
    img = tifffile.imread(img_file)
    res = dict()
    for i, d in enumerate(order):
        if i < len(img.shape):
            res[d] = img.shape[i]
        else:
            res[d] = 1
    return res


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


sample_dir = pathlib.Path(sys.argv[1])
for img_dir in sample_dir.iterdir():
    if not img_dir.is_dir():
        continue
    x = 0
    y = 0
    z = 1
    c = 0
    t = 1
    files = []
    for img_file in img_dir.iterdir():
        if not img_file.is_file():
            continue
        dims = get_dimensions(img_file)
        img_name = img_dir.stem
        img_file = f"{img_file.parent.name}/{img_file.name}"
        if x == 0:
            x = dims['x']
        elif x != dims['x']:
            print(f"Image {img_dir}/{img_file} has different dimensions!")
            break

        if y == 0:
            y = dims['y']
        elif y != dims['y']:
            print(f"Image {img_dir}/{img_file} has different dimensions!")
            break

        if dims['c'] > 1:
            print(f"Image {img_dir}/{img_file} has more than one channel!")
            break

        files.append(img_file)
        c += 1

    img = Image(img_name, x, y, z, c, t)
    for i, file in enumerate(files):
        img.add_channel()
        img.add_plane(c=i)
        img.add_tiff(file, c=i)

    write_companion(img, img_name, sample_dir)

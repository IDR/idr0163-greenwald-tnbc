import csv
import omero
import omero.cli
from omero.gateway import BlitzGateway


PROJECT_NAME = "idr0163-greenwald-tnbc/experimentA"


def load_images(conn):
    project = conn.getObject("Project", attributes={"name": PROJECT_NAME})
    images = dict()
    for dataset in project.listChildren():
        for image in dataset.listChildren():
            yield image


def delete_rois(conn, image):
    result = conn.getRoiService().findByImage(image.id, None)
    roi_ids = [x.getId().getValue() for x in result.rois]
    if roi_ids:
        conn.deleteObjects("Roi", roi_ids, deleteChildren=True, wait=True)
        print(f"Deleted {len(roi_ids)} ROIs.")


def main():
    with omero.cli.cli_login() as c:
        conn = BlitzGateway(client_obj=c.get_client())
        for image in load_images(conn):
            delete_rois(conn, image)


if __name__ == "__main__":
    main()

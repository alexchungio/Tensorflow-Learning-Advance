#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @ File convert_coco_pascal_tfrecord.py
# @ Description :
# @ Author alexchung
# @ Time 10/12/2019 PM 17:05

import os
import glob
import numpy as np
import json
from collections import defaultdict
import tensorflow  as tf
import defusedxml.cElementTree as ET
import cv2 as cv

from Util.tools import view_bar, makedir

# original_dataset_dir = 'F:/datasets/Pascal VOC 2012/VOCdevkit/VOC2012'

pascal_dataset_dir = '/home/alex/Documents/dataset/Pascal_VOC_2012/VOCtrainval/VOCdevkit_test'
pascal_tfrecord_dir = os.path.join(pascal_dataset_dir, 'tfrecords')

coco_dataset_dir = '/home/alex/Documents/dataset/COCO_2017/new_sub_coco'
coco_tfrecord_dir = os.path.join(coco_dataset_dir, 'tfrecords')

NAME_LABEL_MAP = {
        'back_ground': 0,
        'aeroplane': 1,
        'bicycle': 2,
        'bird': 3,
        'boat': 4,
        'bottle': 5,
        'bus': 6,
        'car': 7,
        'cat': 8,
        'chair': 9,
        'cow': 10,
        'diningtable': 11,
        'dog': 12,
        'horse': 13,
        'motorbike': 14,
        'person': 15,
        'pottedplant': 16,
        'sheep': 17,
        'sofa': 18,
        'train': 19,
        'tvmonitor': 20
    }


tf.app.flags.DEFINE_string('dataset_dir', pascal_dataset_dir, 'Voc dir')
tf.app.flags.DEFINE_string('xml_dir', 'Annotations', 'xml dir')
tf.app.flags.DEFINE_string('image_dir', 'JPEGImages', 'image dir')
tf.app.flags.DEFINE_string('save_dir', pascal_tfrecord_dir, 'save directory')
tf.app.flags.DEFINE_string('save_name', 'train', 'save name')
tf.app.flags.DEFINE_string('img_format', '.jpg', 'format of image')


FLAGS = tf.app.flags.FLAGS


# ------------------------------------------convert pascal to tfrecord-----------------------------------------------
def convert_pascal_to_tfrecord(image_path, xml_path, save_path):
    """
    convert pascal dataset to rfrecord
    :param img_dir:
    :param annotation_dir:
    :return: None
    """
    makedir(save_path)
    record_path = os.path.join(save_path, FLAGS.save_name+'.record')
    write = tf.io.TFRecordWriter(record_path)

    num_samples = 0
    sample_xml = glob.glob(os.path.join(xml_path, '*.xml'))
    for n, xml in enumerate(sample_xml):
        img_name = os.path.basename(xml).split('.')[0] + FLAGS.img_format
        img_path = os.path.join(image_path, img_name)
        if not os.path.exists(img_path):
            print('{} is not exist!'.format(img_path))
            continue
        try:
            img_height, img_width, gtbox_label = read_xml_gtbox_and_label(xml)
            # note image channel format of opencv if rgb
            bgr_image = cv.imread(img_path)
            # BGR TO RGB
            rgb_image = cv. cvtColor(bgr_image, cv.COLOR_BGR2RGB)

            image_record = serialize_example(image=rgb_image, img_height=img_height, img_width=img_width, img_depth=3,
                                             filename=img_name, gtbox_label=gtbox_label)
            write.write(record=image_record)

            view_bar(message='\nConversion progress', num=num_samples, total=len(sample_xml))
            num_samples += 1
            num_samples += 1
        except Exception as e:
            print(e)
    write.close()
    print('There are {0} samples convert to {1}'.format(num_samples, save_path))


def read_xml_gtbox_and_label(xml_path):
    """
    read gtbox(ground truth) and label from xml
    :param xml_path: the path of voc xml
    :return: a list contains gtboxes and labels, shape is [num_of_gtboxes, 5],
           and has [xmin, ymin, xmax, ymax, label](top_left, down_right) in a per row


    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    img_width = None
    img_height = None
    box_list = []
    for child_of_root in root:
        if child_of_root.tag == 'size':
            for child_item in child_of_root:
                if child_item.tag == 'width':
                    img_width = int(np.rint(float(child_item.text)))
                if child_item.tag == 'height':
                    img_height = int(np.rint(float(child_item.text)))

        if child_of_root.tag == 'object':
            label = None
            for child_item in child_of_root:
                if child_item.tag == 'name':
                    # label = NAME_LABEL_MAP[child_item.text]
                    label=NAME_LABEL_MAP[child_item.text]
                if child_item.tag == 'bndbox':

                    for node in child_item:
                        if node.tag == 'xmin':
                            xmin = int(np.rint(float(node.text)))
                        if node.tag == 'ymin':
                            ymin = int(np.rint(float(node.text)))
                        if node.tag == 'xmax':
                            xmax = int(np.rint(float(node.text)))
                        if node.tag == 'ymax':
                            ymax = int(np.rint(float(node.text)))
                    tmp_box = [xmin, ymin, xmax, ymax]
                    # tmp_box.append()
                    assert label is not None, 'label is none, error'
                    tmp_box.append(label)
                    box_list.append(tmp_box)

    gtbox_label = np.array(box_list, dtype=np.int32)  # [x1, y1. x2, y2, label]

    # xmin, ymin, xmax, ymax, label = gtbox_label[:, 0], gtbox_label[:, 1], gtbox_label[:, 2], gtbox_label[:, 3], \
    #                                 gtbox_label[:, 4]
    # gtbox_label = np.transpose(np.stack([ymin, xmin, ymax, xmax, label], axis=0))  # [ymin, xmin, ymax, xmax, label]

    return img_height, img_width, gtbox_label


# --------------------------------------------convert coco to tfrecord------------------------------------------------
def convert_coco_to_tfrecord(src_path, save_path, raw_coco=True):
    """

    :param src_path:
    :param save_path:
    :return:
    """
    makedir(save_path)
    record_path = os.path.join(save_path, FLAGS.save_name+'.record')
    write = tf.io.TFRecordWriter(record_path)

    imgs_path = os.path.join(src_path, 'Images')
    anns_path = os.path.join(src_path, 'Annotations')

    annotation_list = glob.glob(os.path.join(anns_path, '*.json'))


    anns, cats, imgs, img_anns, cate_imgs = create_index(annotation_list[0])

    num_samples = 0
    for img_id, img_annotations in img_anns.items():

        # get gtbox_label
        gtbox_label = read_json_gtbox_label(img_annotations)

        # get image name
        if raw_coco:
            img_name = '0'*(12 - len(str(img_id))) + '{0}.jpg'.format(img_id)
        else:
            img_name = '{0}.jpg'.format(img_id)

        img_path = os.path.join(imgs_path, img_name)

        try:
            bgr_image = cv.imread(img_path)
            # BGR TO RGB
            rgb_image = cv.cvtColor(bgr_image, cv.COLOR_BGR2RGB)
            img_height = rgb_image.shape[0]
            img_width = rgb_image.shape[1]

            image_record = serialize_example(image=rgb_image, img_height=img_height, img_width=img_width,
                                             img_depth=3, filename=img_name, gtbox_label=gtbox_label)
            write.write(record=image_record)

            view_bar(message='\nConversion progress', num=num_samples, total=len(img_anns))
            num_samples += 1

        except Exception as e:
            print(e)
            continue
    write.close()
    print('There are {0} samples convert to {1}'.format(num_samples, save_path))

def create_index(json_path):
    """
    create index
    :param dataset:
    :return:
    """
    dataset = json.load(open(json_path, 'r'))
    print('creating index...')
    anns, cats, imgs = {}, {}, {}
    img_anns, cate_imgs = defaultdict(list), defaultdict(list)
    if 'annotations' in dataset:
        for ann in dataset['annotations']:
            img_anns[ann['image_id']].append(ann)
            anns[ann['id']] = ann

    if 'images' in dataset:
        for img in dataset['images']:
            imgs[img['id']] = img

    if 'categories' in dataset:
        for cat in dataset['categories']:
            cats[cat['id']] = cat

    if 'annotations' in dataset and 'categories' in dataset:
        for ann in dataset['annotations']:
            cate_imgs[ann['category_id']].append(ann['image_id'])
    print('index created!')

    return anns, cats, imgs, img_anns, cate_imgs

def read_json_gtbox_label(img_anns):
    """

    :param dataset_dict:
    :param img_id:
    :return:
    """
    # gtbox_label = np.zeros((0, 5), dtype=tf.float32)
    gtbox_label = None
    for annotation in img_anns:
        bbox = annotation['bbox']

        x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
        # (x,y, w, h) -> (x_min, y_min, x_max, y_max)
        x_min, y_min, x_max, y_max = int(np.rint(x)), int(np.rint(y)), int(np.rint(x + w)), int(np.rint(y + h))
        new_bbox = [x_min, y_min, x_max, y_max]
        label = annotation['category_id']
        new_bbox.append(label)

        new_bbox = np.expand_dims(new_bbox, axis=0)
        # convert (x, y, w, h) to (x_min, y_min, x_max, y_max)
        if gtbox_label is None:
            gtbox_label = new_bbox
        else:
            gtbox_label = np.vstack((gtbox_label, new_bbox))

    return gtbox_label

def serialize_example(image, img_height, img_width, img_depth, filename, gtbox_label):
    """
    create a tf.Example message to be written to a file
    :param label: label info
    :param image: image content
    :param filename: image name
    :return:
    """
    # create a dict mapping the feature name to the tf.Example compatible
    # image_shape = tf.image.decode_jpeg(image_string).eval().shape
    feature = {
        'image': _bytes_feature(image.tobytes()),
        'height': _int64_feature(img_height),
        'width': _int64_feature(img_width),
        'depth':_int64_feature(img_depth),
        'filename': _bytes_feature(filename.encode()),
        'gtboxes_and_label': _bytes_feature(gtbox_label.tobytes()),
        'num_objects': _int64_feature(gtbox_label.shape[0])
    }
    # create a feature message using tf.train.Example
    example_proto = tf.train.Example(features=tf.train.Features(feature=feature))
    return example_proto.SerializeToString()

def _int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))


def _bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))


if __name__ == "__main__":
    # # test xml
    # image_path = os.path.join(FLAGS.dataset_dir, FLAGS.image_dir)
    # xml_path = os.path.join(FLAGS.dataset_dir, FLAGS.xml_dir)
    # save_path = FLAGS.save_dir
    #
    # convert_pascal_to_tfrecord(image_path=image_path, xml_path=xml_path, save_path=save_path)


    # test json
    img_path = os.path.join(coco_dataset_dir, 'Images')
    ann_path = os.path.join(coco_dataset_dir, 'Annotations')

    convert_coco_to_tfrecord(src_path=coco_dataset_dir, save_path=coco_tfrecord_dir, raw_coco=False)









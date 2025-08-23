import time
import sys
import platform
from PIL import Image, ImageOps
import numpy as np
import cv2
import ctypes


def is_aarch64():
    return platform.uname()[4] == "aarch64"


def get_bbox(rect_params):
    x = rect_params.left
    y = rect_params.top
    w = rect_params.width
    h = rect_params.height
    xyxy = list(map(int, [x, y, x + w, y + h]))
    return xyxy


def label_on_box(
    frame,
    display_texts,
    x,
    y,
    font_scale=0.75,
    font_thickness=2,
    rect_color=(128, 0, 128),
    font_color=(255, 255, 255),
    margin=(5, 5),  # (x_margin, y_margin)
) -> np.ndarray:
    margin_x, margin_y = margin
    current_y = y + margin_y

    for label in display_texts[::-1]:
        (text_width, text_height), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness
        )
        rect_x1 = x + margin_x
        rect_y1 = current_y - text_height
        rect_x2 = rect_x1 + text_width
        rect_y2 = current_y

        cv2.rectangle(
            frame, (rect_x1, rect_y1), (rect_x2, rect_y2), rect_color, cv2.FILLED
        )
        cv2.putText(
            frame,
            label,
            (rect_x1, current_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            font_color,
            font_thickness,
        )
        current_y -= text_height + 4  # Add spacing between lines

    return frame


def draw_bbox(
    image,
    bbox,
    bbox_type="xyxy",
    bbox_color=(0, 0, 255),
    label=None,
    font_color=(0, 0, 255),
    rect_color=(255, 255, 255),
    margin=(0, -10),
) -> None:

    if isinstance(image, str):
        temp_image = cv2.imread(image)
        if temp_image is None:
            raise ValueError("Could not read image from path.")
    else:
        temp_image = image

    h, w = temp_image.shape[:2]
    temp_bbox = np.array(bbox, dtype=np.float32)

    if bbox_type.endswith("xyxy"):
        x_min, y_min, x_max, y_max = map(int, temp_bbox)
    elif bbox_type.endswith("xywh"):
        x_min, y_min, x_max, y_max = xywh2xyxy(temp_bbox)
    else:
        raise ValueError("Invalid bbox_type: should be 'xyxy', 'xywh', or 's_xywh'")

    cv2.rectangle(temp_image, (x_min, y_min), (x_max, y_max), bbox_color, 2)

    if label:
        if isinstance(label, str):
            label_on_box(
                temp_image,
                [label],
                x_min,
                y_min,
                font_color=font_color,
                rect_color=rect_color,
                margin=margin,
            )
        elif isinstance(label, (list, tuple)) and all(
            isinstance(l, str) for l in label
        ):
            label_on_box(
                temp_image,
                label,
                x_min,
                y_min,
                font_color=font_color,
                rect_color=rect_color,
                margin=margin,
            )
        else:
            raise TypeError("Label must be a string or list of strings.")

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

import os
import sys
import time
import argparse
import platform
from ctypes import *

from utils import is_aarch64, get_bbox, draw_bbox
from search import Base, Face, PGVectorFaceSearch

sys.path.append("/opt/nvidia/deepstream/deepstream/lib")
import pyds
import numpy as np
import cv2
from sklearn.preprocessing import normalize

CONFIG_PGIE_INFER = "engine/primary/retinaface.txt"
CONFIG_SGIE_INFER = "engine/secondary/webface.txt"
STREAMMUX_BATCH_SIZE = 1
STREAMMUX_WIDTH = 1920
STREAMMUX_HEIGHT = 1080
GPU_ID = 0
THRESHOLD = 0.7
face_search = PGVectorFaceSearch(threshold=THRESHOLD)


def decodebin_child_added(child_proxy, Object, name, user_data):
    if name.find("decodebin") != -1:
        Object.connect("child-added", decodebin_child_added, user_data)
    if name.find("nvv4l2decoder") != -1:
        Object.set_property("drop-frame-interval", 0)
        Object.set_property("num-extra-surfaces", 1)
        if is_aarch64():
            Object.set_property("enable-max-performance", 1)
        else:
            Object.set_property("cudadec-memtype", 0)
            Object.set_property("gpu-id", GPU_ID)


def cb_newpad(decodebin, pad, user_data):
    streammux_sink_pad = user_data
    caps = pad.get_current_caps()
    if not caps:
        caps = pad.query_caps()
    structure = caps.get_structure(0)
    name = structure.get_name()
    features = caps.get_features(0)
    if name.find("video") != -1:
        if features.contains("memory:NVMM"):
            if pad.link(streammux_sink_pad) != Gst.PadLinkReturn.OK:
                sys.stderr.write("ERROR: Failed to link source to streammux sink pad\n")
        else:
            sys.stderr.write("ERROR: decodebin did not pick NVIDIA decoder plugin")


def create_uridecode_bin(stream_id, uri, streammux):
    bin_name = "source-bin-%04d" % stream_id
    bin = Gst.ElementFactory.make("uridecodebin", bin_name)
    if "rtsp://" in uri:
        pyds.configure_source_for_ntp_sync(bin)
    bin.set_property("uri", uri)
    pad_name = "sink_%u" % stream_id
    streammux_sink_pad = streammux.get_request_pad(pad_name)
    bin.connect("pad-added", cb_newpad, streammux_sink_pad)
    bin.connect("child-added", decodebin_child_added, 0)
    return bin


def img_probe(pad, info, user_data):
    buf = info.get_buffer()
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
    # print('let go ')
    l_frame = batch_meta.frame_meta_list
    while l_frame:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break
        frame_index = frame_meta.batch_id

        n_frame = pyds.get_nvds_buf_surface(hash(buf), frame_index)
        frame_copy = np.array(n_frame, copy=True, dtype=np.uint8)
        frame_bgr = cv2.cvtColor(frame_copy, cv2.COLOR_RGBA2BGR)
        user_data.append({"image": frame_bgr})
        current_index = frame_meta.source_id
        l_obj = frame_meta.obj_meta_list
        while l_obj:
            try:
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            unique_component_id = obj_meta.unique_component_id
            user_meta = obj_meta.obj_user_meta_list

            user_meta = obj_meta.obj_user_meta_list
            landmarks_list = []
            x1, y1, x2, y2 = get_bbox(obj_meta.rect_params)
            user_data.append({})
            user_data[-1]["bbox"] = [x1, y1, x2, y2]
            user_data[-1]["img"] = frame_bgr
            while user_meta:
                user_meta_data = pyds.NvDsUserMeta.cast(user_meta.data)
                if (
                    user_meta_data.base_meta.meta_type
                    == pyds.NVDSINFER_TENSOR_OUTPUT_META
                ):
                    tensor_meta = pyds.NvDsInferTensorMeta.cast(
                        user_meta_data.user_meta_data
                    )
                    layer = pyds.get_nvds_LayerInfo(tensor_meta, 0)
                    layer_name = layer.layerName
                    dims = layer.dims
                    shape = [dims.d[i] for i in range(dims.numDims)]
                    emb = np.array(
                        [pyds.get_detections(layer.buffer, i) for i in range(512)]
                    )
                    emb = normalize(emb.reshape(1, -1)).flatten()
                    user_data[-1]["embedding"] = emb
                    match_distance, UserId, UserName = face_search.compare_face(emb)
                    if match_distance is not None and match_distance <= THRESHOLD:
                        label = f"{UserName} ({match_distance:.2f})"
                        user_data[-1]["existed"] = True
                        user_data[-1]["UserName"] = UserName
                        user_data[-1]["match_distance"] = match_distance
                    else:
                        label = "Not recognized"
                        user_data[-1]["existed"] = False
                    user_data[-1]["label"] = label
                    # draw_bbox(frame_bgr,[x1, y1, x2, y2], label = label)

                try:
                    user_meta = user_meta.next
                except StopIteration:
                    break
            try:
                l_obj = l_obj.next
            except StopIteration:
                break
        try:
            l_frame = l_frame.next
        except StopIteration:
            break
    return Gst.PadProbeReturn.OK


def video_probe(pad, info, video_writer):
    buf = info.get_buffer()
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(buf))
    # print('let go ')
    l_frame = batch_meta.frame_meta_list
    while l_frame:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break
        frame_index = frame_meta.batch_id
        n_frame = pyds.get_nvds_buf_surface(hash(buf), frame_index)
        frame_copy = np.array(n_frame, copy=True, dtype=np.uint8)
        frame_bgr = cv2.cvtColor(frame_copy, cv2.COLOR_RGBA2BGR)

        current_index = frame_meta.source_id
        l_obj = frame_meta.obj_meta_list
        while l_obj:
            try:
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            unique_component_id = obj_meta.unique_component_id
            user_meta = obj_meta.obj_user_meta_list

            user_meta = obj_meta.obj_user_meta_list
            landmarks_list = []
            x1, y1, x2, y2 = get_bbox(obj_meta.rect_params)
            while user_meta:
                user_meta_data = pyds.NvDsUserMeta.cast(user_meta.data)
                if (
                    user_meta_data.base_meta.meta_type
                    == pyds.NVDSINFER_TENSOR_OUTPUT_META
                ):
                    tensor_meta = pyds.NvDsInferTensorMeta.cast(
                        user_meta_data.user_meta_data
                    )
                    layer = pyds.get_nvds_LayerInfo(tensor_meta, 0)
                    layer_name = layer.layerName
                    dims = layer.dims
                    shape = [dims.d[i] for i in range(dims.numDims)]
                    emb = np.array(
                        [pyds.get_detections(layer.buffer, i) for i in range(512)]
                    )
                    emb = normalize(emb.reshape(1, -1)).flatten()
                    match_distance, UserId, UserName = face_search.compare_face(emb)
                    if match_distance is not None and match_distance <= THRESHOLD:
                        label = f"{UserName} ({match_distance:.2f})"
                    else:
                        label = "Not recognized"
                    draw_bbox(frame_bgr, [x1, y1, x2, y2], label=label)
                try:
                    user_meta = user_meta.next
                except StopIteration:
                    break
            try:
                l_obj = l_obj.next
            except StopIteration:
                break

        video_writer.write(frame_bgr)
        try:
            l_frame = l_frame.next
        except StopIteration:
            break
    return Gst.PadProbeReturn.OK


Gst.init(None)


class DeepStreamInference:
    def __init__(
        self,
        config_pgie=CONFIG_PGIE_INFER,
        config_sgie=CONFIG_SGIE_INFER,
        gpu_id=GPU_ID,
        streammux_width=STREAMMUX_WIDTH,
        streammux_height=STREAMMUX_HEIGHT,
    ):
        self.config_pgie = config_pgie
        self.config_sgie = config_sgie
        self.gpu_id = gpu_id
        self.streammux_width = streammux_width
        self.streammux_height = streammux_height

        self.pipeline = None
        self.loop = None
        self.video_writer = None
        self.video_fps = 30
        self.video_size = (self.streammux_width, self.streammux_height)
        self.embedding_holder = []

    def _make_element(self, factory, name):
        elem = Gst.ElementFactory.make(factory, name)
        if not elem:
            sys.stderr.write(f"ERROR: Failed to create element '{factory}'\n")
            sys.exit(1)
        return elem

    def _set_gpu_mem(self, elem):
        if not is_aarch64():
            elem.set_property("nvbuf-memory-type", int(pyds.NVBUF_MEM_CUDA_UNIFIED))
            elem.set_property("gpu_id", self.gpu_id)

    def _bus_call(self, bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write(f"Error: {err}, Debug: {debug}\n")
            loop.quit()
        return True

    def _add_probe(self, elem, probe_func, infer_type):
        src_pad = elem.get_static_pad("src")
        if not src_pad:
            sys.stderr.write("ERROR: Failed to get src pad for probe\n")
            sys.exit(1)
        if infer_type == "image":
            self.embedding_holder.clear()
            src_pad.add_probe(
                Gst.PadProbeType.BUFFER, probe_func, self.embedding_holder
            )
        elif infer_type == "video":
            if self.video_writer is None:
                # fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                fourcc = cv2.VideoWriter_fourcc(*"avc1")
                self.video_writer = cv2.VideoWriter(
                    self.output_path, fourcc, self.video_fps, self.video_size
                )
            src_pad.add_probe(Gst.PadProbeType.BUFFER, probe_func, self.video_writer)

    def _create_streammux(self, batch_size=1, live_source=0):
        streammux = self._make_element("nvstreammux", "stream-muxer")
        streammux.set_property("batch-size", batch_size)
        streammux.set_property("gpu_id", self.gpu_id)
        streammux.set_property("width", self.streammux_width)
        streammux.set_property("height", self.streammux_height)
        streammux.set_property("batched-push-timeout", 25000)
        streammux.set_property("live-source", live_source)
        streammux.set_property("enable-padding", 1)
        streammux.set_property("attach-sys-ts", 1)
        return streammux

    def run_video(self, uri, output_path):
        self.output_path = output_path
        """Run inference on video / RTSP stream"""
        self.pipeline = Gst.Pipeline()

        streammux = self._create_streammux(
            batch_size=1, live_source=0 if "file://" in uri else 1
        )
        source_bin = create_uridecode_bin(0, uri, streammux)

        pgie = self._make_element("nvinfer", "pgie")
        sgie = self._make_element("nvinfer", "sgie")
        converter = self._make_element("nvvideoconvert", "nvvideoconvert")
        capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
        caps = Gst.Caps.from_string(f"video/x-raw(memory:NVMM), format=RGBA")
        capsfilter.set_property("caps", caps)

        # osd = self._make_element("nvdsosd", "nvdsosd")
        sink = self._make_element("fakesink", "fakesink")

        pgie.set_property("config-file-path", self.config_pgie)
        pgie.set_property("qos", 0)
        sgie.set_property("config-file-path", self.config_sgie)
        sgie.set_property("qos", 0)
        if not is_aarch64():
            self._set_gpu_mem(streammux)
            pgie.set_property("gpu_id", GPU_ID)
            self._set_gpu_mem(converter)
        converter.set_property("qos", 0)
        # self._set_gpu_mem(osd)
        sink.set_property("async", 0)
        sink.set_property("sync", 0)
        sink.set_property("qos", 0)
        self.pipeline.add(
            source_bin, streammux, pgie, sgie, converter, capsfilter, sink
        )
        streammux.link(pgie)
        pgie.link(sgie)
        sgie.link(converter)
        # converter.link(osd)
        converter.link(capsfilter)
        capsfilter.link(sink)
        # osd.link(sink)

        self._add_probe(capsfilter, video_probe, "video")

        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_call, self.loop)

        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.loop.run()
        except:
            pass
        self.pipeline.set_state(Gst.State.NULL)
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
        return

    def run_image(self, image_path):
        """Run inference on single image"""
        if not os.path.isfile(image_path):
            sys.stderr.write(f"ERROR: Image file not found: {image_path}\n")
            return []

        self.pipeline = Gst.Pipeline()

        filesrc = self._make_element("filesrc", "file-source")
        jpegparser = self._make_element("jpegparse", "jpeg-parser")
        decoder = self._make_element("nvv4l2decoder", "nvv4l2-decoder")
        nvvideoconvert_1 = self._make_element("nvvideoconvert", "convertor_1")
        capsfilter_1 = self._make_element("capsfilter", "capsfilter_1")

        streammux = self._create_streammux(batch_size=1, live_source=1)

        pgie = self._make_element("nvinfer", "pgie")
        nvvideoconvert_2 = self._make_element("nvvideoconvert", "convertor_2")
        capsfilter_2 = self._make_element("capsfilter", "capsfilter_2")
        sgie = self._make_element("nvinfer", "sgie")
        sink = self._make_element("fakesink", "fakesink")

        # Set props
        filesrc.set_property("location", image_path)
        pgie.set_property("config-file-path", self.config_pgie)
        sgie.set_property("config-file-path", self.config_sgie)

        caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=RGBA")
        capsfilter_1.set_property("caps", caps)
        capsfilter_2.set_property("caps", caps)

        self._set_gpu_mem(nvvideoconvert_1)
        self._set_gpu_mem(nvvideoconvert_2)

        # Add and link
        for elem in [
            filesrc,
            jpegparser,
            decoder,
            nvvideoconvert_1,
            capsfilter_1,
            streammux,
            pgie,
            nvvideoconvert_2,
            capsfilter_2,
            sgie,
            sink,
        ]:
            self.pipeline.add(elem)

        filesrc.link(jpegparser)
        jpegparser.link(decoder)
        decoder.link(nvvideoconvert_1)
        nvvideoconvert_1.link(capsfilter_1)
        capsfilter_1.get_static_pad("src").link(streammux.get_request_pad("sink_0"))
        streammux.link(pgie)
        pgie.link(nvvideoconvert_2)
        nvvideoconvert_2.link(capsfilter_2)
        capsfilter_2.link(sgie)
        sgie.link(sink)

        self._add_probe(sgie, img_probe, "image")

        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._bus_call, self.loop)

        self.pipeline.set_state(Gst.State.PLAYING)
        try:
            self.loop.run()
        except:
            pass
        self.pipeline.set_state(Gst.State.NULL)
        image_cv = self.embedding_holder.pop(0)["image"]
        return image_cv, self.embedding_holder

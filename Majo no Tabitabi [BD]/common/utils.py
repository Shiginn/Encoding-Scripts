__all__ = ["BDMV", "get_encoder"]

import os
from typing import List, Sequence

import vapoursynth as vs
from vardautomation import JAPANESE, X265, Chapter, FileInfo, OpusEncoder

from .encode import Encoder
from .parse_bd import ParseBD


BDMV = ParseBD(
    bdmv_folder=os.path.join(os.path.dirname(__file__), "../BDMV"),
    bd_volumes=[f"Wandering Witch - The Journey of Elaina Volume {i}" for i in range(1, 3)]
    # bd_volumes=[
    #     "Wandering Witch - The Journey of Elaina Volume 1",
    #     "Wandering Witch - The Journey of Elaina Volume 2"
    # ]
)


def get_encoder(
    file: FileInfo, clip: vs.VideoNode, ep_num: int | str,
    chapters: List[int] | List[Chapter] | None = None,
    chapters_names: Sequence[str | None] | None = None,
) -> Encoder:
    file.set_name_clip_output_ext(".hevc")

    enc = Encoder(file, clip, ep_num, chapters, chapters_names)
    enc.video_encoder(X265, settings="common/x265_settings")

    if chapters and chapters_names:
        enc.make_chapters()

    enc.audio_encoder(tracks=1, encoder=OpusEncoder)
    enc.muxer(f"{enc.v_encoder.__class__.__name__.lower()} BD by Shigin", "Opus 2.0", JAPANESE)

    return enc

__all__ = ["BDMV", "NCOP", "NCED", "get_encoder"]

import os
from typing import List, Sequence

import vapoursynth as vs
from vardautomation import JAPANESE, X265, Chapter, FileInfo, OpusEncoder, PresetBD

from .encode import Encoder
from .parse_bd import ParseBD


BDMV = ParseBD(
    os.path.join(os.path.dirname(__file__), "../BDMV")
)

NCOP = FileInfo(
    BDMV.bdmv_folder / "Wandering Witch - The Journey of Elaina Volume 1/BDMV/STREAM/00007.m2ts",
    trims_or_dfs=(24, -24), preset=[PresetBD]
)

NCED = FileInfo(
    BDMV.bdmv_folder / "Wandering Witch - The Journey of Elaina Volume 1/BDMV/STREAM/00016.m2ts",
    trims_or_dfs=(24, -24), preset=[PresetBD]
)


def get_encoder(
    file: FileInfo, clip: vs.VideoNode, ep_num: int | str,
    chapters: List[int] | List[Chapter] | None = None,
    chapters_names: Sequence[str | None] | None = None,
) -> Encoder:
    file.set_name_clip_output_ext(".hevc")

    enc = Encoder(file, clip, ep_num, chapters, chapters_names)
    enc.video_encoder(X265, settings="common/x265_settings", resumable=True)

    if chapters and chapters_names:
        enc.make_chapters()

    enc.audio_encoder(tracks=1, encoder=OpusEncoder)
    enc.muxer(f"{enc.v_encoder.__class__.__name__.lower()} BD by Shigin", "Opus 2.0", JAPANESE)

    return enc

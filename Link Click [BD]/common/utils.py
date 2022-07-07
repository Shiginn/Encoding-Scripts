__all__ = [
    "BDMV",
    "JP_NCOP", "JP_NCED", "CN_OP", "CN_ED",
    "OP_RANGES", "ED_RANGES",
    "get_encoder"
]

import os
from typing import List, Sequence, Tuple, Dict, Any

import vapoursynth as vs
from vardautomation import JAPANESE, X265, Chapter, FileInfo, FileInfo2, OpusEncoder, PresetBDWAV64

from .encode import Encoder
from .parse_bd import ParseBD

core = vs.core


BDMV = ParseBD(
    os.path.join(os.path.dirname(__file__), "../BDMV"),
    ep_playlist=0
)

JP_NCOP = FileInfo(
    BDMV.bdmv_folder / "Disc - 02/BDMV/STREAM/00005.m2ts", trims_or_dfs=(24, -24), preset=[PresetBDWAV64]
)
CN_OP = FileInfo2(
    BDMV.bdmv_folder / "Disc - 06/BDMV/STREAM/00004.m2ts", trims_or_dfs=(24, -24), preset=[PresetBDWAV64]
)

# first part of the ED is never used in eps
JP_NCED = FileInfo(
    BDMV.bdmv_folder / "Disc - 02/BDMV/STREAM/00004.m2ts", trims_or_dfs=(24 + 357, -24), preset=[PresetBDWAV64]
)
CN_ED = FileInfo2(
    BDMV.bdmv_folder / "Disc - 06/BDMV/STREAM/00003.m2ts", trims_or_dfs=(24 + 357, -24), preset=[PresetBDWAV64]
)


OP_RANGES: List[Tuple[int, int]] = [
    (1174, 2685),
    (1240, 2750),
    (2663, 4174),
    (1844 - 1, 3354),   # 1st frame missing
    (4038 - 1, 5548),   # 1st frame missing
    (2860, 4359),       # excluded from avg
    (4800, 6311),
    (3088 - 1, 4600),   # 1st frame missing
    (2758 - 1, 4270),   # 1st frame missing
    (3194 - 1, 4705),   # 1st frame missing
    (2366 - 1, 3878),   # 1st frame missing
    (3640 - 1, 5151)    # 1st frame missing
]

ED_RANGES: List[Tuple[int, int]] = [
    (30890, 32690),
    (31340, 33140),
    (27889, 29690),
    (28408, 30209),
    (34478, 36278),
    (30939, 32724),
    (31299, 33095),
    (30939, 32733),
    (31854, 33654),
    (29125, 30925),
    (30454, 32254),
    (42035, 43835)
]

assert len(OP_RANGES) == len(ED_RANGES) == BDMV.episode_number


def get_encoder(
    file: FileInfo, clip: vs.VideoNode, ep_num: int | str,
    zones: Dict[Tuple[int, int], Dict[str, Any]] | None = None,
    chapters: List[int] | List[Chapter] | None = None,
    chapters_names: Sequence[str | None] | None = None,
) -> Encoder:
    file.set_name_clip_output_ext(".hevc")

    enc_zones: Dict[Tuple[int, int], Dict[str, Any]] = zones if zones is not None else dict()

    if (op_range := OP_RANGES[int(ep_num) - 1]) is not None:
        enc_zones |= {op_range: {"b": 0.90}}
    if (ed_range := ED_RANGES[int(ep_num) - 1]) is not None:
        enc_zones |= {ed_range: {"b": 0.85}}


    enc = Encoder(file, clip, str(ep_num).zfill(2), chapters, chapters_names)
    enc.video_encoder(X265, settings="common/x265_settings", resumable=False, zones=zones)

    if chapters and chapters_names:
        enc.make_chapters()

    enc.audio_encoder(tracks=[1, 2], extracter=None, cutter=None, encoder=OpusEncoder)
    enc.muxer(f"{enc.v_encoder.__class__.__name__.lower()} BD by Shigin", "Opus 2.0", JAPANESE)

    return enc

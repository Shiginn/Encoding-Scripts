import vapoursynth as vs
from vardautomation import FileInfo, MplsReader, PresetBD, PresetWEB, PresetAAC

from common import Encoder, EightySixFiltering

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "./BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO/BDMV/STREAM/00004.m2ts",
    trims_or_dfs=(None, -26),
    preset=[PresetBD, PresetAAC]
)

NCOP = FileInfo(
    "./BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO/BDMV/STREAM/00007.m2ts",
    trims_or_dfs=(7, None),  # 2177 frames
    preset=[PresetBD]
)

NCED = FileInfo(
    "./BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO/BDMV/STREAM/00010.m2ts",
    trims_or_dfs=(48, -72),  # 2085 frames
    preset=[PresetBD, PresetAAC]
)

WEB = FileInfo(
    f"./WEB/86 - Eighty Six - S01 - FRENCH 1080p WEB x264 -NanDesuKa (CR)/86 - Eighty Six - S01E{EP_NUM} - FRENCH 1080p WEB x264 -NanDesuKa (CR).mkv",
    trims_or_dfs=(None, None),
    preset=[PresetWEB, PresetAAC]
)

JP_BD.ep_num = EP_NUM

CHAPTERS = MplsReader("./BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO").get_playlist()[1].mpls_chapters[int(EP_NUM)-6].to_chapters()
CHAPTERS_NAMES = ["Intro", "OP", "Partie A", "Partie B", "ED", "Epilogue", "Preview"]

op_start = 1327
op_offset = 28
ed_start = 31193
ed_offset = 1
title_ranges = [(16400, 16471), (33926, 34045)]


class Filtering(EightySixFiltering):
    pass


flt = Filtering(JP_BD, NCOP, NCED, op_start, op_offset, ed_start, ed_offset, title_ranges)
filtered = flt.filter()


if __name__ == "__main__":
    Encoder(JP_BD, WEB, filtered, CHAPTERS, CHAPTERS_NAMES).run()

elif __name__ == "__vapoursynth__":
    filtered.set_output()

else:
    outputs = []

    if not len(outputs):
        flt.filtersteps()
    else:
        for i in range(len(outputs)):
            outputs[i].set_output(i)

import vapoursynth as vs
from vardautomation import FileInfo, MplsReader, PresetBD, PresetWEB, PresetAAC

from common import Encoder, EightySixFiltering

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "./BDMV/[BDMV] 86 Eighty-Six Volume 2/BD_VIDEO/BDMV/STREAM/00005.m2ts",
    trims_or_dfs=(None, -27),
    preset=[PresetBD, PresetAAC]
)

NCOP = FileInfo(
    "./BDMV/[BDMV] 86 Eighty-Six Volume 2/BD_VIDEO/BDMV/STREAM/00006.m2ts",
    trims_or_dfs=(7, None),  # 2177 frames
    preset=[PresetBD]
)

NCED = FileInfo(
    "./BDMV/[BDMV] 86 Eighty-Six Volume 2/BD_VIDEO/BDMV/STREAM/00009.m2ts",
    trims_or_dfs=(1478, -24),  # 1312 frames
    preset=[PresetBD, PresetAAC]
)

WEB = FileInfo(
    f"./WEB/86 - Eighty Six - S01 - FRENCH 1080p WEB x264 -NanDesuKa (CR)/86 - Eighty Six - S01E{EP_NUM} - FRENCH 1080p WEB x264 -NanDesuKa (CR).mkv",
    trims_or_dfs=(None, None),
    preset=[PresetWEB, PresetAAC]
)

JP_BD.ep_num = EP_NUM

CHAPTERS = MplsReader("./BDMV/[BDMV] 86 Eighty-Six Volume 2/BD_VIDEO").get_playlist()[1].mpls_chapters[int(EP_NUM)-3].to_chapters()
CHAPTERS_NAMES = ["Intro", "OP", "Partie A", "Partie B", "ED", "Epilogue", "Preview"]

op_start = 6889
op_offset = 29
ed_start = 32085
ed_offset = 1
title_ranges = [(19400, 19467), (33925, 34044)]


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

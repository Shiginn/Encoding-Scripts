import vapoursynth as vs
from vardautomation import FileInfo, VPath, MplsReader, PresetBD, PresetAAC

from common import Encoder, EightySixFiltering

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 1/BD_VIDEO/BDMV/STREAM/00004.m2ts",
    trims_or_dfs=(None, -25),
    preset=[PresetBD, PresetAAC]
)

NCOP = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 1/BD_VIDEO/BDMV/STREAM/00006.m2ts",
    trims_or_dfs=(7, None), #2177 frames
    preset=[PresetBD]
)

NCED = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 1/BD_VIDEO/BDMV/STREAM/00007.m2ts",
    trims_or_dfs=(48, None),
    preset=[PresetBD, PresetAAC]
)

JP_BD.ep_num = EP_NUM

CHAPTERS = MplsReader("../../BDMV/[BDMV] 86 Eighty-Six Volume 1/BD_VIDEO").get_playlist()[1].mpls_chapters[int(EP_NUM)-1].to_chapters()
CHAPTERS_NAMES = ["Intro", "OP", "Partie A", "Partie B", "ED", "Epilogue", "Preview"]

op_start = 559
op_offset = 27
ed_start = 25679
ed_offset = 73
title_ranges = [(16165, 16232), (33927, 34046)]


class Filtering(EightySixFiltering):
    pass


flt = Filtering(JP_BD, NCOP, NCED, op_start, op_offset, ed_start, ed_offset, title_ranges)
filtered = flt.filter()


if __name__ == "__main__": 
    Encoder(JP_BD, filtered, CHAPTERS, CHAPTERS_NAMES).run()

elif __name__ == "__vapoursynth__":
    filtered.set_output()

else:
    outputs = []
    
    if not len(outputs):
        flt.filtersteps()
    else:
        for i in range(len(outputs)):
            outputs[i].set_output(i)
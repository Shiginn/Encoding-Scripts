import vapoursynth as vs
from vardautomation import FileInfo, MplsReader, PresetBD, PresetAAC

from common import Encoder, EightySixFiltering

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO/BDMV/STREAM/00004.m2ts",
    trims_or_dfs=(None, -26),
    preset=[PresetBD, PresetAAC]
)

NCOP = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO/BDMV/STREAM/00007.m2ts",
    trims_or_dfs=(7, None), #2177 frames
    preset=[PresetBD]
)

NCED = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO/BDMV/STREAM/00010.m2ts",
    trims_or_dfs=(48, -72), #2085 frames
    preset=[PresetBD, PresetAAC]
)

JP_BD.ep_num = EP_NUM

CHAPTERS = MplsReader("../../BDMV/[BDMV] 86 Eighty-Six Volume 3/BD_VIDEO").get_playlist()[1].mpls_chapters[int(EP_NUM)-6].to_chapters()
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
    Encoder(JP_BD, filtered, CHAPTERS, CHAPTERS_NAMES).run()

elif __name__ == "__vapoursynth__":
    filtered.set_output()

else:

    import vardefunc as vdf
    from vsutil import depth

    op_ranges = (op_start, op_start + NCOP.clip_cut.num_frames - op_offset)

    op_start, op_end = op_ranges

    src = depth(JP_BD.clip_cut, 8)

    credit_mask = vdf.mask.Difference().creditless(
        src,
        src[op_start:op_end+1],
        NCOP.clip_cut[:-op_offset],
        op_start,
        thr=150,
        prefilter=True
    )







    outputs = []
    # import lvsfunc as lvf
    # outputs = [lvf.diff(JP_BD.clip_cut[op_start:op_start+NCOP.clip_cut.num_frames-op_offset], NCOP.clip_cut)]
    
    if not len(outputs):
        flt.filtersteps()
    else:
        for i in range(len(outputs)):
            outputs[i].set_output(i)
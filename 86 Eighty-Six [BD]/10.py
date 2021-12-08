import vapoursynth as vs
from vardautomation import FileInfo, MplsReader, PresetBD, PresetAAC

from common import Encoder, EightySixFiltering

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "../../BDMV/[BDMV] EIGHTY-SIX 4/BDMV/STREAM/00004.m2ts",
    trims_or_dfs=(None, -27),
    preset=[PresetBD, PresetAAC]
)

NCOP = FileInfo(
    "../../BDMV/[BDMV] EIGHTY-SIX 4/BDMV/STREAM/00007.m2ts",
    trims_or_dfs=(7, None), #2177 frames
    preset=[PresetBD]
) 

NCED = FileInfo(
    "../../BDMV/[BDMV] EIGHTY-SIX 4/BDMV/STREAM/00010.m2ts",
    trims_or_dfs=(43, -198), #2010 frames
    preset=[PresetBD, PresetAAC]
)

JP_BD.ep_num = EP_NUM

CHAPTERS = MplsReader("../../BDMV/[BDMV] EIGHTY-SIX 4").get_playlist()[1].mpls_chapters[int(EP_NUM)-9].to_chapters()
CHAPTERS_NAMES = ["Intro", "OP", "Partie A", "Partie B", "ED", "Preview"]

op_start = 3220
op_offset = 27
ed_start = 21767
ed_offset = 1
title_ranges = [(23883, 23950), (33925, 34044)]


class Filtering(EightySixFiltering):
    def filter_ed(self, clip: vs.VideoNode, NCED: FileInfo) -> vs.VideoNode:
        import vardefunc as vdf
        from vsutil import depth

        src = depth(self.JP_BD.clip_cut, 8)

        ed_start, ed_end = self.ed_ranges

        credit_mask = vdf.mask.Difference().creditless(
            src,
            src[ed_start:ed_end+1],
            NCED.clip_cut[:-self.ed_offset],
            ed_start,
            thr=75,
            prefilter=True
        )
        credit_mask = depth(credit_mask, 16)

        return core.std.MaskedMerge(clip, self.JP_BD.clip_cut, credit_mask)


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
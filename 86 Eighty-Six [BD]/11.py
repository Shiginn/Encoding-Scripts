import vapoursynth as vs
from vardautomation import FileInfo, MplsReader, PresetBD, PresetWEB, PresetAAC

from common import Encoder, EightySixFiltering

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "./BDMV/[BDMV] EIGHTY-SIX 4/BDMV/STREAM/00005.m2ts",
    trims_or_dfs=(None, -25),
    preset=[PresetBD, PresetAAC]
)

NCOP = FileInfo(
    "./BDMV/[BDMV] EIGHTY-SIX 4/BDMV/STREAM/00008.m2ts",
    trims_or_dfs=(7, None),  # 2177 frames
    preset=[PresetBD]
)

NCED = FileInfo(
    "./BDMV/[BDMV] EIGHTY-SIX 4/BDMV/STREAM/00011.m2ts",
    trims_or_dfs=(2563, -1335),  # 2139 frames
    preset=[PresetBD, PresetAAC]
)

WEB = FileInfo(
    f"./WEB/86 - Eighty Six - S01 - FRENCH 1080p WEB x264 -NanDesuKa (CR)/86 - Eighty Six - S01E{EP_NUM} - FRENCH 1080p WEB x264 -NanDesuKa (CR).mkv",
    trims_or_dfs=(None, None),
    preset=[PresetWEB, PresetAAC]
)

JP_BD.ep_num = EP_NUM

CHAPTERS = MplsReader("./BDMV/[BDMV] EIGHTY-SIX 4").get_playlist()[1].mpls_chapters[int(EP_NUM)-9].to_chapters()
CHAPTERS_NAMES = ["Intro", "OP", "Partie A", "Partie B", "ED"]

op_start = 1063
op_offset = 28
ed_start = 30477
ed_offset = 1
title_ranges = [(20504, 20571)]


class Filtering(EightySixFiltering):
    def filter_ed(self, clip: vs.VideoNode, denoise: vs.VideoNode, NCED: FileInfo) -> vs.VideoNode:
        import vardefunc as vdf
        from vsutil import depth

        ed_start, ed_end = self.ed_ranges

        credit_mask = vdf.mask.Difference().creditless(
            self.JP_BD.clip_cut,
            self.JP_BD.clip_cut[ed_start:ed_end+1],
            NCED.clip_cut[:-self.ed_offset],
            ed_start,
            thr=75,
            prefilter=True
        )
        credit_mask = depth(credit_mask, 16)

        return core.std.MaskedMerge(clip, denoise, credit_mask)


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

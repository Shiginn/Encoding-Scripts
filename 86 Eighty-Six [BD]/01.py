import vapoursynth as vs
from vardautomation import FileInfo, MplsReader, PresetBD, PresetAAC

from common import Encoder, EightySixFiltering

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 1/BD_VIDEO/BDMV/STREAM/00003.m2ts",
    trims_or_dfs=(None, -26),
    preset=[PresetBD, PresetAAC]
)

NCOP = FileInfo(
    "../../BDMV/[BDMV] 86 Eighty-Six Volume 1/BD_VIDEO/BDMV/STREAM/00006.m2ts",
    trims_or_dfs=(7, None), #2177 frames
    preset=[PresetBD]
)

NCED = None

JP_BD.ep_num = EP_NUM

CHAPTERS = MplsReader("../../BDMV/[BDMV] 86 Eighty-Six Volume 1/BD_VIDEO").get_playlist()[1].mpls_chapters[int(EP_NUM)-1].to_chapters()
CHAPTERS_NAMES = ["Intro", "Partie A", "Partie B", "OP", "Preview"]

op_start = 31769
op_offset = 20
ed_start = None
ed_offset = -1
title_ranges = [(16165, 16232), (33927, 34045)]


class Filtering(EightySixFiltering):
    def scenefilter(self, clip: vs.VideoNode) -> vs.VideoNode:
        # Filtering blurs the scanlines added on the TVs. 
        # Masking is done to preserve these.

        import lvsfunc as lvf

        screen_ranges = [(3317, 3802), (3803, 3880), (7478, 7609)]

        detail_mask = lvf.mask.detail_mask(JP_BD.clip_cut, rad=1, brz_a=0.2, brz_b=0.07)
        detail_mask_2 = lvf.mask.detail_mask(JP_BD.clip_cut, rad=1, brz_a=0.2, brz_b=0.07, sigma=0.8).std.Maximum()

        details = core.std.Expr([detail_mask, detail_mask_2], expr="x y -").std.Binarize(5<<8).std.Minimum().std.Maximum().std.Maximum().std.Maximum()
        details = lvf.rfs(core.std.BlankClip(details), details, screen_ranges)

        scene_filter = core.std.MaskedMerge(clip, self.denoise_clip, details)

        return scene_filter


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
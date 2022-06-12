import vapoursynth as vs

from common import ElainaFiltering, get_encoder, BDMV

core = vs.core

EP_NUM = __file__[-5:-3]

JPBD = BDMV.get_episode(EP_NUM)
CHAPTERS = BDMV.get_chapter(EP_NUM)
CHAPTERS_NAMES = ["Intro", "OP", "Partie A", "Partie B", "ED"]


class Filtering(ElainaFiltering):
    OP_RANGES = (864, 3020)
    ED_RANGES = (31888, 34045)

    def prefilter(self, bd: vs.VideoNode) -> vs.VideoNode:
        import lvsfunc as lvf

        web = core.ffms2.Source("WEB/[SubsPlease] Majo no Tabitabi - 02v2 (1080p) [C80BFA61].mkv")[240:]

        # Undoing a Saya face redraw — https://slow.pics/c/zFGJBtNc
        sqmask = lvf.mask.BoundingBox((1397, 370), (86, 74)).get_mask(bd).bilateral.Gaussian(sigma=10)
        fixed = lvf.rfs(bd, bd.std.MaskedMerge(web, sqmask), [(21248, 21310)])

        # Another face redraw undo — https://slow.pics/c/QoxjoSeB
        sqmask = lvf.mask.BoundingBox((1310, 356), (94, 80)).get_mask(bd).bilateral.Gaussian(sigma=10)
        fixed = lvf.rfs(fixed, fixed.std.MaskedMerge(web, sqmask), [(21447, 21493)])

        # Very minor line fuck-up
        sqmask = lvf.mask.BoundingBox((1320, 478), (8, 14)).get_mask(bd)
        fixed = lvf.rfs(fixed, fixed.std.MaskedMerge(web, sqmask), [(21452, 21454)])

        return fixed


flt = Filtering(JPBD)
filtered = flt.filterchain()


if __name__ == "__main__":
    enc = get_encoder(JPBD, filtered, EP_NUM, CHAPTERS, CHAPTERS_NAMES)
    enc.run()
    enc.clean_up()

    enc.generate_keyframes()

elif __name__ == "__vapoursynth__":
    filtered.set_output()

else:
    flt.filtersteps()

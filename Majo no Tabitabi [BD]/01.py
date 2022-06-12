import vapoursynth as vs

from common import ElainaFiltering, get_encoder, BDMV

core = vs.core

EP_NUM = __file__[-5:-3]

JPBD = BDMV.get_episode(EP_NUM)
CHAPTERS = BDMV.get_chapter(EP_NUM)
CHAPTERS_NAMES = ["Intro", "Partie A", "Partie B", "Outro"]


class Filtering(ElainaFiltering):
    def prefilter(self, bd: vs.VideoNode) -> vs.VideoNode:
        import lvsfunc as lvf

        web = core.ffms2.Source("WEB/[SubsPlease] Majo no Tabitabi - 01v2 (1080p) [C70DFF8B].mkv")[240:]

        # Fix mouth misplacement introduced on BDs — https://slow.pics/c/NE6vqUdq
        sqmask = lvf.mask.BoundingBox((1084, 663), (225, 200)).get_mask(bd).bilateral.Gaussian(sigma=10)
        fixed = lvf.rfs(bd, bd.std.MaskedMerge(web, sqmask), [(1226, 1227)])

        # Fix bit of rope they deleted on the BDs — https://slow.pics/c/JdVX7Chb
        sqmask = lvf.mask.BoundingBox((1841, 458), (67, 17)).get_mask(fixed)
        fixed = lvf.rfs(fixed, fixed.std.MaskedMerge(web, sqmask), [(3330, 3365)])

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

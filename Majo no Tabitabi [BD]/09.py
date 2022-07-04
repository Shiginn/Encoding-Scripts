import vapoursynth as vs

from common import ElainaFiltering, get_encoder, BDMV

core = vs.core

EP_NUM = __file__[-5:-3]

JPBD = BDMV.get_episode(EP_NUM)
CHAPTERS = BDMV.get_chapter(EP_NUM)
CHAPTERS_NAMES = ["Intro", "Partie A", "Partie B", "ED"]


class Filtering(ElainaFiltering):
    OP_RANGES = (1043, 1175)
    ED_RANGES = (31914, 34046)

    NCOP = core.std.BlankClip(JPBD.clip_cut, color=[235, 128, 128])
    NCED = core.std.BlankClip(JPBD.clip_cut, color=[16, 128, 128])


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

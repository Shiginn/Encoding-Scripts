import vapoursynth as vs

from common import ElainaFiltering, get_encoder, BDMV

core = vs.core

EP_NUM = __file__[-5:-3]

JPBD = BDMV.get_episode(EP_NUM)
CHAPTERS = BDMV.get_chapter(EP_NUM)[:-1]
CHAPTERS_NAMES = ["Intro", "Partie A", "Partie B", "Epilogue"]


class Filtering(ElainaFiltering):
    OP_RANGES = None
    ED_RANGES = None


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

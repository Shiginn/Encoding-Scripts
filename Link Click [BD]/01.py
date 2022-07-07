from vardautomation import FileInfo2, PresetBDWAV64, PresetOpus

from common import BDMV, LinkClickFiltering, get_encoder

EP_NUM = __file__[-5:-3]


# SOURCES
JPBD = FileInfo2(BDMV.episodes[int(EP_NUM) - 1], trims_or_dfs=(24, -24), preset=[PresetBDWAV64, PresetOpus])

filterchain = LinkClickFiltering(JPBD, EP_NUM)
filtered = filterchain.filter()


if __name__ == "__main__":
    # JPBD.trims_or_dfs = (224, 1224)
    # filtered = filtered[200:1200]

    enc = get_encoder(JPBD, filtered, EP_NUM)

    enc.run()
    enc.make_comp()
    enc.clean_up(ignore_file=[JPBD.a_enc_cut.set_track(i) for i in (1, 2) if JPBD.a_enc_cut is not None])

elif __name__ == "__vapoursynth__":
    filtered.set_output()

else:
    filterchain.preview()
    # JPBD.clip_cut[30890:32690 + 1].std.PlaneStats().set_output()

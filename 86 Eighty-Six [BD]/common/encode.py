import vapoursynth as vs
import kagefunc as kgf
from vsutil import depth
from vardautomation import (
    FileInfo, VPath,
    X265, FFmpegAudioExtracter, EztrimCutter, QAACEncoder, BitrateMode,
    Chapter, MatroskaXMLChapters,
    Mux, AudioStream, VideoStream, ChapterStream, JAPANESE, FRENCH,
    RunnerConfig, SelfRunner,
)
from vardautomation.status import Status

import os
from typing import Optional, List


def set_bitdepth(clip: vs.VideoNode):
    return depth(clip, 10).std.Limiter(16<<2, [235<<2, 240<<2], [0, 1, 2])


class Encoder:
    """Encoder class"""

    def __init__(
        self,
        bd: FileInfo,
        web: Optional[FileInfo],
        clip: vs.VideoNode,
        chapters: Optional[List[Chapter]] = None,
        chapter_names: Optional[List[str]] = None
    ) -> None:

        self.bd = bd
        self.bd.name_file_final = VPath(f"./premux/{self.bd.ep_num}_premux.mkv")
        self.bd.set_name_clip_output_ext(".hevc")

        self.web = web

        self.clip = set_bitdepth(clip)

        self.chapters = chapters
        self.chapters_names = chapter_names


    def run(self, generate_keyframes: bool = True, clean_up: bool = True) -> None:
        """Run the encoder with specified settings.

        ---

        Eighty Six specific settings:
        - x265 Encoder
        - FFmpegAudioExtracter: 1st BD track + 2nd WEB track
        - EztrimCutter : BD + WEB
        - QAACEncoder : BD only
        - MatroskaXMLChapters: generated from .mpls, renamed and shifted
        - Muxer

        ---

        Args:
        - generate_keyframe: generate keyframes for timing
        - clean_up: clean temporary files after encoding (e.g. raw audio)
        """

        v_encoder = X265("common/x265_settings")

        a_extract = [FFmpegAudioExtracter(self.bd, track_in=1, track_out=1)]

        a_cutter = EztrimCutter(self.bd, track=1)

        a_encoder = QAACEncoder(self.bd, track=1, mode=BitrateMode.TVBR, bitrate=127, qaac_args=["-N"])

        audio_streams = [AudioStream(self.bd.a_enc_cut.set_track(1), "AAC 2.0", JAPANESE)]

        if self.web:
            a_extract.append(FFmpegAudioExtracter(self.web, track_in=1, track_out=2))
            audio_streams.append(AudioStream(self.web.a_src.set_track(2), "AAC 2.0", FRENCH))

        if self.chapters:
            self.bd.chapter = VPath(f"{self.bd.ep_num}_chapters.xml")
            chapterXML = MatroskaXMLChapters(self.bd.chapter)
            chapterXML.create(self.chapters, self.bd.clip.fps)
            chapterXML.set_names(self.chapters_names)

            self.chapter_offset = self.bd.trims_or_dfs[0]

            if isinstance(self.chapter_offset, int):
                self.chapter_offset = self.chapter_offset * -1
                chapterXML.shift_times(self.chapter_offset, self.bd.clip.fps)

        muxer = Mux(
            self.bd,
            streams=(
                VideoStream(self.bd.name_clip_output, "x265 BD"),
                audio_streams,
                ChapterStream(chapterXML.chapter_file) if self.chapters else None
            )
        )

        config = RunnerConfig(v_encoder, None, a_extract, a_cutter, a_encoder, muxer)

        runner = SelfRunner(self.clip, self.bd, config)
        runner.run()

        if generate_keyframes:
            if os.path.isfile(self.bd.name_file_final):
                clip = vs.core.ffms2.Source(self.bd.name_file_final)

                Status.info("Generating keyframes from encoded file")
            else:
                clip = self.clip
                Status.info("Generating keyframes from filtered clip")

            kgf.generate_keyframes(clip, f"{self.bd.name_file_final.to_str()}_keyframes.txt")

        if clean_up:
            Status.info("Cleaning up extra files")
            runner.work_files.add(f"{self.bd.name_file_final.to_str()}.ffindex")
            runner.work_files.add(self.web.a_src.set_track(2).to_str())
            runner.work_files.clear()

import vapoursynth as vs
import kagefunc as kgf
from vsutil import depth, get_depth
from vardautomation import (
    FileInfo, VPath,
    X265Encoder, FFmpegAudioExtracter, EztrimCutter, QAACEncoder, BitrateMode,
    Chapter, MatroskaXMLChapters,
    Mux, AudioStream, VideoStream, ChapterStream, JAPANESE,
    RunnerConfig, SelfRunner
)
from vardautomation.status import Status

import os
from typing import Optional, List

class Encoder:
    """Encoder class"""
    
    def __init__(
        self, 
        file: FileInfo, 
        clip: vs.VideoNode, 
        chapters: Optional[List[Chapter]] = None,
        chapter_names: Optional[List[str]] = None
    ) -> None:

        self.file = file
        self.clip = clip
        self.chapters = chapters
        self.chapters_names = chapter_names


    def run(self, generate_keyframes: bool=True, clean_up: bool=True) -> None:
        """Run the encoder with specified settings. 

        ---

        Eighty Six specific settings:
        - x265 Encoder
        - FFmpegAudioExtracter: 1st track
        - EztrimCutter
        - QAACEncoder
        - MatroskaXMLChapters: generated from .mpls, renamed and shifted
        - Muxer

        ---

        Args:
        - generate_keyframe: generate keyframes for timing
        - clean_up: clean temporary files after encoding (e.g. raw audio)
        """


        if get_depth(self.clip) != 10:
            self.clip = depth(self.clip, 10)

        v_encoder = X265Encoder("common/x265_settings")

        a_extract = FFmpegAudioExtracter(self.file, track_in=1, track_out=1)

        a_cutter = EztrimCutter(self.file, track=1)

        a_encoder = QAACEncoder(self.file, track=1, mode=BitrateMode.TVBR, bitrate=127, qaac_args=["-N"])

        if self.chapters:
            self.file.chapter = VPath(f"{self.file.ep_num}_chapters.xml")
            chapterXML = MatroskaXMLChapters(self.file.chapter)
            chapterXML.create(self.chapters, self.file.clip.fps)
            chapterXML.set_names(self.chapters_names)

            self.chapter_offset = self.file.trims_or_dfs[0]

            if isinstance(self.chapter_offset, int):
                self.chapter_offset = self.chapter_offset * -1
                chapterXML.shift_times(self.chapter_offset, self.file.clip.fps)

        self.file.name_file_final = VPath(f"../{self.file.ep_num}_premux.mkv")
        muxer = Mux(
            self.file,
            streams=(
                VideoStream(self.file.name_clip_output, "x265 BD"),
                AudioStream(self.file.a_enc_cut.set_track(1), "AAC 2.0", JAPANESE),
                ChapterStream(chapterXML.chapter_file) if self.chapters else None
            )
        )

        config = RunnerConfig(v_encoder, None, a_extract, a_cutter, a_encoder, muxer)

        runner = SelfRunner(self.clip, self.file, config)
        runner.run()

        if generate_keyframes:
            if os.path.isfile(self.file.name_file_final):
                clip = vs.core.ffms2.Source(self.file.name_file_final)
                Status.info(f"Generating keyframes from encoded file")
            else:
                clip = self.clip
                Status.info(f"Generating keyframes from filtered clip")

            kgf.generate_keyframes(clip, f"{self.file.name_file_final.to_str()}_keyframes.txt")
        
        if clean_up:
            Status.info("Cleaning up extra files")
            runner.do_cleanup()

            #remove ffindex of final file if used to generate keyframe
            if os.path.isfile(f"{self.file.name_file_final.to_str()}.ffindex"):
                os.remove(f"{self.file.name_file_final.to_str()}.ffindex")
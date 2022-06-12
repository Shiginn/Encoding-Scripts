__all__ = ["ParseBD"]

from pathlib import Path
from typing import Any, List

import vapoursynth as vs
from vardautomation import (Chapter, FileInfo, MplsReader, PresetBD,
                            PresetOpus, VPath)

core = vs.core


class ParseBD:
    bdmv_folder: Path
    episodes: List[VPath]
    episode_number: int

    _bd_vols: List[Path]
    _vol_number: int
    _ep_per_vol: List[int]
    _ep_playlist: List[int]

    def __init__(self, bdmv_folder: str, bd_volumes: List[str], ep_playlist: int | List[int] = 1) -> None:
        """
        Parse a Blu-Ray (BD) by reading the playlist files in order to get the list of episodes

        :param bdmv_folder:     Path to the BDMV folder that contains every volume
        :param bd_volumes:      Path to every volume of the BD (relative to the BDMV folder)
        :param ep_playlist:     Playlist file for the episodes (defaults to 1, can be set for each volume)
        """
        self.bdmv_folder = Path(bdmv_folder).resolve()
        self._bd_vols = [Path(self.bdmv_folder / bd_vol).resolve() for bd_vol in bd_volumes]
        self._vol_number = len(self._bd_vols)

        if any(not path.exists() for path in [self.bdmv_folder] + self._bd_vols):
            raise ValueError("Invalid path")

        self._ep_playlist = self._validate_list(ep_playlist, self._vol_number)

        self._ep_per_vol = []
        self.episodes = []
        for bd_vol, p in zip(self._bd_vols, self._ep_playlist):
            eps = [chap.m2ts for chap in self._parse_playlist(bd_vol, p)]
            self.episodes += eps
            self._ep_per_vol += [len(eps)]



    def _parse_playlist(self, bd_vol: Path, playlist: int):
        return MplsReader(self.bdmv_folder / bd_vol).get_playlist()[playlist].mpls_chapters


    def get_episode(self, ep_num: int | str, **fileinfo_args: Any) -> FileInfo:
        """
        Get FileInfo object of an episode

        :param ep_num:          Episode to get
        :param fileinfo_args:   Additional parameters to be passed to FileInfo

        :return:                FileInfo object
        """
        if isinstance(ep_num, str):
            ep_num = int(ep_num)

        args = dict(trims_or_dfs=(24, -24), preset=[PresetBD, PresetOpus], idx=core.lsmas.LWLibavSource)
        args |= fileinfo_args

        return FileInfo(self.episodes[ep_num - 1], **args)


    def get_chapter(
        self,
        ep_num: int | str
    ) -> List[Chapter]:
        """Get a list of chapters of an episode

        :param ep_num:      Episode to get

        :return:            List of chapters
        """
        if isinstance(ep_num, str):
            ep_num = int(ep_num)

        offset = 0
        i = 0
        while ep_num > (vol_eps := self._ep_per_vol[i]):
            ep_num -= vol_eps
            offset += vol_eps
            i += 1

        return self._parse_playlist(self._bd_vols[i], self._ep_playlist[i])[ep_num - 1].to_chapters()


    @staticmethod
    def _validate_list(src: Any, target_length: int) -> List[Any]:
        if not isinstance(src, list):
            return [src] * target_length
        elif len(src) < target_length:
            return list(src) + ([src[-1]] * (target_length - len(src)))
        elif len(src) > target_length:
            raise ValueError(f"Too many playlist values, expected {target_length} max")

        return src

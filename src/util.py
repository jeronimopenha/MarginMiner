import os
import sys
from datetime import date
from pathlib import Path
from typing import List, Tuple


class Util:
    @staticmethod
    def get_files_list_by_extension(path: str, file_extension: str) -> List[Tuple[str, str]]:
        """
        Get a list of files with a specific extension in a directory.

        :param path: The path to the directory.
        :type path: str
        :param file_extension: The file extension to filter.
        :type file_extension: str
        :return: A list of tuples containing the file path and file name.
        :rtype: List[Tuple[str, str]]
        """
        files_list_by_extension: List[Tuple[str, str]] = [
            (os.path.join(file_path, file_name), file_name)
            for file_path, _, filenames in os.walk(path)
            for file_name in filenames
            if os.path.splitext(file_name)[1] == file_extension
        ]
        return files_list_by_extension

    @staticmethod
    def get_project_root() -> str:
        """
        Get the root path of the project.

        Returns:
            str: The root path of the project.
        """
        path: Path = Path(__file__).parent.parent
        return str(path)

    @staticmethod
    def get_data_dir(sub_folder: str = ""):
        app_dir = Util.get_app_dir()
        data_dir = app_dir / ("data/" + sub_folder)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def get_app_dir():
        if getattr(sys, "frozen", False):
            # executável empacotado (AppImage)
            return Path(sys.executable).resolve().parent
        else:
            # modo dev
            return Path(__file__).resolve().parents[2]

    def years_ago(today: date | None = None) -> date:
        DEFAULT_LOOKBACK_YEARS = 10

        if today is None:
            today = date.today()

        try:
            return today.replace(year=today.year - DEFAULT_LOOKBACK_YEARS)
        except ValueError:
            # caso raro: 29/02
            return today.replace(month=2, day=28, year=today.year - DEFAULT_LOOKBACK_YEARS)

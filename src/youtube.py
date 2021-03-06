import collections.abc
import html.parser
import sys
import urllib.error
import urllib.request

import bs4
import pytube
import pytube.exceptions
from PyQt5 import QtCore, QtWidgets


class YouTube(QtCore.QObject):
    resolutions = collections.OrderedDict([("144p", "144p"), ("144p 15 fps", "144p15"), ("240p", "240p"),
                                           ("360p", "SD (360p)"), ("480p", "FWVGA (480p)"),
                                           ("720p", "HD (720p)"), ("720p HFR", "HD (720p60)"),
                                           ("1080p", "Full HD (1080p)"), ("1080p HFR", "Full HD (1080p60)"),
                                           ("1440p", "Quad HD (1440p)"), ("1440p HFR", "Quad HD (1440p60)"),
                                           ("2160p", "4K UHD (2160p)"), ("2160p HFR", "4K UHD (2160p60)"),
                                           ("2160p-2304p", "4K UHD (2160p-2304p)"),
                                           ("2160p-4320p", "4K UHD (2160p-4320p)")])

    formats = collections.OrderedDict([("mp4", "MPEG-4 AVC / H.264 (.mp4)"),
                                       ("webm", "VP9 (.webm)"),
                                       ("3gpp", "MPEG-4 Visual (.3gpp)"),
                                       ("flv", "Sorenson H.263 (.flv)")])

    standard_formats = collections.OrderedDict([("mp4", ["360p", "720p"]),
                                                ("webm", ["360p"]),
                                                ("3gpp", ["144p", "240p"])])

    finished = QtCore.pyqtSignal()
    video_found = QtCore.pyqtSignal(list)
    playlist_found = QtCore.pyqtSignal(list)
    success = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str, str, int, tuple, bool)

    last_downloaded = []

    def __init__(self, page_url):
        super().__init__()
        self.page_url = page_url

    def find_videos(self):
        try:
            if not self.page_url:
                self.error.emit("Error", "No URL given. Enter a URL to continue.",
                                QtWidgets.QMessageBox.Warning, (), True)
            else:
                yt = pytube.YouTube(self.page_url)
                yt.register_on_progress_callback(self.on_progress)
                video = yt.streams.filter(progressive=True).desc().all()
                if video:
                    self.success.emit()
                    # TODO: instead of passing the StreamQuery, pass "self" -> download_video can be an instance method
                    self.video_found.emit(video)
        except (ValueError, AttributeError, urllib.error.URLError):
            try:
                yt = pytube.YouTube("https://" + self.page_url)
                yt.register_on_progress_callback(self.on_progress)
                video = yt.streams.filter(progressive=True).desc().all()
                if video:
                    self.success.emit()
                    self.video_found.emit(video)
            except pytube.exceptions.RegexMatchError:
                # this could be an invalid url OR we're maybe dealing with a playlist
                self.find_playlist("https://" + self.page_url)
            except (ValueError, AttributeError, urllib.error.URLError, pytube.exceptions.PytubeError):
                self.error.emit("Error", "Invalid url: no videos could be found. Check url for typos.",
                                QtWidgets.QMessageBox.Warning, sys.exc_info(), True)

        except pytube.exceptions.RegexMatchError:
            # this could be an invalid url OR we're maybe dealing with a playlist
            self.find_playlist(self.page_url)
        except pytube.exceptions.PytubeError:
            self.error.emit("Error", "An error occurred. Couldn't get video(s). Try another url.",
                            QtWidgets.QMessageBox.Warning, sys.exc_info(), True)
        finally:
            self.finished.emit()

    def find_playlist(self, url):
        page_html = urllib.request.urlopen(url).read()
        page_soup = bs4.BeautifulSoup(page_html, "html.parser")

        playlist_html = page_soup.find_all(
            "a", attrs={"class": "pl-video-title-link yt-uix-tile-link yt-uix-sessionlink spf-link "})

        if not playlist_html:
            self.error.emit("Error", "This is not a playlist (or shitty youtube have changed their html again).",
                            QtWidgets.QMessageBox.Warning, sys.exc_info(), True)
        else:
            videos = []
            for a in playlist_html:
                videos.append((a.string.strip(), "https://www.youtube.com" + a.get("href")))

            self.success.emit()
            self.playlist_found.emit(videos)

    @staticmethod
    def prettify(video_format):
        if video_format in YouTube.formats.keys():
            return YouTube.formats[video_format]
        elif video_format in YouTube.resolutions.keys():
            return YouTube.resolutions[video_format]

    @staticmethod
    def uglify(video_format):
        reversed_format_dict = collections.OrderedDict((value, key) for key, value in YouTube.formats.items())
        reversed_resolution_dict = collections.OrderedDict((value, key) for key, value in YouTube.resolutions.items())

        if video_format in reversed_format_dict.keys():
            return reversed_format_dict[video_format]
        elif video_format in reversed_resolution_dict.keys():
            return reversed_resolution_dict[video_format]

    @staticmethod
    def download_video(video_list, extension="mp4", resolution=None, destination=""):
        raise NotImplementedError("Since this application is still under active development, not all features are "
                                  "available yet. Be patient!")

    @staticmethod
    def download_playlist(video_list, extension="mp4", resolution=None, destination=""):
        raise NotImplementedError("Since this application is still under active development, not all features are "
                                  "available yet. Be patient!")

    @staticmethod
    def _download_video(video, extension, resolution, destination=""):
        # TODO: "really" do it (put downloading into thread, emit signals, update progress bar etc.)
        global stream_filesize
        YouTube.last_downloaded.clear()
        successful_downloads = 0
        errors = 0
        print("Downloading ", "1", "of", "1", "...", flush=True)
        try:
            for stream in video:
                if stream.subtype == extension and stream.resolution == resolution:
                    stream_filesize = stream.filesize
                    stream.download(destination)
                    break
        except Exception:
            print("An error occurred:\n", sys.exc_info())
            errors += 1
        else:
            successful_downloads += 1
            YouTube.last_downloaded.append(stream)

        print(successful_downloads, "of", "1", "videos were downloaded successfully.")
        if errors:
            print(errors, "errors occurred.")
        return

    @staticmethod
    def _download_playlist(video_list, extension, resolution, destination=""):
        # TODO: multi-threaded downloading -> playlists download faster
        global stream_filesize
        YouTube.last_downloaded.clear()
        successful_downloads = 0
        errors = 0
        for index, video in enumerate(video_list):
            print("Downloading", index + 1, "of", len(video_list), "...", flush=True)
            try:
                yt = pytube.YouTube(video[1])
                # yt.register_on_progress_callback(self.on_progress)
                video = yt.streams.filter(progressive=True).desc().all()
                for stream in video:
                    if stream.subtype == extension and stream.resolution == resolution:
                        stream_filesize = stream.filesize
                        stream.download(destination)

            except Exception:
                print("An error occurred:\n", sys.exc_info())
                errors += 1
            else:
                successful_downloads += 1
                YouTube.last_downloaded.append(stream)

        print(successful_downloads, "of", len(video_list), "videos were downloaded successfully.")
        if errors:
            print(errors, "errors occurred.")
        return

    def on_progress(self, stream, chunk, file_handle, bytes_remaining):
        # accessing stream.filesize was a bottleneck -> fixed by declaring global var in download_video
        #
        # printing this data luckily doesn't affect performance negatively, now let's see how fast Qt is...

        # print(stream_filesize - bytes_remaining, "of", stream_filesize, "bytes downloaded,",
        #       bytes_remaining, "bytes remaining")
        pass

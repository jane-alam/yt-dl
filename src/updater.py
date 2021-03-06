import os
import shutil
import sys
import time
import urllib.request
import zipfile
from datetime import datetime
from distutils.version import StrictVersion

from PyQt5 import QtCore, QtWidgets

from config import VERSION, IS_FROZEN, APP_PATH


# TODO: support updating if application is frozen (.exe)
class Update(QtCore.QObject):

    status_update = QtCore.pyqtSignal(str)
    success = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str, str, int, tuple, bool)
    information = QtCore.pyqtSignal(str, str, int)
    finished = QtCore.pyqtSignal()

    def __init__(self, url):
        super().__init__()
        self.url = url

    def check_for_updates(self):
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M")
        self.filename = "yt-dl_update_" + current_datetime + ".zip"

        self.status_update.emit("1 / 5\nFetching the latest version from Github...")
        urllib.request.urlretrieve(self.url, self.filename)

        self.status_update.emit("2 / 5\nExtracting ZIP archive...")
        self.dst_folder = self.filename.split(".")[0]
        self.extract_zipball(self.filename, self.dst_folder)

        self.status_update.emit("3 / 5\nVerifying files...")
        self.new_files = self.query_files(self.dst_folder)

        if self.check_update_need():
            if not IS_FROZEN:
                self.status_update.emit("4 / 5\nCopying new files...")
                self.copy_files(self.new_files, APP_PATH)

                self.status_update.emit("5 / 5\nCleaning up...")
                self.cleanup()

                self.information.emit("Info", "Updated successfully! (" + self.old_version + " -> " + self.new_version
                                      + ")\nThe application will restart now for the update to take effect.",
                                      QtWidgets.QMessageBox.Information)
                time.sleep(5)
                self.success.emit()
            else:
                self.status_update.emit("5 / 5\nCleaning up...")
                self.cleanup()

                self.information.emit("Info", "Updating is not yet supported for Windows executables.",
                                      QtWidgets.QMessageBox.Information)
        else:
            self.status_update.emit("5 / 5\nCleaning up...")
            self.cleanup()

            self.information.emit("Info", "There's no update available at the time!",
                                  QtWidgets.QMessageBox.Information)

        self.finished.emit()

    @staticmethod
    def extract_zipball(fname, dst):
        with zipfile.ZipFile(fname) as archive:
            archive.extractall(dst)

    @staticmethod
    def query_files(tree):
        queried_files = []
        for root, _, files in os.walk(tree):
            for file in files:
                queried_files.append(os.path.join(root, file))
        return queried_files

    def check_update_need(self):
        for file in self.new_files:
            if file.endswith("config.py"):
                sys.path.insert(0, file)

        self.old_version = VERSION
        from config import VERSION as new_version
        self.new_version = new_version

        if StrictVersion(self.new_version) <= StrictVersion(self.old_version):
            return False
        else:
            return True

    def copy_files(self, files, dst):
        try:
            for file in files:
                shutil.copy2(file, dst)
        except OSError:
            # no write permissions or some other weird OS-thingy
            self.error.emit("Error", "Apparently you don't have write permissions for \"" + dst + "\".",
                            QtWidgets.QMessageBox.Warning, sys.exc_info(), True)

    def cleanup(self):
        shutil.rmtree(self.dst_folder)
        os.remove(self.filename)

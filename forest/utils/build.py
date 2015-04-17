# coding=utf-8
"""Модуль описывает методы сборки uwsgi со всеми необходимыми плагинами."""

from __future__ import unicode_literals, print_function

import os
import sys
import shutil
import urllib
import tarfile
import tempfile
import subprocess

try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


UWSGI_VERSION = "2.0.10"


FOREST_CFG = """
[uwsgi]
main_plugin = logzmq, emperor_zeromq
inherit = base
"""


def progressbar(bcount, bsize, fsize):
    """Обновляет прогрессбар загрузки исходного кода.

    :param bcount: Количество блоков
    :type bcount: int
    :param bsize: Размер блока
    :type bsize: int
    :param fsize: Размер файла
    :type fsize: int
    """
    dsize = min(bcount * bsize, fsize)
    part = int((dsize * 20) / fsize)
    print("\rDownloading {dsize:6}/{fsize:6} [{pbar:20}]".format(pbar="="*part, **locals()), end="")
    sys.stdout.flush()


def build_uwsgi(target):
    """Выполняет сборку uwsgi.

    :param target: Директория, куда будут помещены исполняемые файлы и плагины.
    :type target: str
    """
    tempdir = tempfile.mkdtemp()

    try:
        uwsgi_source = os.path.join(tempdir, "uwsgi.tar.gz")
        uwsgi_dir = os.path.join(tempdir, "uwsgi-" + UWSGI_VERSION)
        try:
            urllib.urlretrieve(
                "http://projects.unbit.it/downloads/uwsgi-{}.tar.gz".format(UWSGI_VERSION),
                uwsgi_source,
                reporthook=progressbar
            )
        finally:
            print("")

        tfile = tarfile.open(uwsgi_source, 'r:gz')
        tfile.extractall(tempdir)

        with open(os.path.join(uwsgi_dir, "buildconf" + os.sep + "forest.ini"), "w") as forest_cfg:
            forest_cfg.write(FOREST_CFG)

        uwsgiconfig_executable = os.path.join(uwsgi_dir, "uwsgiconfig.py")

        # ===========
        # uwsgi core binary
        print("Building uwsgi core... ", end="")
        sys.stdout.flush()
        proc = subprocess.Popen([
            "python2", uwsgiconfig_executable,
            "--build", "forest"
        ], stdout=DEVNULL, stderr=DEVNULL, cwd=uwsgi_dir)
        res = proc.wait()
        if res:
            raise Exception("Error building uwsgi core")
        print("done")
        # ==========

        # ==========
        # uwsgi python2 plugin
        print("Building python2 plugin... ", end="")
        sys.stdout.flush()
        proc = subprocess.Popen([
            "python2", uwsgiconfig_executable,
            "--plugin", "plugins/python",
            "forest", "python2"
        ], stdout=DEVNULL, stderr=DEVNULL, cwd=uwsgi_dir)
        res = proc.wait()
        if res:
            raise Exception("Error building python2 plugin")
        print("done")
        # ==========

        # ==========
        # uwsgi python3 plugin
        print("Building python3 plugin...", end="")
        sys.stdout.flush()
        proc = subprocess.Popen([
            "python3", uwsgiconfig_executable,
            "--plugin", "plugins/python",
            "forest", "python3"
        ], stdout=DEVNULL, stderr=DEVNULL, cwd=uwsgi_dir)
        res = proc.wait()
        if res:
            raise Exception("Error building python3 plugin")
        print("done")
        # ==========

        for f in ["uwsgi", "python2_plugin.so", "python3_plugin.so"]:
            shutil.copy(os.path.join(uwsgi_dir, f), target)
    except Exception as e:
        print("Error building uwsgi: {}".format(e))
    finally:
        shutil.rmtree(tempdir)

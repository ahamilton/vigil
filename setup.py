#!/usr/bin/env python3.8

# Copyright (C) 2017-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


setup(name="eris",
      version="20.04",
      description=("Eris maintains an up-to-date set of reports for every"
                   " file in a codebase."),
      url="https://github.com/ahamilton/eris",
      author="Andrew Hamilton",
      license="Artistic 2.0",
      packages=["eris", "eris.urwid"],
      package_data={"eris": ["LS_COLORS.sh", "tools.toml"]},
      entry_points={"console_scripts":
                    ["eris=eris.__main__:entry_point",
                     "eris-worker=eris.worker:main",
                     "eris-webserver=eris.webserver:main",
                     "pydoc_color=eris.pydoc_color:main"]})

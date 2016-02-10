#!/usr/bin/env python3

# Copyright (C) 2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import contextlib
import os
import unittest
import unittest.mock

import fill3
import golden
import tools


VIGIL_ROOT = os.path.dirname(__file__)


def widget_to_string(widget):
    appearance = widget.appearance_min()
    return str(fill3.join("\n", appearance))


@contextlib.contextmanager
def chdir(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def result_path(tool, input_filename):
    filename = tool.__qualname__ + "-" + input_filename.replace(".", "_")
    return os.path.join(VIGIL_ROOT, "golden-files", "results", filename)


def run_tool(tool, input_filename):
    with chdir(os.path.join(VIGIL_ROOT, "golden-files")):
        return tool(os.path.join(".", "input", input_filename))


class ToolsTestCase(unittest.TestCase):

    def _test_tool(self, tool, sub_tests):
        for input_filename, expected_status in sub_tests:
            with self.subTest(input_filename=input_filename):
                status, result = run_tool(tool, input_filename)
                golden_path = result_path(tool, input_filename)
                golden.assertGolden(widget_to_string(result), golden_path)
                self.assertEqual(status, expected_status)

    def test_metadata(self):
        mock_stat_result = unittest.mock.Mock(
            st_mode=0o755, st_mtime=1454282045, st_ctime=1454282045,
            st_atime=1454282047, st_size=12, st_uid=1111, st_gid=1111,
            st_nlink=2)
        mock_pw_entry = unittest.mock.Mock(pw_name="foo")
        with unittest.mock.patch.object(os, "stat",
                                        return_value=mock_stat_result):
            with unittest.mock.patch.object(tools.pwd, "getpwuid",
                                            return_value=mock_pw_entry):
                self._test_tool(tools.metadata,
                                [("hi3.py", tools.Status.normal)])

    def test_contents(self):
        self._test_tool(tools.contents, [("hi3.py", tools.Status.normal)])

    def test_python_syntax(self):
        self._test_tool(tools.python_syntax, [("hi3.py", tools.Status.ok),
                                              ("hi.py", tools.Status.ok)])

    def test_unittests(self):
        self._test_tool(tools.python_unittests,
                        [("hi3.py", tools.Status.not_applicable),
                         ("hi.py", tools.Status.not_applicable)])

    def test_pydoc(self):
        self._test_tool(tools.pydoc, [("hi3.py", tools.Status.normal),
                                      ("hi.py", tools.Status.normal)])

    def test_python_coverage(self):
        self._test_tool(tools.python_coverage,
                        [("hi3.py", tools.Status.normal),
                         ("hi.py", tools.Status.normal)])

    def test_pep8(self):
        self._test_tool(tools.pep8, [("hi3.py", tools.Status.ok),
                                     ("hi.py", tools.Status.ok)])

    def test_pyflakes(self):
        self._test_tool(tools.pyflakes, [("hi3.py", tools.Status.ok),
                                         ("hi.py", tools.Status.ok)])

    def test_pylint(self):
        self._test_tool(tools.pylint, [("hi3.py", tools.Status.ok),
                                       ("hi.py", tools.Status.ok)])

    def test_python_gut(self):
        self._test_tool(tools.python_gut, [("hi3.py", tools.Status.normal),
                                           ("hi.py", tools.Status.normal)])

    def test_python_modulefinder(self):
        self._test_tool(tools.python_modulefinder,
                        [("hi3.py", tools.Status.normal),
                         ("hi.py", tools.Status.normal)])

    def test_python_mccable(self):
        self._test_tool(tools.python_mccabe, [("hi3.py", tools.Status.ok),
                                              ("hi.py", tools.Status.ok)])

    def test_perl_syntax(self):
        self._test_tool(tools.perl_syntax, [("perl.pl", tools.Status.ok)])

    def test_perldoc(self):
        self._test_tool(tools.perldoc,
                        [("perl.pl", tools.Status.not_applicable),
                         ("contents.pod", tools.Status.normal)])

    def test_perltidy(self):
        self._test_tool(tools.perltidy, [("perl.pl", tools.Status.normal)])

    def test_perl6_syntax(self):
        self._test_tool(tools.perl6_syntax,
                        [("perl6.p6", tools.Status.problem)])

    def test_antic(self):
        self._test_tool(tools.antic,
                        [("closure-util.java", tools.Status.problem)])

    def test_jlint(self):
        self._test_tool(tools.jlint, [("javaversion.class", tools.Status.ok)])

    def test_uncrustify(self):
        self._test_tool(tools.uncrustify,
                        [("closure-util.java", tools.Status.problem),
                         ("hello.c", tools.Status.normal),
                         ("hello.h", tools.Status.normal),
                         ("hello.cpp", tools.Status.normal)])

    def test_splint(self):
        self._test_tool(tools.splint, [("hello.c", tools.Status.ok),
                                       ("hello.h", tools.Status.ok)])

    def test_objdump_headers(self):
        self._test_tool(tools.objdump_headers,
                        [("Mcrt1.o", tools.Status.normal)])

    def test_objdump_disassemble(self):
        self._test_tool(tools.objdump_disassemble,
                        [("Mcrt1.o", tools.Status.problem)])

    def test_readelf(self):
        self._test_tool(tools.readelf, [("Mcrt1.o", tools.Status.normal)])

    def test_unzip(self):
        self._test_tool(tools.unzip, [("hi.zip", tools.Status.normal)])

    def test_tar_gz(self):
        self._test_tool(tools.tar_gz, [("hi.tar.gz", tools.Status.normal),
                                       ("hi.tgz", tools.Status.normal)])

    def test_tar_bz2(self):
        self._test_tool(tools.tar_bz2, [("hi.tar.bz2", tools.Status.normal)])

    def test_nm(self):
        self._test_tool(tools.nm, [("libieee.a", tools.Status.normal),
                                   ("libpcprofile.so", tools.Status.normal)])

    def test_pdf2txt(self):
        self._test_tool(tools.pdf2txt, [("standard.pdf", tools.Status.normal)])

    def test_html_syntax(self):
        self._test_tool(tools.html_syntax, [("hi.html", tools.Status.problem)])

    def test_tidy(self):
        self._test_tool(tools.tidy, [("hi.html", tools.Status.normal)])

    def test_html2text(self):
        self._test_tool(tools.html2text, [("hi.html", tools.Status.normal)])

    def test_bcpp(self):
        self._test_tool(tools.bcpp, [("hello.cpp", tools.Status.normal)])

    def test_php5_syntax(self):
        self._test_tool(tools.bcpp, [("root.php", tools.Status.normal)])


if __name__ == "__main__":
    golden.main()
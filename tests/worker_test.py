#!/usr/bin/env python3.8

# Copyright (C) 2016-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.


import asyncio
import os
import shutil
import tempfile
import unittest

import eris.tools as tools
import eris.worker as worker


class WorkerTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_working_dir = os.getcwd()
        os.chdir(self.temp_dir)
        os.mkdir(tools.CACHE_PATH)
        open("foo", "w").close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        os.chdir(self.original_working_dir)

    def test_run_job(self):
        loop = asyncio.get_event_loop()
        compression = "none"
        worker_ = worker.Worker(False, compression)
        loop.run_until_complete(worker_.create_process())
        worker_.process.stdin.write(f"{compression}\n".encode("utf-8"))
        future = worker_.run_tool("foo", tools.metadata)
        status = loop.run_until_complete(future)
        self.assertEqual(status, tools.Status.normal)
        result_path = os.path.join(tools.CACHE_PATH, "foo-metadata")
        self.assertTrue(os.path.exists(result_path))


if __name__ == "__main__":
    unittest.main()

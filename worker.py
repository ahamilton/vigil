#!/usr/bin/env python3

# Copyright (C) 2015-2016 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import asyncio
import os
import signal

import psutil

import tools


def _make_process_nicest(pid):
    process = psutil.Process(pid)
    process.nice(19)
    process.ionice(psutil.IOPRIO_CLASS_IDLE)


class Worker:

    def __init__(self, sandbox, is_already_paused, is_being_tested):
        self.sandbox = sandbox
        self.is_already_paused = is_already_paused
        self.is_being_tested = is_being_tested
        self.result = None
        self.process = None
        self.child_pid = None

    async def create_process(self):
        command = [__file__]
        if self.sandbox is not None:
            command = self.sandbox.command(command)
        create = asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.process = await create
        pid_line = await self.process.stdout.readline()
        self.child_pid = int(pid_line.strip())

    async def run_tool(self, path, tool):
        self.process.stdin.write(("%s\n%s\n" %
                                  (tool.__qualname__, path)).encode("utf-8"))
        data = await self.process.stdout.readline()
        return tools.Status(int(data))

    async def job_runner(self, summary, log, jobs_added_event,
                         appearance_changed_event):
        await self.create_process()
        _make_process_nicest(self.child_pid)
        while True:
            await jobs_added_event.wait()
            while True:
                try:
                    self.result = summary.get_closest_placeholder()
                except StopIteration:
                    self.result = None
                    if summary.result_total == summary.completed_total:
                        log.log_message("All results are up to date.")
                        if self.is_being_tested:
                            os.kill(os.getpid(), signal.SIGINT)
                    break
                await self.result.run(log, appearance_changed_event,
                                      self)
                summary.completed_total += 1
            jobs_added_event.clear()

    def pause(self):
        if self.result is not None and \
           self.result.status == tools.Status.running:
            os.kill(self.child_pid, signal.SIGSTOP)
            self.result.set_status(tools.Status.paused)

    def continue_(self):
        if self.result is not None and \
           self.result.status == tools.Status.paused:
            self.result.set_status(tools.Status.running)
            os.kill(self.child_pid, signal.SIGCONT)


def main():
    print(os.getpid(), flush=True)
    try:
        while True:
            tool_name, path = input(), input()
            tool = getattr(tools, tool_name)
            result = tools.Result(path, tool)
            status, result.result = tools.run_tool_no_error(path, tool)
            print(status.value, flush=True)
    except:
        tools.log_error()


if __name__ == "__main__":
    main()

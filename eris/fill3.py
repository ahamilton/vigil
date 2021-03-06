#!/usr/bin/python3.8
# -*- coding: utf-8 -*-

# Copyright (C) 2015-2019 Andrew Hamilton. All rights reserved.
# Licensed under the Artistic License 2.0.

import asyncio
import contextlib
import itertools
import os
import signal
import sys

import eris.urwid
import eris.urwid.raw_display

import eris.terminal as terminal
import eris.termstr as termstr


def appearance_is_valid(appearance):
    return (all(isinstance(line, (str, termstr.TermStr)) and len(line) > 0
                for line in appearance) and
            len(set(len(line) for line in appearance)) < 2)


def appearance_resize(appearance, dimensions, pad_char=" "):
    width, height = dimensions
    result = [line[:width].ljust(width, pad_char)
              for line in appearance[:height]]
    if len(result) < height:
        result.extend([pad_char * width] * (height - len(result)))
    return result


def appearance_dimensions(appearance):
    try:
        return len(appearance[0]), len(appearance)
    except IndexError:
        return 0, 0


def join(seperator, parts):
    if parts == []:
        return ""
    try:
        return seperator.join(parts)
    except TypeError:
        return termstr.TermStr(seperator).join(parts)


def join_horizontal(appearances):
    heights = set(len(appearance) for appearance in appearances)
    assert len(heights) == 1, heights
    return [join("", parts) for parts in zip(*appearances)]


def even_widths(column_widgets, width):
    column_count = len(column_widgets)
    widths = []
    for index, column_widget in enumerate(column_widgets):
        start_pos = int(round(float(width) / column_count * index))
        end_pos = int(round(float(width) / column_count * (index+1)))
        widths.append(end_pos - start_pos)
    return widths


def appearance_as_html(appearance):
    lines = []
    all_styles = set()
    for line in appearance:
        html, styles = termstr.TermStr(line).as_html()
        all_styles.update(styles)
        lines.append(html)
    return ("\n".join(style.as_html() for style in all_styles) +
            "\n<pre>" + "<br>".join(lines) + "</pre>")


class Row:

    def __init__(self, widgets, widths_func=even_widths):
        self.widgets = widgets
        self.widths_func = widths_func

    def appearance(self, dimensions):
        width, height = dimensions
        widths = self.widths_func(self.widgets, width)
        assert sum(widths) == width, (sum(widths), width)
        return join_horizontal([column_widget.appearance((item_width, height))
                                for column_widget, item_width
                                in zip(self.widgets, widths)])

    def appearance_min(self):
        appearances = [column_widget.appearance_min()
                       for column_widget in self.widgets]
        dimensions = [appearance_dimensions(appearance)
                      for appearance in appearances]
        max_height = max(height for width, height in dimensions)
        return join_horizontal([
            appearance_resize(appearance, (width, max_height))
            for appearance, (width, height) in zip(appearances, dimensions)])


def even_partition(row_widgets, height):
    row_count = len(row_widgets)
    heights = []
    for index, row_widget in enumerate(row_widgets):
        start_pos = int(round(float(height) / row_count * index))
        end_pos = int(round(float(height) / row_count * (index+1)))
        heights.append(end_pos - start_pos)
    return heights


def join_vertical(appearances):
    result = []
    for appearance in appearances:
        result.extend(appearance)
    return result


class Column:

    def __init__(self, widgets, partition_func=even_partition,
                 background_char=" "):
        self.widgets = widgets
        self.partition_func = partition_func
        self.background_char = background_char

    def appearance(self, dimensions):
        width, height = dimensions
        if len(self.widgets) == 0:  # FIX: Really allow zero widgets?
            return [self.background_char * width] * height
        heights = self.partition_func(self.widgets, height)
        assert sum(heights) == height, (sum(heights), height)
        return join_vertical([row_widget.appearance((width, item_height))
                              for row_widget, item_height
                              in zip(self.widgets, heights)])

    def _appearance_list(self, widgets):
        if widgets == []:
            return []
        appearances = [row_widget.appearance_min() for row_widget in widgets]
        dimensions = [appearance_dimensions(appearance)
                      for appearance in appearances]
        max_width = max(width for width, height in dimensions)
        padded_appearances = [
            appearance_resize(appearance, (max_width, height))
            for appearance, (width, height) in zip(appearances, dimensions)]
        result = []
        for appearance in padded_appearances:
            result.extend(appearance)
        return result

    def appearance_interval(self, interval):
        start_y, end_y = interval
        return self._appearance_list(self.widgets[start_y:end_y])

    def appearance_min(self):
        return self._appearance_list(self.widgets)


class Filler:

    def __init__(self, widget):
        self.widget = widget

    def appearance(self, dimensions):
        return appearance_resize(self.widget.appearance_min(), dimensions)


class ScrollBar:

    _PARTIAL_CHARS = (["█", "▇", "▆", "▅", "▄", "▃", "▂", "▁"],
                      [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"])
    DEFAULT_BAR_COLOR = termstr.Color.grey_100
    DEFAULT_BACKGROUND_COLOR = termstr.Color.grey_30

    def __init__(self, is_horizontal, interval=(0, 0), bar_color=None,
                 background_color=None):
        self._is_horizontal = is_horizontal
        self.interval = interval
        bar_color = bar_color or ScrollBar.DEFAULT_BAR_COLOR
        background_color = (background_color or
                            ScrollBar.DEFAULT_BACKGROUND_COLOR)
        self._bar_char = termstr.TermStr("█").fg_color(bar_color)
        self._background_char = termstr.TermStr(" ").bg_color(background_color)
        if self._is_horizontal:
            bar_color, background_color = background_color, bar_color
        self._partial_chars = [(termstr.TermStr(char).fg_color(
            bar_color).bg_color(background_color),
                                termstr.TermStr(char).fg_color(
            background_color).bg_color(bar_color))
                for char in self._PARTIAL_CHARS[self._is_horizontal]]

    def appearance(self, dimensions):
        width, height = dimensions
        assert width == 1 or height == 1, (width, height)
        length = width if self._is_horizontal else height
        assert all(0 <= fraction <= 1 for fraction in self.interval), \
            self.interval
        (start_index, start_remainder), (end_index, end_remainder) = \
            [divmod(fraction * length * 8, 8) for fraction in self.interval]
        start_index, end_index = int(start_index), int(end_index)
        start_remainder, end_remainder = \
            int(start_remainder), int(end_remainder)
        if start_index == end_index:
            end_index, end_remainder = start_index + 1, start_remainder
        elif end_index == start_index + 1:
            end_remainder = max(start_remainder, end_remainder)
        bar = (self._background_char * start_index +
               self._partial_chars[start_remainder][0] +
               self._bar_char * (end_index - start_index - 1) +
               self._partial_chars[end_remainder][1] +
               self._background_char * (length - end_index - 1))
        bar = bar[:length]
        return [bar] if self._is_horizontal else [char for char in bar]


class Portal:

    def __init__(self, widget, position=(0, 0), background_char=" "):
        self.widget = widget
        self.position = position
        self.background_char = background_char
        self.last_dimensions = 0, 0

    def _scroll_half_pages(self, dx, dy):
        x, y = self.position
        width, height = self.last_dimensions
        self.position = (max(x + dx * (width // 2), 0),
                         max(y + dy * (height // 2), 0))

    def scroll_up(self):
        self._scroll_half_pages(0, -1)

    def scroll_down(self):
        self._scroll_half_pages(0, 1)

    def scroll_left(self):
        self._scroll_half_pages(-1, 0)

    def scroll_right(self):
        self._scroll_half_pages(1, 0)

    def appearance(self, dimensions):
        width, height = dimensions
        x, y = self.position
        try:
            appearance = self.widget.appearance_interval((y, y+height))
        except AttributeError:
            appearance = self.widget.appearance_min()[y:y+height]
        self.last_dimensions = dimensions
        return appearance_resize([row[x:x+width] for row in appearance],
                                 dimensions, self.background_char)


class View:

    def __init__(self, portal, horizontal_scrollbar, vertical_scrollbar,
                 hide_scrollbars=True):
        self.portal = portal
        self.horizontal_scrollbar = horizontal_scrollbar
        self.vertical_scrollbar = vertical_scrollbar
        self.hide_scrollbars = hide_scrollbars

    @classmethod
    def from_widget(cls, widget):
        return cls(Portal(widget), ScrollBar(is_horizontal=True),
                   ScrollBar(is_horizontal=False))

    @property
    def position(self):
        return self.portal.position

    @position.setter
    def position(self, position):
        self.portal.position = position

    @property
    def widget(self):
        return self.portal.widget

    @widget.setter
    def widget(self, widget):
        self.portal.widget = widget

    def appearance(self, dimensions):
        width, height = dimensions
        try:
            full_width, full_height = (self.portal.widget.
                                       appearance_dimensions())
        except AttributeError:
            full_appearance = self.portal.widget.appearance_min()
            full_width, full_height = appearance_dimensions(full_appearance)
        if full_width == 0 or full_height == 0:
            return self.portal.appearance(dimensions)
        x, y = self.portal.position
        hide_scrollbar_vertical = (self.hide_scrollbars and
                                   full_height <= height and y == 0)
        hide_scrollbar_horizontal = (self.hide_scrollbars and
                                     full_width <= width and x == 0)
        if not hide_scrollbar_horizontal:
            full_width = max(full_width, x + width)
            self.horizontal_scrollbar.interval = (x / full_width,
                                                  (x + width) / full_width)
            height -= 1
        if not hide_scrollbar_vertical:
            full_height = max(full_height, y + height)
            self.vertical_scrollbar.interval = (y / full_height,
                                                (y + height) / full_height)
            width -= 1
        portal_appearance = self.portal.appearance((width, height))
        if hide_scrollbar_vertical:
            result = portal_appearance
        else:
            scrollbar_v_appearance = self.vertical_scrollbar.appearance(
                (1, height))
            result = join_horizontal([portal_appearance,
                                      scrollbar_v_appearance])
        if not hide_scrollbar_horizontal:
            scrollbar_h_appearance = self.horizontal_scrollbar.appearance(
                (width, 1))
            result.append(scrollbar_h_appearance[0] +
                          ("" if hide_scrollbar_vertical else " "))
        return result


def str_to_appearance(text, pad_char=" "):
    lines = text.splitlines()
    if len(lines) == 0:
        return []
    max_width = max(len(line) for line in lines)
    height = len(lines)
    return appearance_resize(lines, (max_width, height), pad_char)


class Text:

    def __init__(self, text, pad_char=" "):
        self.text = str_to_appearance(text, pad_char)

    def appearance_min(self):
        return self.text

    def appearance(self, dimensions):
        return appearance_resize(self.appearance_min(), dimensions)


class Table:

    def __init__(self, table, pad_char=" "):
        self._widgets = table
        self._pad_char = pad_char

    def appearance_min(self):
        if self._widgets == []:
            return []
        appearances = [[cell.appearance_min() for cell in row]
                       for row in self._widgets]
        row_heights = [0] * len(self._widgets)
        column_widths = [0] * len(self._widgets[0])
        for y, row in enumerate(appearances):
            for x, appearance in enumerate(row):
                width, height = appearance_dimensions(appearance)
                row_heights[y] = max(row_heights[y], height)
                column_widths[x] = max(column_widths[x], width)
        return join_vertical([join_horizontal(
            [appearance_resize(appearance, (column_widths[x], row_heights[y]),
                               pad_char=self._pad_char)
             for x, appearance in enumerate(row)])
            for y, row in enumerate(appearances)])


class Border:

    THIN = ["─", "─", "│", "│", "┌", "└", "┘", "┐"]
    THICK = ["━", "━", "┃", "┃", "┏", "┗", "┛", "┓"]
    ROUNDED = ["─", "─", "│", "│", "╭", "╰", "╯", "╮"]
    DOUBLE = ["═", "═", "║", "║", "╔", "╚", "╝", "╗"]

    def __init__(self, widget, title=None, characters=THIN):
        self.widget = widget
        self.title = title
        self.set_style(characters)

    def set_style(self, characters):
        (self.top, self.bottom, self.left, self.right, self.top_left,
         self.bottom_left, self.bottom_right, self.top_right) = characters

    def _add_border(self, body_content):
        content_width, content_height = appearance_dimensions(body_content)
        if self.title is None:
            title_bar = self.top * content_width
        else:
            padded_title = " " + ("…" + self.title[-(content_width-3):]
                                  if len(self.title) > content_width - 2
                                  else self.title) + " "
            try:
                title_bar = padded_title.center(content_width, self.top)
            except TypeError:
                padded_title = termstr.TermStr(padded_title)
                title_bar = padded_title.center(content_width, self.top)
        result = [self.top_left + title_bar + self.top_right]
        result.extend(self.left + line + self.right for line in body_content)
        result.append(self.bottom_left + self.bottom * content_width +
                      self.bottom_right)
        return result

    def appearance_min(self):
        return self._add_border(self.widget.appearance_min())

    def appearance(self, dimensions):
        width, height = dimensions
        return self._add_border(self.widget.appearance((width-2, height-2)))


class Placeholder:

    def __init__(self, widget=None):
        self.widget = widget

    def appearance_min(self):
        return self.widget.appearance_min()

    def appearance(self, dimensions):
        return self.widget.appearance(dimensions)


class Fixed:

    def __init__(self, appearance_min):
        self.appearance_min_ = appearance_min
        self.dimensions = appearance_dimensions(appearance_min)

    def appearance_min(self):
        return self.appearance_min_

    def appearance_dimensions(self):
        return self.dimensions


##########################


_last_appearance = []


def draw_screen(widget):
    global _last_appearance
    appearance = widget.appearance(os.get_terminal_size())
    print(terminal.move(0, 0), *appearance, sep="", end="", flush=True)
    _last_appearance = appearance


def patch_screen(widget):
    global _last_appearance
    appearance = widget.appearance(os.get_terminal_size())
    zip_func = (itertools.zip_longest
                if len(appearance) > len(_last_appearance) else zip)
    changed_lines = (str(terminal.move(0, row_index)) + line
                     for row_index, (line, old_line)
                     in enumerate(zip_func(appearance, _last_appearance))
                     if line != old_line)
    print(*changed_lines, sep="", end="", flush=True)
    _last_appearance = appearance


@contextlib.contextmanager
def _urwid_screen():
    screen = eris.urwid.raw_display.Screen()
    screen.set_mouse_tracking(True)
    screen.start()
    try:
        yield screen
    finally:
        screen.stop()


async def update_screen(screen_widget, appearance_changed_event):
    while True:
        await appearance_changed_event.wait()
        appearance_changed_event.clear()
        patch_screen(screen_widget)
        await asyncio.sleep(0.01)


def on_input(urwid_screen, screen_widget):
    for event in urwid_screen.get_input():
        screen_widget.on_input_event(event)


@contextlib.contextmanager
def context(loop, appearance_changed_event, screen_widget, exit_loop=None):
    appearance_changed_event.set()
    if exit_loop is None:
        exit_loop = loop.stop
    loop.add_signal_handler(signal.SIGWINCH, lambda: draw_screen(screen_widget))
    loop.add_signal_handler(signal.SIGINT, exit_loop)
    loop.add_signal_handler(signal.SIGTERM, exit_loop)
    with terminal.hidden_cursor(), terminal.fullscreen(), \
            _urwid_screen() as urwid_screen:
        loop.add_reader(sys.stdin, on_input, urwid_screen, screen_widget)
        yield


##########################


class _Screen:

    def __init__(self, appearance_changed_event):
        self.appearance_changed_event = appearance_changed_event
        self.content = Filler(Text("Hello World"))

    def appearance(self, dimensions):
        return self.content.appearance(dimensions)

    def on_input_event(self, event):
        self.appearance_changed_event.set()


def _main():
    loop = asyncio.get_event_loop()
    appearance_changed_event = asyncio.Event()
    screen = _Screen(appearance_changed_event)
    loop.create_task(update_screen(screen, appearance_changed_event))
    with context(loop, appearance_changed_event, screen):
        loop.run_forever()


if __name__ == "__main__":
    _main()

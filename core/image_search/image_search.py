# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


import datetime
import logging
from typing import List

import cv2
import numpy as np

try:
    import Image
except ImportError:
    from PIL import Image

from core.image_search.pattern import Pattern
from core.settings import Settings
from core.helpers.location import Location
from core.errors import ScreenshotError
from core.helpers.rectangle import Rectangle
from core.screen.screenshot_image import ScreenshotImage

# from save_debug_image import save_debug_image

logger = logging.getLogger(__name__)

FIND_METHOD = cv2.TM_CCOEFF_NORMED


def is_pattern_size_correct(pattern: Pattern, region: Rectangle):
    """validates that the pattern is inside the region."""
    p_width, p_height = pattern.get_size()
    r_width = region.width
    r_height = region.height
    is_correct = True

    if p_width > r_width:
        logger.warning('Pattern Width (%s) greater than Region/Screenshot Width (%s)' % (p_width, r_width))
        is_correct = False
    if p_height > r_height:
        logger.warning('Pattern Height (%s) greater than Region/Screenshot Height (%s)' % (p_height, r_height))
        is_correct = False
    return is_correct


def match_template(pattern: Pattern, region: Rectangle = None) -> Location:
    """Find a pattern in a Region or full screen

    :param Pattern pattern: Image details
    :param Region region: Region object.
    :return: Location.
    """
    logger.debug('Searching for pattern: %s' % pattern.get_filename())
    try:
        stack_image = ScreenshotImage(region=region)
        precision = pattern.similarity

        needle = pattern.get_color_image() if precision == 0.99 else pattern.get_gray_image()
        haystack = stack_image.get_color_image() if precision == 0.99 else stack_image.get_gray_image()

        res = cv2.matchTemplate(np.array(haystack), np.array(needle), FIND_METHOD)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val < precision:
            position = Location(-1, -1)
        else:
            position = Location(max_loc[0], max_loc[1])

        # if position.x == -1:
        #     save_debug_image(needle, np.array(haystack), None, True)
        # else:
        #     save_debug_image(needle, haystack, position)
    except ScreenshotError:
        logger.warning('Screenshot failed.')
        position = Location(-1, -1)

    if position.x == -1 or position.y == -1:
        return position
    elif region is not None:
        return Location(position.x + region.x, position.y + region.y)
    else:
        return position


def match_template_multiple(pattern: Pattern, region: Rectangle = None, threshold: float = 0.5) -> List[Location]:
    """Find all occurrences of a pattern in a Region or full screen

    :param Pattern pattern: Image details
    :param Region region: Region object.
    :param threshold: float
    :return: List of locations.
    """
    logger.debug('Searching for pattern: %s' % pattern.get_filename())
    try:
        stack_image = ScreenshotImage(region=region)
        precision = pattern.similarity

        needle = pattern.get_rgb_array() if precision == 0.99 else pattern.get_gray_array()
        haystack = stack_image.get_rgb_array() if precision == 0.99 else stack_image.get_gray_array()

        res = cv2.matchTemplate(haystack, needle, FIND_METHOD)

        final_matches = []
        while True:
            min_val, max_val, min_loc, best_match = cv2.minMaxLoc(res)
            if FIND_METHOD in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                top_left = min_loc
            else:
                top_left = best_match

            if precision > max_val > threshold:
                sx, sy = top_left
                width, height = pattern.get_size()
                for x in range(int(sx - width / 2), int(sx + width / 2)):
                    for y in range(int(sy - height / 2), int(sy + height / 2)):
                        try:
                            res[y][x] = np.float32(-10000)
                        except IndexError:
                            pass
                new_match_point = Location(top_left[0], top_left[1])
                final_matches.append(new_match_point)
            else:
                break
        return final_matches
    except ScreenshotError:
        logger.warning('Screenshot failed.')
        return []


def image_find(pattern: Pattern, timeout: float = None, region: Rectangle = None) -> None or Location:
    """ Search for an image in a Region or full screen.

    :param Pattern pattern: Name of the searched image.
    :param timeout: Number as maximum waiting time in seconds.
    :param Region region: Region object.
    :return: Location.
    """
    if not is_pattern_size_correct(pattern, region):
        return None

    if timeout is None:
        timeout = Settings.auto_wait_timeout

    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(seconds=timeout)

    while start_time < end_time:
        time_remaining = end_time - start_time
        logger.debug("Searching for image %s - %s seconds remaining" % (pattern.get_filename(), time_remaining))
        pos = match_template(pattern, region)
        start_time = datetime.datetime.now()

        if pos.x != -1:
            return pos
    return None


def image_vanish(pattern: Pattern, timeout: float = None, region: Rectangle = None) -> None or bool:
    """ Search if an image is NOT in a Region or full screen.

    :param Pattern pattern: Name of the searched image.
    :param timeout: Number as maximum waiting time in seconds.
    :param Region region: Region object.
    :return: Location.
    """
    if not is_pattern_size_correct(pattern, region):
        return None

    pattern_found = True

    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(seconds=timeout)

    while pattern_found is True and start_time < end_time:
        image_found = match_template(pattern, region)
        if (image_found.x != -1) & (image_found.y != -1):
            pattern_found = True
        else:
            pattern_found = False
        start_time = datetime.datetime.now()

    return None if pattern_found else True

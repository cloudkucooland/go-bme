#!/usr/bin/python3
# -*- coding: utf-8 -*-
# written by Scot C. Bontrager, March 2016
# this file is public domain - more free than free
import os
import sys
import logging
import csv
import signal

# import pprint
# import string, stat
import pybme
from optparse import OptionParser

logger = logging.getLogger()
# import inspect, pprint


def main():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-d",
        "--debug",
        help="enable debugging (extreme verbosity) (false)",
        action="store_true",
        dest="debug",
        default=False,
    )

    (options, args) = parser.parse_args()

    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)

    if options.debug:
        logger.setLevel(logging.DEBUG)

    # I can't imagine anything other than the flac dir..., but if we need to
    # expand we can
    options.srcdir = "/home/data"
    dirs = [os.path.join(options.srcdir, "flac")]

    # if bme could be initialized without a file, this would get cleaner...

    for dir in dirs:
        for sourcefile in sourcefiles(dir):
            bme = pybme.bmefile(sourcefile.encode("utf-8", "ignore"))
            dirname = os.path.dirname(sourcefile.encode("utf-8", "ignore"))
            if (
                "tracknumber" in bme.flactags
                and bme.flactags["tracknumber"][0] == "1"
                and "discnumber" in bme.flactags
                and bme.flactags["discnumber"][0] == "1"
            ):
                if "Vinyl" in bme.flactags["media"][0]:
                    if "digitize_info" not in bme.flactags:
                        logger.warn("no digitize info: {0}".format(dirname))
                        continue
                    # if "JICO" not in bme.flactags["digitize_info"][0]:
                    #    logger.warn("Sumiko Pearl used: {0}".format(dirname))
                    #    continue
                    # if "TASCAM" in bme.flactags["digitize_info"][0]:
                    #    logger.warn("TASCAM ADC used: {0}".format(dirname))
                    #    continue


def sourcefiles(item):
    for root, dirs, files in os.walk(item):
        for f in files:
            filename, extension = os.path.splitext(f)
            if extension == ".flac" or extension == ".mp3":
                yield os.path.join(root, f)


if __name__ == "__main__":
    main()

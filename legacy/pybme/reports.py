#!/usr/bin/python3
# -*- coding: utf-8 -*-
# this file is public domain - more free than free
import os
import stat
import string
import logging
import pprint
from optparse import OptionParser
import pybme

logger = logging.getLogger()


def main():
    usage = "usage: %prog [options] file.flac|dir [...]"
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-d",
        "--debug",
        help="enable debugging (extreme verbosity) (false)",
        action="store_true",
        dest="debug",
        default=False,
    )
    parser.add_option(
        "-v",
        "--verbose",
        help="show some status while working (false)",
        action="store_true",
        dest="verbose",
        default=False,
    )

    (options, args) = parser.parse_args()
    options.done = 0

    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)

    if options.verbose:
        logger.setLevel(logging.INFO)
    if options.debug:
        logger.setLevel(logging.DEBUG)

    if len(args) == 0:
        return ()

    incoming = buildfilelist(args)
    incoming = list(set(incoming))  # remove duplicates

    options.count = len(incoming)
    logger.info("found %d files" % (options.count))
    incoming.sort()

    tags = {}
    for filename in incoming:
        bme = pybme.bmefile(filename)
        if "tag" in bme.flactags:
            for t in bme.flactags["tag"]:
                if t not in tags:
                    tags[t] = 1
                else:
                    tags[t] = tags[t] + 1
    pprint.pprint(tags)


def buildfilelist(args):
    srcfiles = []
    for item in args:
        try:
            iteminfo = os.stat(item)
        except (IOError, OSError):
            logger.warn("File not found: %s" % (item))
            continue

        if stat.S_ISREG(iteminfo.st_mode):
            filename, extension = os.path.splitext(item)
            if extension == ".flac" or extension == ".mp3":
                srcfiles.append(os.path.realpath(item))
        if stat.S_ISDIR(iteminfo.st_mode):
            for root, dirs, files in os.walk(item):
                # logger.debug("%s %s %s" % (root, dirs, files))
                for f in files:
                    filename, extension = os.path.splitext(f)
                    if extension == ".flac" or extension == ".mp3":
                        srcfiles.append(os.path.realpath(os.path.join(root, f)))
    return srcfiles


if __name__ == "__main__":
    main()

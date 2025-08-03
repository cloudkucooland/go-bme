#!/usr/bin/python3
# -*- coding: utf-8 -*-
# written by Scot C. Bontrager, May 2015
# this file is public domain - more free than free
from builtins import str
import os
import sys
import logging

# import string, stat
import pybme
from optparse import OptionParser

logger = logging.getLogger()


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
    parser.add_option(
        "-n",
        "--dryrun",
        help="don't actually delete",
        action="store_true",
        dest="dryrun",
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
    parser.add_option(
        "-D",
        "--outputdirectory",
        help="output directory (/home/transcode)",
        action="store",
        type="string",
        dest="outdir",
        default="/home/transcode",
    )
    parser.add_option(
        "-F",
        "--sourcedirectory (searches .../flac and .../mp3)",
        help="directory containing the source files (/home/data)",
        action="store",
        type="string",
        dest="srcdir",
        default="/home/data",
    )
    parser.add_option(
        "-W",
        "--windows",
        help="force NTFS safe file names (false)",
        action="store_true",
        dest="windows",
        default=False,
    )

    (options, args) = parser.parse_args()

    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)

    if options.verbose:
        logger.setLevel(logging.INFO)
    if options.debug:
        logger.setLevel(logging.DEBUG)

    transcoded = []
    for root, dirs, files in os.walk(options.outdir):
        for f in files:
            filename, extension = os.path.splitext(f)
            if extension == ".mp3":
                transcoded.append(os.path.join(root, f))
    transcoded = list(set(transcoded))
    count = len(transcoded)
    sourcefilecount = 0
    logger.info("Found %d transcoded files" % (count))

    dirs = [os.path.join(options.srcdir, "flac"), os.path.join(options.srcdir, "mp3")]

    for dir in dirs:
        for sourcefile in sourcefiles(dir):
            logger.debug("checking %s" % sourcefile)
            sourcefilecount = sourcefilecount + 1
            bme = pybme.bmefile(sourcefile)
            oughttoexist = bme.transcodePath(options.outdir, options.windows)
            if oughttoexist and oughttoexist in transcoded:
                logger.debug("legit: %s" % oughttoexist)
                transcoded.remove(oughttoexist)

    logger.info(
        "transcoded: %d source: %d remainder: %d"
        % (count, sourcefilecount, len(transcoded))
    )
    transcoded.sort()
    for topurge in transcoded:
        if topurge.find("Podcasts") == -1:
            logger.info("purging: %s" % (topurge))
            try:
                if not options.dryrun:
                    os.remove(topurge)
            except OSError as e:
                logger.warn("purge failed: %s %s" % (e, topurge))
        else:
            logger.info("skipping: %s" % (topurge))


def sourcefiles(item):
    for root, dirs, files in os.walk(item):
        for f in files:
            filename, extension = os.path.splitext(f)
            if extension == ".flac" or extension == ".mp3":
                yield str(os.path.join(root, f))


if __name__ == "__main__":
    main()

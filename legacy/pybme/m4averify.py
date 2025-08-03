#!/usr/bin/python3
# -*- coding: utf-8 -*-
# this file is public domain - more free than free
from builtins import str
import os

# import sys
# import datetime
# import string
import logging
from stat import S_ISREG, S_ISDIR
from subprocess import call, check_output
from optparse import OptionParser
from PIL import Image
from datetime import timedelta
import pybme
import shutil
import pprint

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
        "-D",
        "--outputdirectory",
        help="output directory (/home/data/alac)",
        action="store",
        type="string",
        dest="outdir",
        default="/home/data/alac",
    )
    parser.add_option(
        "-L",
        "--ffmpeg",
        help="path to ffmpeg (/usr/bin/ffmpeg)",
        action="store",
        type="string",
        dest="ffmpeg",
        default="/usr/bin/ffmpeg",
    )
    parser.add_option(
        "-V",
        "--verify",
        help="verify m4a times are +/- 1 second of flac (false)",
        action="store_true",
        dest="verify",
        default=False,
    )

    (options, args) = parser.parse_args()
    options.done = 0

    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)

    if options.debug:
        logger.setLevel(logging.DEBUG)

    if len(args) == 0:
        return ()

    incoming = buildfilelist(args)
    incoming = list(set(incoming))  # remove duplicates

    options.count = len(incoming)
    logger.warn("%d flac files" % (options.count))
    incoming.sort()

    outfiles = []
    for filename in incoming:
        options.done = options.done + 1
        bme = pybme.bmefile(filename)
        tags = bme.flactom4a()
        # doing it like this saves some overhead from pprint
        if options.debug:
            logger.debug(pprint.pprint(tags))
        if bme.filetype == "flac":
            outfiles.append(verify(bme, tags, options))

    logger.warn("%d alac files" % len(outfiles))
    distinct = list(set(outfiles))
    logger.warn("%d alac files without duplicates" % len(distinct))

    for fn in distinct:
        outfiles.remove(fn)

    for filename in outfiles:
        logger.warn(filename)

# not a generator since sorting is handy
def buildfilelist(args):
    srcfiles = []
    for item in args:
        try:
            iteminfo = os.stat(item)
        except (IOError, OSError):
            logger.warn("File not found: %s" % (item))
            continue

        if S_ISREG(iteminfo.st_mode):
            filename, extension = os.path.splitext(item)
            if extension == ".flac" or extension == ".m4a":
                srcfiles.append(os.path.realpath(item))
        if S_ISDIR(iteminfo.st_mode):
            for root, dirs, files in os.walk(item):
                for f in files:
                    filename, extension = os.path.splitext(f)
                    if extension == ".flac" or extension == ".m4a":
                        srcfiles.append(os.path.realpath(os.path.join(root, f)))
    return srcfiles


def verify(bme, tags, options):
    outfile = bme.transcodePath(options.outdir, False, "m4a")
    if not outfile:
        return
    logger.debug("output file: %s", outfile)

    if os.path.exists(outfile) == False:
        logger.warn("missing: %s" % (outfile))
        return outfile

    try:
        m4ainfo = os.stat(outfile)
    except (IOError, OSError) as e:
        logger.warn("unable to stat: %s" % (e))
        return outfile

    if options.verify:
        try:
            verify = MP4(outfile)
            if (
                abs(
                    timedelta(seconds=bme.flactags.info.length).seconds
                    - timedelta(seconds=verify.info.length).seconds
                )
                > 1
            ):
                logger.warn(
                    "time mismatch: expected: %s got: %s for: %s"
                    % (
                        timedelta(seconds=bme.flactags.info.length),
                        timedelta(seconds=verify.info.length),
                        outfile,
                    )
                )
        except Exception as e:
            logger.warn("Error opening m4a for verification: %s (%s)" % (outfile, e))
            return outfile
            
    return outfile


if __name__ == "__main__":
    main()

#!/usr/bin/python3
# -*- coding: utf-8 -*-
# written by Scot C. Bontrager, May 2015
# this file is public domain - more free than free
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
        "-D",
        "--outputdirectory",
        help="output directory (/home/data/tmp)",
        action="store",
        type="string",
        dest="outdir",
        default="/home/data/tmp",
    )

    (options, args) = parser.parse_args()

    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    if options.debug:
        logger.setLevel(logging.DEBUG)

    options.srcdir = "/home/data"
    dirs = [os.path.join(options.srcdir, "flac"), os.path.join(options.srcdir, "mp3")]

    for dir in dirs:
        for sourcefile in sourcefiles(dir):
            logger.debug("checking %s" % sourcefile)
            bme = pybme.bmefile(sourcefile.encode("utf-8", "ignore"))
            if "musicbrainz_trackid" in bme.flactags:
                if "lyrics" not in bme.flactags or "[...]" in bme.flactags["lyrics"][0]:
                    wd = os.path.join(
                        options.outdir,
                        "%s" % (bme.flactags["musicbrainz_trackid"][0][:1]),
                    )
                    if not os.path.exists(wd):
                        logger.info("making directory: %s" % wd)
                        os.makedirs(wd)
                    lp = os.path.join(
                        wd,
                        "%s.%s"
                        % (bme.flactags["musicbrainz_trackid"][0], bme.filetype),
                    )
                    if not os.path.exists(lp):
                        logger.info("linking %s to %s" % (lp, sourcefile))
                        os.link(sourcefile, lp)


def sourcefiles(item):
    for root, dirs, files in os.walk(item):
        for f in files:
            filename, extension = os.path.splitext(f)
            if extension == ".flac" or extension == ".mp3":
                yield os.path.join(
                    root.decode("utf-8", "ignore"), f.decode("utf-8", "ignore")
                )


if __name__ == "__main__":
    main()

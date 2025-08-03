#!/usr/bin/python3
# -*- coding: utf-8 -*-

from optparse import OptionParser
import logging
import os
import stat
import pprint
import pybme


def main():
    usage = "usage: %prog [options] file|directory ..."
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-d",
        "--debug",
        help="enable debugging (more verbosity) (false)",
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
    parser.add_option(
        "-m",
        "--ID3",
        help="show ID3 tags (false)",
        action="store_true",
        dest="showid3",
        default=False,
    )
    parser.add_option(
        "-4",
        "--MP4",
        help="show mp4 tags (false)",
        action="store_true",
        dest="showmp4",
        default=False,
    )
    parser.add_option(
        "-g",
        "--search-tag",
        help="search for and print a specific tag",
        action="store",
        type="string",
        dest="searchtag",
    )

    (options, args) = parser.parse_args()
    if len(args) == 0:
        return ()

    logging.captureWarnings(True)
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(name)-12s %(levelname)-8s %(message)s")
    # handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)

    if options.verbose:
        logger.setLevel(logging.INFO)
    if options.debug:
        logger.setLevel(logging.DEBUG)

    found = []
    for item in args:
        f = buildfilelist(item)
        found = found + f

    for file in found:
        logger.info("%s" % (file))
        bme = pybme.bmefile(file)
        if options.searchtag:
            if options.searchtag in bme.flactags:
                print("%s=%s" % (options.searchtag, bme.flactags[options.searchtag]))
        else:
            for k, v in list(bme.flactags.items()):
                print("%s=%s" % (k, pprint.pformat(v)))
        if options.showid3:
            mp3tags = bme.flactoid3()
            print("\nID3 Tags:")
            for k, v in list(mp3tags.items()):
                print("%s" % (pprint.pformat(v)))
        if options.showmp4:
            m4atags = bme.flactom4a()
            print("\nMP4 Tags:")
            for k, v in list(m4atags.items()):
                print("%s" % (pprint.pformat(v)))
        print("")


def buildfilelist(item):
    gotit = []

    try:
        iteminfo = os.stat(item)
    except (IOError, OSError):
        logging.warn("File not found: %s" % (item))
        return ()
    if stat.S_ISREG(iteminfo.st_mode):
        fn, fe = os.path.splitext(item)
        if fe == ".flac" or fe == ".mp3":
            gotit.append(os.path.realpath(item))
    if stat.S_ISDIR(iteminfo.st_mode):
        for root, dirs, files in os.walk(item):
            for f in files:
                fn, fe = os.path.splitext(f)
                if fe == ".flac" or fe == ".mp3":
                    gotit.append(os.path.realpath(os.path.join(root, f)))
    return gotit


if __name__ == "__main__":
    main()

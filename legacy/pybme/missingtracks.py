#!/usr/bin/python3
# -*- coding: utf-8 -*-
# this file is public domain - more free than free
from builtins import object
import os
import stat
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
        return

    incoming = buildfilelist(args, options)
    incoming = list(set(incoming))  # remove duplicates

    options.count = len(incoming)
    logger.info("found %d files" % (options.count))
    incoming.sort()

    albums = {}
    for filename in incoming:
        bme = pybme.bmefile(filename)
        if "musicbrainz_albumid" not in bme.flactags:
            continue
        key = bme.flactags["musicbrainz_albumid"][0]
        if key in albums:
            tmp = albums[key]
        else:
            if "disctotal" not in bme.flactags:
                logger.warn("disctotal missing from %s" % (filename))
                dt = 1
            else:
                dt = int(bme.flactags["disctotal"][0])
            tmp = album(
                "%s - %s" % (bme.flactags["artist"][0], bme.flactags["album"][0]), dt
            )
            albums[key] = tmp

        if "discnumber" not in bme.flactags:
            logger.warn("discnumber missing from %s" % (filename))
            dn = 0
        else:
            dn = int(bme.flactags["discnumber"][0])

        if "tracknumber" not in bme.flactags:
            logger.warn("tracknumber missing from %s" % (filename))
            tn = 0
        else:
            tn = int(bme.flactags["tracknumber"][0])

        if "tracktotal" not in bme.flactags:
            logger.warn("tracktotal missing from %s" % (filename))
            tt = 0
        else:
            tt = int(bme.flactags["tracktotal"][0])

        tmp.addtrack(dn, tn, tt)

    for k in list(albums.keys()):
        albums[k].tally()


class album(object):
    def __init__(self, name, disccount):
        self.albumname = name
        self.discs = []
        self.expected = []
        i = 0
        while i <= disccount:
            self.expected.append(0)
            self.discs.append([])
            i = i + 1

    def addtrack(self, discnumber, tracknumber, tracktotal):
        if self.expected[discnumber] != 0:
            if self.expected[discnumber] != tracktotal:
                logger.warn(
                    "%s: tracktotal changed?! %s/%s"
                    % (self.albumname, self.expected[discnumber], tracktotal)
                )
        else:
            self.expected[discnumber] = tracktotal
        self.discs[discnumber].append(tracknumber)

    def tally(self):
        totalexpected = 0
        for x in self.expected:
            totalexpected = totalexpected + x
        actual = 0
        for x in self.discs:
            actual = actual + len(x)

        if actual != totalexpected:
            logger.warn("%s: %s/%s" % (self.albumname, actual, totalexpected))
            logger.warn(pprint.pprint(self.discs))


def buildfilelist(args, options):
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

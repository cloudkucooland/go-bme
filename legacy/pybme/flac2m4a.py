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
        "-a",
        "--artcachedir",
        help="art cache directory (/home/data/bme-working/art-downloads)",
        action="store",
        type="string",
        dest="artcachedir",
        default="/home/data/bme-working/art-downloads",
    )
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
        help="do not actually save the new tags",
        action="store_true",
        dest="dryrun",
        default=False,
    )
    parser.add_option(
        "-r",
        "--retag",
        help="retag all files, ignoring times (false)",
        action="store_true",
        dest="retag",
        default=False,
    )
    parser.add_option(
        "-t",
        "--touch",
        help="touch files not retagged (false)",
        action="store_true",
        dest="touch",
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
        "-x",
        "--imagesize",
        help="thumbnail max aspect ratio (500)",
        action="store",
        type="string",
        dest="imagesize",
        default="500",
    )
    parser.add_option(
        "-C",
        "--artfilename",
        help="cover art filename (cover.jpg)",
        action="store",
        type="string",
        dest="coverart",
        default="cover.jpg",
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
        "-F",
        "--flac",
        help="path to flac (/usr/bin/flac)",
        action="store",
        type="string",
        dest="flac",
        default="/usr/bin/flac",
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
        "-R",
        "--rebuild",
        help="delete and rebuild transcoded files (false)",
        action="store_true",
        dest="rebuild",
        default=False,
    )
    parser.add_option(
        "-V",
        "--verify",
        help="verify m4a times are +/- 1 second of flac (false)",
        action="store_true",
        dest="verify",
        default=False,
    )
    parser.add_option(
        "-W",
        "--windows",
        help="use NTFS safe file names (false)",
        action="store_true",
        dest="windows",
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

    for filename in incoming:
        options.done = options.done + 1
        bme = pybme.bmefile(filename)
        tags = bme.flactom4a()
        # doing it like this saves some overhead from pprint
        if options.debug:
            logger.debug(pprint.pprint(tags))
        if bme.filetype == "flac":
            transcode(bme, tags, options)


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


def transcode(bme, tags, options):
    outfile = bme.transcodePath(options.outdir, options.windows, "m4a")
    if not outfile:
        return
    logger.debug("output file: %s", outfile)

    if options.rebuild:
        logger.info("rebuilding: %s" % (outfile))
        try:
            if not options.dryrun:
                os.remove(outfile)
        except OSError:
            logger.warn("rebuild failed to remove: %s" % (outfile))

    newfile = False
    if os.path.exists(outfile) == False and options.dryrun != True:
        newfile = True
        try:
            logger.info("encoding: %s" % (outfile))
            out = check_output( [ options.ffmpeg, "-hide_banner", "-loglevel", "error", "-i", bme.filename, "-c:v", "copy", "-c:a", "alac", outfile, ])
        except OSError as e:
            logger.warn("unable to transcode: %s %s" % (bme.filename, e))
            return ()

    if os.path.exists(outfile) == False:
        logger.warn("transcoded failed: %s" % (outfile))
        return ()

    try:
        m4ainfo = os.stat(outfile)
    except (IOError, OSError) as e:
        logger.warn("unable to stat: %s" % (e))
        return ()

    flacdir = os.path.dirname(bme.filename)
    flacartfile = os.path.join(flacdir, options.coverart)
    hasflacart = os.path.exists(flacartfile)
    if hasflacart:
        try:
            flacartinfo = os.stat(flacartfile)
        except (IOError, OSError):
            logger.warn("unable to stat: %s"(e))

    if hasflacart and "musicbrainz_albumid" in bme.flactags:
        artcachefile = os.path.join(
            options.artcachedir,
            str("zz-" + bme.flactags["musicbrainz_albumid"][0] + ".jpg"),
        )
        # XXX recreate if flacartfile is newer than artcachefile
        if os.path.exists(artcachefile) == False:
            logger.debug("did not find artcachefile: %s" % (artcachefile))
            try:
                thumbnail = Image.open(flacartfile)
                size = (int(options.imagesize), int(options.imagesize))
                thumbnail.thumbnail(size, resample=Image.ANTIALIAS)
                thumbnail.save(artcachefile, "JPEG")
            except (IOError, IndexError) as e:
                logger.warn(
                    "failed to create artcachefile: %s %s %s"
                    % (artcachefile, flacartfile, e)
                )

    try:
        flacinfo = os.stat(bme.filename)
    except (IOError, OSError):
        logger.warn("File not found: %s" % (bme.filename))
        return

    if (
        flacinfo.st_mtime > m4ainfo.st_mtime
        or options.retag
        or newfile
        or (hasflacart and flacartinfo.st_mtime > m4ainfo.st_mtime)
    ):
        logger.info("tagging: %s (%d/%d)" % (outfile, options.done, options.count))
        try:
            if not options.dryrun:
                tags.save(outfile)
        except Exception as e:
            logger.warn("failed saving tags to: %s (%s)" % (outfile, e))

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
            return


if __name__ == "__main__":
    main()

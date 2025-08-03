#!/usr/bin/python3
# -*- coding: utf-8 -*-
from optparse import OptionParser
import os
import logging
import signal
import stat
import pybme

import urllib3
#import certifi
#import urllib3.contrib.pyopenssl

#urllib3.contrib.pyopenssl.inject_into_urllib3()
#urllib3.disable_warnings()
# httpconn = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())
#urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def main():
    # version = "20161107"
    signal.signal(signal.SIGALRM, timeouthandler)

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
        "-f",
        "--force",
        help="ignore existing images (false)",
        action="store_true",
        dest="force",
        default=False,
    )
    parser.add_option(
        "-l",
        "--lite",
        help="only get core data from MusicBrainz (false)",
        action="store_true",
        dest="lite",
        default=False,
    )
    parser.add_option(
        "-n",
        "--dryrun",
        help="don't actually update",
        action="store_true",
        dest="dryrun",
        default=False,
    )
    parser.add_option(
        "-t",
        "--tagscount",
        help="update when only freeform musicbrainz tags change",
        action="store_true",
        dest="tagsdocount",
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
        "-A",
        "--fetchart",
        help="fetch artwork (false)",
        action="store_true",
        dest="fetchart",
        default=False,
    )
    parser.add_option(
        "-B",
        "--artcache",
        help="art cache directory (/home/data/bme-working/art-downloads)",
        action="store",
        dest="artcache",
        default="/home/data/bme-working/art-downloads",
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
        help="output directory (/home/data)",
        action="store",
        type="string",
        dest="outdir",
        default="/home/data",
    )
    parser.add_option(
        "-G",
        "--no-discogs",
        help="do not fetch data from discogs (false)",
        action="store_false",
        dest="discogs",
        default=True,
    )
    parser.add_option(
        "-K",
        "--no-acousticbrainz",
        help="do not fetch AcousticBrainz data (false)",
        action="store_false",
        dest="acousticbrainz",
        default=True,
    )
    parser.add_option(
        "-N",
        "--no-musicbrainz",
        help="do not check for updates from MB",
        action="store_false",
        dest="mb",
        default=True,
    )
    parser.add_option(
        "-T",
        "--timeout",
        help="Timeout for HTTP requests (seconds)",
        action="store",
        type="int",
        dest="timeout",
        default=30,
    )
    parser.add_option(
        "-V",
        "--verify",
        help="verify file",
        action="store_true",
        dest="verify",
        default=False,
    )
    parser.add_option(
        "-W",
        "--windows",
        help="NTFS safe file names",
        action="store_true",
        dest="windows",
        default=False,
    )

    (options, args) = parser.parse_args()
    if len(args) == 0:
        return

    logging.captureWarnings(True)
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    # formatter = logging.Formatter('%(name)-12s %(levelname)-8s %(message)s')
    # handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARN)
    logging.getLogger("oauthlib.oauth1.rfc5849").setLevel(logging.WARN)
    logging.getLogger("musicbrainzngs").setLevel(logging.WARN)

    outfile = logging.FileHandler(filename="/tmp/curate", mode="a")
    outfile.setLevel(logging.INFO)
    logging.getLogger().addHandler(outfile)

    if options.verbose:
        logger.setLevel(logging.INFO)
    if options.debug:
        logger.setLevel(logging.DEBUG)
        # logging.getLogger("musicbrainzngs").setLevel(logging.DEBUG)

    found = []
    for item in args:
        foundfile = buildfilelist(item)
        found = found + foundfile

    # remove duplicates
    found = list(set(found))
    logger.info("found %d files" % len(found))
    found.sort()

    for foundfile in found:
        # load the file and existing tags
        logger.debug(foundfile)
        bme = pybme.bmefile(foundfile)

        # preen and save any initial changes
        if bme.preentags() and options.dryrun == False:
            bme.savetags()

        # set up options
        bme.timeout = options.timeout
        bme.force = options.force
        bme.artcache = options.artcache
        bme.coverart = options.coverart
        bme.outdir = options.outdir
        bme.timeout = options.timeout
        bme.windows = options.windows
        bme.tagsdocount = options.tagsdocount

        changes = bme.updatetags(
            options.mb, options.lite, options.discogs,
        )

        # should this logic be in the class?
        if changes > 0 and options.dryrun == False:
            bme.savetags()

        # rename -- dryrun really should be taken care of here
        bme.renamefromtags(options.dryrun)

        if options.fetchart:
            bme.fetchart()
        if options.verify:
            bme.verify()


def buildfilelist(item):
    gotit = []

    try:
        iteminfo = os.stat(item)
    except (IOError, OSError):
        logging.warn("File not found: %s" % (item))
        return ()
    if stat.S_ISREG(iteminfo.st_mode):
        filename, extention = os.path.splitext(item)
        if extention == ".flac" or extention == ".mp3":
            gotit.append(os.path.realpath(item))
    if stat.S_ISDIR(iteminfo.st_mode):
        for root, dirs, files in os.walk(item):
            for found in files:
                filename, extention = os.path.splitext(found)
                if extention == ".flac" or extention == ".mp3":
                    gotit.append(os.path.realpath(os.path.join(root, found)))
    return gotit


def timeouthandler(signum, frame):
    raise Exception("timeout reached %s\n%s" % (signum, frame))


if __name__ == "__main__":
    main()

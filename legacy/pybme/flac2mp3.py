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
from subprocess import Popen, PIPE
from optparse import OptionParser
from PIL import Image
from datetime import timedelta
from mutagen.id3 import ID3, COMM, APIC

# from mutagen.mp3 import MPEGInfo
from mutagen.mp3 import MP3
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
        "-l",
        "--lameopts",
        help='(quoted) lame options ("--preset standard")',
        action="store",
        type="string",
        dest="lameopts",
        default="--preset standard",
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
        help="output directory (/home/transcode)",
        action="store",
        type="string",
        dest="outdir",
        default="/home/transcode",
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
        "--lame",
        help="path to lame (/usr/bin/lame)",
        action="store",
        type="string",
        dest="lame",
        default="/usr/bin/lame",
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
        "-S",
        "--sox",
        help="path to sox (/usr/bin/sox)",
        action="store",
        dest="sox",
        default="/usr/bin/sox",
    )
    parser.add_option(
        "-V",
        "--verify",
        help="verify mp3 times are +/- 1 second of flac (false)",
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
        tags = bme.flactoid3()
        # doing it like this saves some overhead from pprint
        if options.debug:
            logger.debug(pprint.pprint(tags))
        if bme.filetype == "flac":
            transcode(bme, tags, options)
        if bme.filetype == "mp3":
            outfile = bme.transcodePath(options.outdir, options.windows)
            if not outfile:
                continue
            # or this newer than that...
            if os.path.exists(outfile) == False or options.rebuild or options.retag:
                outfile = outfile.encode("utf-8")
                logger.info("copying %s %s" % (filename, outfile))
                shutil.copy(filename, outfile)
                domp3art(bme, outfile, options)


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
            if extension == ".flac" or extension == ".mp3":
                srcfiles.append(os.path.realpath(item))
        if S_ISDIR(iteminfo.st_mode):
            for root, dirs, files in os.walk(item):
                logger.debug("%s %s %s" % (root, dirs, files))
                for f in files:
                    filename, extension = os.path.splitext(f)
                    if extension == ".flac" or extension == ".mp3":
                        srcfiles.append(os.path.realpath(os.path.join(root, f)))
    return srcfiles


def transcode(bme, tags, options):
    outfile = bme.transcodePath(options.outdir, options.windows)
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
            if bme.flactags.info.channels > 2 and bme.flactags.info.sample_rate > 48000:
                logger.info("hi-res multi-channel: skipping: %s", (outfile))
                return ()
            if (
                bme.flactags.info.channels > 2
                and bme.flactags.info.sample_rate <= 48000
            ):  # == 6?
                logger.info("remixing 5.1 to stereo: %s", (outfile))
                proc1 = Popen(
                    [
                        options.sox,
                        "-c",
                        "6",
                        bme.filename,
                        "-t",
                        "wav",
                        "-",
                        "remix",
                        "-m",
                        "1v0.2929,3v0.2071,4v0.2071,5v0.2929",
                        "2v0.2929,3v0.2071,4v0.2071,6v0.2929",
                        "norm",
                    ],
                    stdout=PIPE,
                )
                # many guesses abound on the right coeff. to use
                # 1v0.3254,3v0.2301,5v0.2818,6v0.1627
                # 2v0.3254,3v0.2301,5v-0.1627,6v-0.2818 norm
            if (
                bme.flactags.info.sample_rate > 48000
                and bme.flactags.info.channels == 2
            ):
                logger.info(
                    "resampling (sox [rate -v -L -b 90 48000 dither]): %s", (outfile)
                )
                proc1 = Popen(
                    [
                        options.sox,
                        bme.filename,
                        "-t",
                        "wavpcm",
                        "-",
                        "rate",
                        "-v",
                        "-L",
                        "-b",
                        "90",
                        "48000",
                        "dither",
                    ],
                    stdout=PIPE,
                )
            if (
                bme.flactags.info.sample_rate <= 48000
                and bme.flactags.info.channels == 2
            ):
                proc1 = Popen(
                    [options.flac, "--silent", "-c", "-d", bme.filename], stdout=PIPE
                )
            lameopts = [options.lame, "--quiet", "--tt", bme.flactags["title"][0]]
            for opt in options.lameopts.split():
                lameopts.append(opt)
            lameopts.append("-")
            lameopts.append(outfile)
            logger.debug("encoding with lame: (%s) %s" % (str(lameopts), bme.filename))
            proc2 = Popen(lameopts, stdin=proc1.stdout, stdout=PIPE)
            proc1.stdout.close()
            procout = proc2.communicate()[0]
            proc2.wait()  # necessary?
            logger.debug(procout)
        except OSError as e:
            logger.warn("unable to transcode: %s %s" % (bme.filename, e))
            return ()

    if os.path.exists(outfile) == False:
        logger.warn("transcoded failed: %s" % (outfile))
        return ()

    try:
        mp3info = os.stat(outfile)
    except (IOError, OSError) as e:
        logger.warn("unable to stat: %s" % (e))
        return ()

    # preserve the playlists - format defined by an applescript found in the
    # wild
    # if not newfile:
    #    try:
    #        oldtags = ID3(outfile)
    #        oldcomments = oldtags.getall('COMM:')
    #    except Exception as e:
    #        logger.warn("Error reading old tags: %s (%s)" % (outfile, e))
    #        oldcomments = {}
    #    for c in oldcomments:
    #        tmp = unicode(c)
    #        logger.debug(u'Old comment: %s' % (tmp))
    #        bullits = tmp.split(u'·', 2)
    #        if len(bullits) > 1:
    #            carets = bullits[1].split(u'^')
    #            for bunk in [u'Music', u'90’s Music', 'unchecked-dumb']:
    #                if bunk in carets:
    #                    carets.remove(bunk)
    #            carets.sort()
    #            tmp = u'·Music' + u'^'.join(carets) + u'^'
    #            logger.debug(u'preserving iTunes comment: %s' % (tmp))
    #            tags.add(COMM(encoding=3, desc=u'', text=("%s" % tmp)))
    #            if 'iTunesCOMM' not in bme.flactags or tmp != bme.flactags[
    #                    'iTunesCOMM'][0]:
    #                logger.info(
    #                    u'backing up iTunesCOMM to %s: %s' %
    #                    (bme.filename, tmp))
    #                bme.flactags['iTunesCOMM'] = tmp
    # bme.savetags(bme.filename);

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
                # size = (options.imagesize, options.imagesize)
                size = (int(options.imagesize), int(options.imagesize))
                thumbnail.thumbnail(size, resample=Image.ANTIALIAS)
                thumbnail.save(artcachefile, "JPEG")
            except (IOError, IndexError) as e:
                logger.warn(
                    "failed to create artcachefile: %s %s %s"
                    % (artcachefile, flacartfile, e)
                )

        logger.debug("adding art: %s %s" % (artcachefile, outfile))
        try:
            tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=open(artcachefile, "rb").read(),
                )
            )
        except IOError as e:
            logger.warn("failed to add art: %s %s %s" % (artcachefile, outfile, e))

    try:
        flacinfo = os.stat(bme.filename)
    except (IOError, OSError):
        logger.warn("File not found: %s" % (bme.filename))
        return

    if (
        flacinfo.st_mtime > mp3info.st_mtime
        or options.retag
        or newfile
        or (hasflacart and flacartinfo.st_mtime > mp3info.st_mtime)
    ):
        logger.info("tagging: %s (%d/%d)" % (outfile, options.done, options.count))
        try:
            if not options.dryrun:
                tags.save(outfile)
        except Exception as e:
            logger.warn("failed saving tags to: %s (%s)" % (outfile, e))

    if options.verify:
        try:
            verify = MP3(outfile)
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
            logger.warn("Error opening mp3 for verification: %s (%s)" % (outfile, e))
            return
    return  # transcode


def domp3art(bme, outfile, options):
    indir = os.path.dirname(bme.filename)
    artfile = os.path.join(indir, options.coverart)
    hasart = os.path.exists(artfile)

    if not hasart:
        return False

    try:
        artinfo = os.stat(artfile)
    except (IOError, OSError):
        logger.warn("unable to stat: %s %s"(e, artfile))
        return False

    if "musicbrainz_albumid" in bme.flactags:
        artcachefile = os.path.join(
            options.artcachedir,
            str(bme.flactags["musicbrainz_albumid"][0] + ".jpg"),
        )
        if os.path.exists(artcachefile) == False:
            logger.debug("did not find artcachefile: %s" % (artcachefile))
            try:
                thumbnail = Image.open(artfile)
                size = (int(options.imagesize), int(options.imagesize))
                thumbnail.thumbnail(size, resample=Image.ANTIALIAS)
                thumbnail.save(artcachefile, "JPEG")
            except (IOError, IndexError) as e:
                logger.warn(
                    "failed to create artcachefile: %s %s %s"
                    % (artcachefile, artfile, e)
                )
                return False
            except Exception as e:
                logger.warn("creating artcachefile: %s" % e)
                return False

    try:
        outfileinfo = os.stat(outfile)
    except (IOError, OSError):
        logger.warn("File not found: %s" % (bme.filename))
        return False

    logger.debug("adding art: %s %s" % (artcachefile, outfile.decode("utf-8")))
    try:
        tags = ID3(outfile)
        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=open(artcachefile, "rb").read(),
            )
        )
        tags.save(outfile)
    except IOError as e:
        logger.warn(
            "failed to add art: %s %s %s" % (artcachefile, outfile.decode("utf-8"), e)
        )


if __name__ == "__main__":
    main()

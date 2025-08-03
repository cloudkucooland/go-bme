# -*- coding: utf-8 -*-
# this file is public domain - more free than free

from builtins import input
from builtins import map
from builtins import str
from builtins import object
#from past.utils import old_div
import os

# import sys
import string
import musicbrainzngs
import pprint

# import json
import datetime
import logging
import signal
import tempfile
import filecmp
import shutil
import struct

# import io
import time

# import urllib
import requests
import discogs_client
import pickle
# import acoustid

# import stat
import subprocess
import fnmatch

# from optparse import OptionParser
from mutagen.flac import FLAC

# don't do it this way, import mutagen.id3 and then use id3.TXXX
from mutagen.id3 import ID3, TPE1, TSOP, TPE2, TXXX, TSOA, TALB, TBPM, COMM
from mutagen.id3 import TCMP, TCOM, TPE3, TCOP, TDRC, TPOS, TCON, TIT1, TIT2, TIT3, TSRC
from mutagen.id3 import TPUB, TLAN, TMED, TDOR, TKEY, TEXT, TOLY, TRCK, TMOO
from mutagen.id3 import TPE4, TIPL, TSST, USLT, UFID, TMCL, TSOC, TSO2, WXXX

# from mutagen.id3 import APIC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Tags

# from mutagen.mp3 import MPEGInfo
from datetime import timedelta
# from PIL import Image
from io import BytesIO
import pybme_lists

_log = logging.getLogger(__name__)
_log.addHandler(logging.NullHandler())
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


def setupOAuth(progname, version):
    client_key = r"xhmnqdaDHkxcOCsBEagU"
    client_secret = r"QfOZtTwcloXWkEpNkVNXOrqTrCBrXOct"

    discogs = discogs_client.Client(
        "%s/%s +http://www.indievisible.org/bme/" % (progname, version),
        consumer_key=client_key,
        consumer_secret=client_secret,
    )
    # return discogs

    # urllib3/requests busted this https://github.com/sampsyo/beets/issues/1656
    cachefile = os.path.join(
        os.path.expanduser("~"), ".config", "bme", "curate.discogs"
    )
    if os.path.exists(cachefile):
        # print "using cached discogs auth data (%s)",  cachefile
        with open(cachefile, "rb") as f:
            discogs = pickle.load(f)
    else:
        print("discogs auth data not cached, setting up")
        (request_token, request_secret, authorize_url) = discogs.get_authorize_url()
        print(("Please go here and authorize this session: ", authorize_url))
        verifier = eval(input("Verifyer Code: "))
        (access_token, access_secret) = discogs.get_access_token(verifier)
        with open(cachefile, "wb") as f:
            pickle.dump(discogs, f)
    me = discogs.identity()
    print(("authenticated to discogs as %s" % (me.username)))
    return discogs


class bmefile(object):
    progname = "bme-curate"
    version = "20151128"
    musicbrainzngs.set_useragent(progname, version, "http://www.indievisible.org/bme/")
    dgclient = setupOAuth(progname, version)
    lists = pybme_lists.bme_lists()
    dgcache = {}
    mbcache = {}
    global azsleep
    azsleep = 0.8

    def __init__(self, file):
        self.headers = {"User-Agent": str("%s %s" % (self.progname, self.version))}
        self.artcache = "/home/data/bme-working/art-downloads"
        self.coverart = "cover.jpg"
        self.outdir = "/home/data"
        self.force = False
        self.timeout = 30
        self.windows = False
        self.url_discogs_release_image = False
        self.flactags = dict()
        self.newtags = dict()
        self.acoustid = False
        self.submitacoustid = False
        self.length = 0
        self.mbcachesize = 100
        self.tagsdocount = False

        self.filename = file #.decode("utf-8", "ignore")
        #_log.debug(self.filename)
        fn, fe = os.path.splitext(self.filename)
        if fe == ".flac":
            self.__loadflac()
            self.filetype = "flac"
        if fe == ".mp3":
            self.__loadmp3()
            self.filetype = "mp3"
        # _log.debug(pprint.pformat(self.flactags))
        return

    def __loadflac(self):
        try:
            self.flactags = FLAC(self.filename)
            self.length = self.flactags.info.length
        except Exception as e:
            _log.error("Error reading tags from: %s %s" % (self.filename, e))

    def __loadmp3(self):
        try:
            tmp = MP3(self.filename)
            mp3tags = tmp.tags
            self.length = tmp.info.length
        except Exception as e:
            _log.error("Error reading tags from: %s %s" % (self.filename, e))
        self.id3toflac(mp3tags)

    def updatetags(self, mb, lite, discogs):
        changes = 0

        if not mb:
            self.newtags = dict(self.flactags)
        else:
            self.fetchtagfrommb(lite)

        if len(self.newtags) < 1:
            if (
                "tracknumber" in self.flactags
                and self.flactags["tracknumber"][0] == "1"
            ):
                _log.warn("MusicBrainz returned empty tags")
            return changes

        if discogs:
            if "url_discogs_release_site" in self.newtags:
                self.fetchDiscogs()
            else:
                self.findDiscogs()

        if (
            self.acoustid
            and ("acoustid_id" not in self.flactags or self.force)
            and self.length > 30
        ):
            self.scanacousticbrainz()

        if (
            self.submitacoustid
            and "acoustid_id" not in self.newtags
            and "acoustid_fingerprint" in self.newtags
            and "musicbrainz_recordingid" in self.newtags
        ):
            self.submitacousticbrainz()

        for k, v in list(self.newtags.items()):
            # _log.warn("checking %s" % (k))
            if (
                k not in self.flactags
                and len(self.newtags[k]) > 0
                and len(self.newtags[k][0]) > 0
            ):
                changes = changes + 1
                _log.warn("[%s] unset -> %s" % (k, self.newtags[k]))
                self.flactags[k] = self.newtags[k]
                continue
            if len(self.newtags[k]) > 1:
                try:
                    if sorted(self.flactags[k]) != sorted(self.newtags[k]):
                        if k == "tag":
                            if self.tagsdocount is True:
                                changes = changes + 1
                                _log.warn(
                                    "[%s] %s -> %s"
                                    % (
                                        k,
                                        sorted(self.flactags[k]),
                                        sorted(self.newtags[k]),
                                    )
                                )
                        else:
                            changes = changes + 1
                            _log.warn(
                                "[%s] %s -> %s" % (k, self.flactags[k], self.newtags[k])
                            )
                        self.flactags[k] = self.newtags[k]
                except Exception as e:
                    _log.warn("tag %s threw error %s %s" % (k, e, self.filename))
            else:
                if k in self.flactags and self.flactags[k] != self.newtags[k]:
                    changes = changes + 1
                    _log.warn("[%s] %s -> %s" % (k, self.flactags[k], self.newtags[k]))
                    self.flactags[k] = self.newtags[k]
        # _log.debug(pprint.pformat(self.newtags))
        # _log.debug(pprint.pformat(self.flactags))

        # if it was album, not track...
        # if "asin" in self.flactags and "asin" not in self.newtags:
        #    _log.warn("[asin] %s -> unset" % (self.flactags["asin"]))
        #    del self.flactags["asin"]
        #    changes = changes + 1

        # XXX build a list of deletable tags and cycle through looking for new absences
        # if "url_discogs_release_site" in self.flactags and "url_discogs_release_site" not in self.newtags:
        #    _log.warn("[url_discogs_release_site] %s -> unset" % (self.flactags["url_discogs_release_site"]))
        #    del self.flactags["url_discogs_release_site"]
        #    changes = changes + 1

        if changes > 0:
            _log.warn("%d changes: %s" % (changes, self.filename))
        return changes

    def preentags(self):
        changes = False
        if "artist" not in self.flactags:
            _log.warn("artist not set: %s" % (self.filename))
            self.flactags["artist"] = ["Unknown Artist"]

        if "album" not in self.flactags:
            _log.warn("album not set: %s" % (self.filename))
            self.flactags["album"] = ["Unknown Album"]

        if "media" not in self.flactags:
            _log.warn("media unset: %s" % (self.filename))
            self.flactags["media"] = ["unknown"]
            changes = True

        if "title" in self.flactags and "musicbrainz_albumid" in self.flactags:
            # _log.warn("title %s: %s" % (self.flactags["title"], self.flactags["musicbrainz_albumid"]))
            if '"' in self.flactags["title"][0]:
                _log.info(
                    'http://musicbrainz.org/release/%s/edit : a title contains "'
                    % (self.flactags["musicbrainz_albumid"][0])
                )
            if "'" in self.flactags["title"][0]:
                _log.debug(
                    "http://musicbrainz.org/release/%s/edit : a title contains '"
                    % (self.flactags["musicbrainz_albumid"][0])
                )

        if "genre" in self.flactags:
            newgenre = []
            for g in self.flactags["genre"]:
                if g in self.lists.validgenre:
                    newgenre.append(g)
                else:
                    _log.warn(
                        "preen: removing unknown genre [%s]: %s " % (g, self.filename)
                    )
            if sorted(newgenre) != sorted(self.flactags["genre"]):
                self.flactags["genre"] = newgenre
                changes = True

        if "grouping" in self.flactags:
            newgenre = []
            for g in self.flactags["grouping"]:
                if g in self.lists.validgrouping:
                    newgenre.append(g)
                else:
                    _log.warn(
                        "preen: removing unknown grouping [%s]: %s "
                        % (g, self.filename)
                    )
            if sorted(newgenre) != sorted(self.flactags["grouping"]):
                self.flactags["grouping"] = newgenre
                changes = True

        # XXX unfinished
        if "tag" in self.flactags:
            nt = []
            for t in self.flactags["tag"]:
                if ";" in t:
                    _log.warn("preen: splitting tag %s: %s" % (t, self.filename))
                    for chunk in t.split(";"):
                        if chunk not in self.lists.bogustags:
                            nt.append(chunk)
                        else:
                            _log.warn(
                                "preen: removing bogus chunk %s: %s"
                                % (chunk, self.filename)
                            )
                else:
                    if t not in self.lists.bogustags and "_" not in t:
                        nt.append(t)
                    else:
                        _log.warn(
                            "preen: removing bogus tag %s: %s" % (t, self.filename)
                        )
            if sorted(nt) != sorted(self.flactags["tag"]):
                _log.warn("[tag] %s -> %s" % (self.flactags["tag"], nt))
                self.flactags["tag"] = nt
                changes = True

        for old, new in list(self.lists.rename.items()):
            if old in self.flactags:
                for tag in self.flactags[old]:
                    _log.warn(
                        "preen: renaming [%s] to [%s]: %s" % (old, new, self.filename)
                    )
                    if new not in self.flactags:
                        self.flactags[new] = [tag]
                    else:
                        self.flactags[new].append(tag)
                del self.flactags[old]
                changes = True

        for tag in self.lists.bogus:
            if tag in self.flactags:
                _log.warn("preen: removing bogus tag %s: %s" % (tag, self.filename))
                del self.flactags[tag]
                changes = True

        for tag in self.flactags:
            if tag not in self.lists.known:
                _log.warn(
                    "preen: ignoring unknown tag [%s] [%s]: %s"
                    % (tag, self.flactags[tag], self.filename)
                )

        # which of the replaygain tags to check?
        # check for "89db" ?
        # if there is a sample-rate or bit-depth change in the files (DVDs or downloads)
        # metaflac should be run manually
        if (
            self.filetype == "flac"
            and "replaygain_reference_loudness" not in self.flactags
            and self.flactags.info.channels < 3
            and "discnumber" in self.flactags
        ):
            a = ["/bin/metaflac", "--add-replay-gain"]
            dirname = os.path.dirname(self.filename)
            _log.warn("preen: fixing incomplete replaygain for: %s" % (dirname))
            for f in os.listdir(dirname):
                if fnmatch.fnmatch(f, format("%s*.flac" % self.flactags["discnumber"])):
                    a.append(str("%s/%s" % (dirname, f)))
            # _log.debug(a)
            subprocess.call(a)

        # make sure flac version is current
        # if self.flactags["vendor"] not in [ "reference libFLAC 1.2.1 20070917", "reference libFLAC 1.3.0 20130526"]:
        #    _log.warn("odd flac version:", self.filename, file=sys.stderr)

        # XXX run through flac to verify file inegrity
        # XXX run through sox to check for (inter sample) clipping

        if "lyrics" in self.flactags and "[...]" in self.flactags["lyrics"][0]:
            _log.warn(
                "preen: removing junk lyrics in %s:\n%s "
                % (self.filename, self.flactags["lyrics"][0])
            )
            del self.flactags["lyrics"]
            changes = True

        return changes

    def savetags(self):
        if self.filetype == "flac":
            # should go in preen
            self.flactags.clear_pictures()
            self.flactags.save()
        if self.filetype == "mp3":
            # _log.critical("mp3 unsupported")
            self.flactoid3().save(self.filename)
        return

    # allow passing in root path as well so can be used for transcode?
    def renamefromtags(self, dryrun):
        if self.windows:
            bad = '/:*?;"<>|'
        else:
            bad = "/"

        if "artist" in self.flactags:
            bestartist = self.flactags["artist"][0]
        else:
            self.flactags["artist"] = "Unknown Artist"
            bestartist = "Unknown Artist"
        if "artistsort" in self.flactags:
            bestartist = self.flactags["artistsort"][0]
        if "albumartist" in self.flactags:
            bestartist = self.flactags["albumartist"][0]
        if "albumartistsort" in self.flactags:
            bestartist = self.flactags["albumartistsort"][0]

        if "album" in self.flactags:
            album = self.flactags["album"][0]
        else:
            album = ""

        if "date" in self.flactags:
            date = self.flactags["date"][0]
        else:
            date = ""

        if "media" in self.flactags:
            media = self.flactags["media"][0]
            if (
                "Vinyl" in self.flactags["media"][0]
                or "Flexi-disc" in self.flactags["media"][0]
            ):
                if "vinyldigitizer" in self.flactags:
                    digitizer = self.flactags["vinyldigitizer"][0]
                else:
                    digitizer = ""
                sr = ""
                if self.filetype == "flac":
                    sr = str(
                        "%dbit-%dkHz"
                        % (
                            self.flactags.info.bits_per_sample,
                            self.flactags.info.sample_rate / 1000,
                        )
                    )
                media = ";".join([media, sr, digitizer])
        else:
            media = ""

        if "releasecountry" in self.flactags:
            releasecountry = self.flactags["releasecountry"][0]
        else:
            releasecountry = ""

        if "label" in self.flactags:
            labels = "; ".join(self.flactags["label"])
        else:
            labels = ""
        if "catalognumber" in self.flactags:
            catalognumbers = "; ".join(self.flactags["catalognumber"])
        else:
            catalognumbers = ""

        if "discnumber" in self.flactags:
            discnumber = self.flactags["discnumber"][0]
        else:
            discnumber = "0"

        if "tracknumber" in self.flactags:
            if len(self.flactags["tracknumber"][0]) < 2:
                tracknumber = str("0%s" % (self.flactags["tracknumber"][0]))
            else:
                tracknumber = self.flactags["tracknumber"][0]
        else:
            tracknumber = "00"

        maxlen = 240 - len(self.outdir)
        bestname = "".join([(s in bad and "_") or s for s in bestartist])
        maxlen = maxlen - len(bestname)
        albumname = "".join(
            map(
                lambda s: (s in bad and "_") or s,
                str(
                    "%s [%s,%s,%s,%s,%s]"
                    % (album, date, media, releasecountry, labels, catalognumbers)
                ),
            )
        )
        maxlen = maxlen - len(albumname)

        if "title" in self.flactags:
            title = self.flactags["title"][0][:maxlen]
        else:
            title = "Unknown Track"

        outdir = os.path.join(
            self.outdir, self.filetype, bestname[0].upper(), bestname, albumname
        )
        if os.path.exists(outdir) == False:
            os.makedirs(outdir)
        trackname = "".join(
            map(
                lambda s: (s in bad and "_") or s,
                str("%s-%s %s.%s" % (discnumber, tracknumber, title, self.filetype)),
            )
        )
        outfile = os.path.join(outdir, trackname)

        if self.filename != outfile:
            if os.path.exists(outfile):
                _log.error(
                    "not moving since target already exists, duplicates? %s %s"
                    % (self.filename, outfile)
                )
            else:
                _log.warn("moving %s %s" % (self.filename, outfile))
                if not dryrun:
                    try:
                        os.rename(self.filename, outfile)
                    except Exception as e:
                        _log.error(
                            "failed to move %s to %s (%s)" % (self.filename, outfile, e)
                        )
                        return self.filename
                    for e in self.lists.rename_extras:
                        eOld = os.path.join(os.path.dirname(self.filename), e)
                        eNew = os.path.join(outdir, e)
                        if os.path.exists(eOld):
                            try:
                                os.rename(eOld, eNew)
                            except Exception as e:
                                _log.error(
                                    "failed to move extra file %s to %s (%s)"
                                    % (eOld, enew, e)
                                )
        self.filename = outfile

    def scanacousticbrainz(self):
        if "acoustid_id" in self.flactags:
            return
        if "musicbrainz_recordingid" not in self.flactags:
            return

        try:
            if "acoustid_fingerprint" in self.flactags:
                dur = self.length
                fp = self.flactags["acoustid_fingerprint"][0]
            else:
                _log.debug("acoustid fingerprinting: %s" % self.filename)
                dur, fp = acoustid.fingerprint_file(self.filename)
            self.newtags["acoustid_fingerprint"] = [fp]
            res = acoustid.lookup("79O94Yyl", fp, dur)
        except Exception as e:
            _log.error("acoustid scan failed: %s (%s)" % (self.filename, e))
            return

        if "results" in res and len(res["results"]) > 0:
            for item in res["results"]:
                if "recordings" in item:
                    for rec in item["recordings"]:
                        if rec["id"] == self.newtags["musicbrainz_recordingid"][0]:
                            if "acoustid_id" not in self.newtags:
                                self.newtags["acoustid_id"] = []
                            self.newtags["acoustid_id"].append(item["id"])

    def submitacousticbrainz(self):
        if "acoustid_id" in self.flactags:
            return
        if self.filetype != "flac":
            return

        if "acoustid_fingerprint" not in self.newtags:
            self.scanacousticbrainz()
        if "acoustid_fingerprint" not in self.newtags:
            return

        url = "http://api.acoustid.org/v2/submit"
        payload = {
            "format": "json",
            "client": "79O94Yyl",
            "clientversion": self.version,
            "wait": "10",
            "user": "6YMH5vEi",
            "duration.0": int(round(self.length)),
            "fingerprint.0": self.newtags["acoustid_fingerprint"][0],
            # "bitrate.0" : self.flactags.info.bitrate / 1000,
            "fileformat.0": "FLAC",  # self.filetype.toupper()
            "mbid.0": self.newtags["musicbrainz_recordingid"][0],
            "track.0": self.newtags["title"][0],
            "artist.0": self.newtags["artist"][0],
            "album.0": self.newtags["album"][0],
            "albumartist.0": self.newtags["albumartist"][0],
            "trackno.0": self.newtags["tracknumber"][0],
            "discno.0": self.newtags["discnumber"][0],
        }
        _log.warn("submitting fingerprint to acoustid: %s" % (self.filename))
        try:
            headers = dict(self.headers)
            signal.alarm(self.timeout)
            req = requests.get(
                url, params=payload, headers=headers, timeout=self.timeout
            )
            req.raise_for_status()
        except Exception as e:
            _log.critical(
                "acoustid submission threw an error: %s %s\n%s\n%s\n"
                % (e, self.filename, req.url, req.text)
            )
        finally:
            signal.alarm(0)
            # time.sleep(0.34)

    def fetchtagfrommb(self, lite):
        self.newtags = {}

        if "discnumber" not in self.flactags:
            _log.info("discnumber missing from: %s" % (self.filename))
            self.flactags["discnumber"] = ["0"]
        if "tracknumber" not in self.flactags:
            _log.info("tracknumber missing from: %s" % (self.filename))
            self.flactags["tracknumber"] = ["0"]

        if (
            "musicbrainz_albumid" in self.flactags
            and len(self.flactags["musicbrainz_albumid"][0]) == 36
        ):
            self.release_top(lite)
            if lite == False and len(self.newtags) < 1:
                _log.warn("failed to get release, trying lite: %s" % (self.filename))
                self.release_top(True)
            if (
                len(self.newtags) < 1
                and "musicbrainz_recordingid" in self.flactags
                and len(self.flactags["musicbrainz_recordingid"][0]) == 36
            ):
                _log.warn(
                    "failed to get release, trying per-track: %s" % (self.filename)
                )
                self.track_recording(
                    {"id": self.flactags["musicbrainz_recordingid"][0]}
                )
        else:
            if (
                "musicbrainz_recordingid" in self.flactags
                and len(self.flactags["musicbrainz_recordingid"][0]) == 36
            ):
                self.track_recording(
                    {"id": self.flactags["musicbrainz_recordingid"][0]}
                )
            else:
                _log.warn("no MusicBrainz tags in %s" % (self.filename))
                # return None

        if "preformatted_albumartist" in self.newtags:
            if "albumartist" in self.newtags:
                # remove duplicates
                self.newtags["albumartist"] = list(set(self.newtags["albumartist"]))
                if (
                    self.newtags["albumartist"][0]
                    != self.newtags["preformatted_albumartist"][0]
                ):
                    _log.debug(
                        "albumartist and preformatted_albumartist did not match: %s [%s] [%s]"
                        % (
                            self.filename,
                            self.newtags["albumartist"][0],
                            self.newtags["preformatted_albumartist"][0],
                        )
                    )
                    self.newtags["albumartist"] = self.newtags[
                        "preformatted_albumartist"
                    ]
            else:
                # _log.debug("albumartist not set, using preformatted_albumartist: %s" % self.filename)
                self.newtags["albumartist"] = self.newtags["preformatted_albumartist"]
            del self.newtags["preformatted_albumartist"]

        if "preformatted_artist" in self.newtags:
            if "artist" in self.newtags:
                # remove duplicates
                self.newtags["artist"] = list(set(self.newtags["artist"]))
                if self.newtags["artist"][0] != self.newtags["preformatted_artist"][0]:
                    _log.debug(
                        "artist and preformatted_artist did not match: %s [%s] [%s]"
                        % (
                            self.filename,
                            self.newtags["artist"][0],
                            self.newtags["preformatted_artist"][0],
                        )
                    )
                    self.newtags["artist"] = self.newtags["preformatted_artist"]
            else:
                self.newtags["artist"] = self.newtags["preformatted_artist"]
            del self.newtags["preformatted_artist"]

        if "recording_title" in self.newtags:
            if "title" in self.newtags:
                if self.newtags["title"][0] != self.newtags["recording_title"][0]:
                    # the only reason for a title is if it differs from the recording title...
                    _log.debug(
                        "title and recording-title do not match: %s (%s/%s)"
                        % (
                            self.filename,
                            self.newtags["title"][0],
                            self.newtags["recording_title"][0],
                        )
                    )
            else:
                self.newtags["title"] = [self.newtags["recording_title"][0]]
            del self.newtags["recording_title"]

        if "compilation" in self.newtags:
            if "musicbrainz_albumtype" not in self.newtags:
                self.newtags["musicbrainz_albumtype"] = []
            self.newtags["musicbrainz_albumtype"].append("compilation")
        if "media" in self.newtags:
            # double quote to double-prime for inches
            self.newtags["media"] = [str(self.newtags["media"][0].replace('"', "″"))]
        if "album" in self.newtags and "release_disambiguation" in self.newtags:
            self.newtags["album"] = [
                str(
                    "%s ❬%s❭"
                    % (
                        self.newtags["album"][0],
                        self.newtags["release_disambiguation"][0].lower(),
                    )
                )
            ]
            del self.newtags["release_disambiguation"]

        for k, v in list(self.newtags.items()):
            if len(self.newtags[k]) > 1:
                self.newtags[k] = list(set(self.newtags[k]))
        # _log.debug(pprint.pformat(self.newtags))

    def release_top(self, lite):
        if self.flactags["musicbrainz_albumid"][0] in self.mbcache:
            mb = self.mbcache[self.flactags["musicbrainz_albumid"][0]]
        else:
            if len(self.mbcache) > self.mbcachesize:
                _log.debug("MusicBrainz cache getting large: dumping")
                for k in list(self.mbcache.keys()):
                    del self.mbcache[k]
            try:
                if lite:
                    includes = ["artists", "labels", "recordings", "media", "url-rels"]
                else:
                    includes = [
                        "artists",
                        "labels",
                        "recordings",
                        "release-groups",
                        "media",
                        "artist-credits",
                        "isrcs",
                        "area-rels",
                        "artist-rels",
                        "label-rels",
                        "place-rels",
                        "release-rels",
                        "release-group-rels",
                        "url-rels",
                    ]
                signal.alarm(self.timeout)
                mb = musicbrainzngs.get_release_by_id(
                    self.flactags["musicbrainz_albumid"][0], includes
                )
            except Exception as e:
                _log.critical(
                    "get_release_by_id failure %s: %s (%s)"
                    % (e, self.filename, self.flactags["musicbrainz_albumid"][0])
                )
                mb = {}
                return
            finally:
                signal.alarm(0)
                self.mbcache[self.flactags["musicbrainz_albumid"][0]] = mb
                # _log.info(pprint.pformat(self.mbcache))

        # not seen this in reality unless MB failed to return the info
        if "release" not in mb:
            if (
                "tracknumber" in self.flactags
                and self.flactags["tracknumber"][0] == "1"
            ):
                _log.error("no release information: %s" % (self.filename))
            return

        # easy string nodes (no children)
        releaseDictString = {
            "artist-credit-phrase": "preformatted_albumartist",
            "asin": "asin",
            "barcode": "barcode",
            "country": "releasecountry",
            "date": "date",
            "disambiguation": "release_disambiguation",
            "id": "musicbrainz_albumid",
            "title": "album",
            "packaging": "packaging",
        }
        # easy integer nodes
        releaseDictInt = {
            "medium-count": "disctotal",
            "track-count": "tracktotal",
            "track-count": "totaltracks",
        }
        # nodes with children or which require special processing
        releaseDictFunc = {
            "artist-credit": self.release_artist_credit,
            "label-info-list": self.release_label,
            "label-relation-list": self.release_label_relation,
            "medium-list": self.medium_list,
            "release-event-list": self.release_event_list,
            "release-group": self.release_group,
            "text-representation": self.text_representation,
            "url-relation-list": self.release_url_relation_list,
            "release-relation-list": self.release_relation_list,
            "artist-relation-list": self.artist_relation_list,
            "status": self.release_status,
            "area-relation-list": self.area_relation_list,
        }
        # "cover-art-archive": self.cover_art_archive,
        # nodes to ignore
        releaseListIgnore = [
            "release-event-count",
            "label-info-count",
            "quality",
            "annotation",
            "place-relation-list",
        ]

        # this is where the data tree is walked
        self.gcs(
            mb["release"],
            releaseDictString,
            releaseDictInt,
            releaseDictFunc,
            releaseListIgnore,
            "release",
        )

    def release_status(self, status):
        if status is not None:
            if "releasestatus" not in self.newtags:
                self.newtags["releasestatus"] = []
            self.newtags["releasestatus"].append(status.lower())

    def artist_relation_list(self, arl):
        # _log.info(pprint.pformat(arl))
        change = {
            "mix": "mixer",
            "mix-dj": "djmixer",
            "mix-DJ": "djmixer",
            "recording": "engineer",
            "orchestrator": "arranger",
            "instrument": "performer",
            "vocal": "performer",
        }
        for ar in arl:
            if (
                "target" in ar
                and "type" in ar
                and "artist" in ar
                and "name" in ar["artist"]
            ):
                credittype = ar["type"]
                credit = ar["artist"]["name"]
                attributes = []
                role = ""

                # bits before the change list
                if credittype == "vocal":
                    if "attribute-list" not in ar:
                        ar["attribute-list"] = ["vocals"]
                    else:
                        if "vocals" not in ar["attribute-list"]:
                            ar["attribute-list"].append("vocals")
                if credittype == "composer" and "sort-name" in ar["artist"]:
                    if "composersort" not in self.newtags:
                        self.newtags["composersort"] = []
                    self.newtags["composersort"].append(ar["artist"]["sort-name"])
                # apply the change list
                for k, v in list(change.items()):
                    if credittype == k:
                        credittype = v

                if "attribute-list" in ar:
                    role = ", ".join(ar["attribute-list"])
                    attributes.append(role)
                    credit = str(
                        "%s%s"
                        % (
                            ar["artist"]["name"],
                            str(" (%s)" % (" ".join(attributes))),
                        )
                    )

                if credittype not in self.newtags:
                    self.newtags[credittype] = []
                self.newtags[credittype].append(credit)

    def release_artist_credit(self, artistcredit):
        # _log.info(pprint.pformat(artistcredit))
        albumartist = ""
        albumartistsort = ""

        strings = {}
        funcs = {
            "url-relation-list": self.artist_url_relation_list,
            "tag-list": self.tag_list,
        }
        ignore = [
            "area",
            "country",
            "id",
            "isni-list",
            "life-span",
            "name",
            "sort-name",
            "type",
            "annotation",
            "begin-area",
            "end-area",
            "ipi",
            "ipi-list",
            "gender",
            "disambiguation",
        ]

        if "albumartist" not in self.newtags:
            self.newtags["albumartist"] = []
        if "albumartistsort" not in self.newtags:
            self.newtags["albumartistsort"] = []
        for ac in artistcredit:
            sep = " "
            if "artist" in ac:
                if "name" in ac["artist"]:
                    albumartist = albumartist + str(ac["artist"]["name"])
                if "sort-name" in ac["artist"]:
                    albumartistsort = albumartistsort + str(ac["artist"]["sort-name"])
                if "id" in ac["artist"]:
                    if "musicbrainz_albumartistid" not in self.newtags:
                        self.newtags["musicbrainz_albumartistid"] = []
                    self.newtags["musicbrainz_albumartistid"].append(
                        str(ac["artist"]["id"])
                    )
                if ac["artist"]["id"] in self.mbcache:
                    mbartist = self.mbcache[ac["artist"]["id"]]
                    # _log.debug("release_artist_credit %s /IN/ cache" % ac["artist"]["id"])
                else:
                    try:
                        # _log.debug("release_artist_credit %s not in cache" % ac["artist"]["id"])
                        signal.alarm(self.timeout)
                        mbartist = musicbrainzngs.get_artist_by_id(
                            ac["artist"]["id"], ["tags", "url-rels"]
                        )
                    except Exception as e:
                        _log.critical(
                            "get_artist_by_id failure %s: %s (%s)"
                            % (e, self.filename, ac["artist"]["id"])
                        )
                        mbartist = {}
                    finally:
                        signal.alarm(0)
                        self.mbcache[ac["artist"]["id"]] = mbartist
                # _log.info(mbartist)
                # skip "Various Artists" for release info
                if (
                    "artist" in mbartist
                    and "id" in ac["artist"]
                    and ac["artist"]["id"] != "89ad4ac3-39f7-470e-963a-56509c546377"
                ):
                    self.gcs(
                        mbartist["artist"],
                        strings,
                        {},
                        funcs,
                        ignore,
                        "release_artist_credit",
                    )
            else:
                sep = ac
                albumartist = albumartist + sep
                albumartistsort = albumartistsort + sep

        self.newtags["albumartist"].append(albumartist)
        self.newtags["albumartistsort"].append(albumartistsort)

    def release_label(self, lil):
        strings = {"catalog-number": "catalognumber"}
        funcs = {"label": self.release_label_node}
        ignore = ["id"]
        for li in lil:
            self.gcs(li, strings, {}, funcs, ignore, "release-label-list")

    def release_label_node(self, rln):
        strings = {"name": "label"}
        ignore = ["id", "sort-name", "label-code", "disambiguation", "type"]
        self.gcs(rln, strings, {}, {}, ignore, "release-label-node")

    def release_label_relation(self, lrl):
        ignore = [
            "id",
            "type-id",
            "type",
            "target",
            "label",
            "direction",
            "begin",
            "end",
            "ended",
        ]
        for l in lrl:
            if "direction" in l and l["direction"] == "backward":
                if "type" in l:
                    if l["type"] == "licensor":
                        if "licensor" not in self.newtags:
                            self.newtags["licensor"] = []
                        self.newtags["licensor"].append(l["label"]["name"])
                    if l["type"] == "distributed":
                        if "distributed" not in self.newtags:
                            self.newtags["distributed"] = []
                        self.newtags["distributed"].append(l["label"]["name"])
            self.gcs(l, {}, {}, {}, ignore, "release-label-relation")

    def medium_list(self, ml):
        strings = {"format": "media"}
        ints = {"position": "discnumber", "track-count": "tracktotal"}
        ignore = [
            "track-list",
            "title",
            "data-track-count",
            "data-track-list",
            "pregap",
        ]

        trackints = {"position": "tracknumber"}
        trackstrings = {
            "title": "title",
            "id": "musicbrainz_trackid",
            "id": "musicbrainz_releasetrackid",
            "artist-credit-phrase": "preformatted_artist",
        }

        trackignore = ["number", "length", "track_or_recording_length", "id"]
        trackfunc = {
            "artist-credit": self.track_artist_credit,
            "recording": self.track_recording,
            "recording-relation-list": self.recording_relation_list,
        }
        for medium in ml:
            if (
                "position" in medium
                and medium["position"] == self.flactags["discnumber"][0]
            ):
                self.gcs(medium, strings, ints, {}, ignore, "medium-list")
                for track in medium["track-list"]:
                    if (
                        "position" in track
                        and track["position"] == self.flactags["tracknumber"][0]
                    ):
                        self.gcs(
                            track,
                            trackstrings,
                            trackints,
                            trackfunc,
                            trackignore,
                            "track",
                        )

    def track_artist_credit(self, tac):
        # _log.info(pprint.pformat(tac))
        artist = ""
        artistsort = ""
        if "artist" not in self.newtags:
            self.newtags["artist"] = []
        if "artists" not in self.newtags:
            self.newtags["artists"] = []
        if "artistsort" not in self.newtags:
            self.newtags["artistsort"] = []
        if "musicbrainz_artistid" not in self.newtags:
            self.newtags["musicbrainz_artistid"] = []

        strings = {}
        funcs = {
            "url-relation-list": self.artist_url_relation_list,
            "tag-list": self.tag_list,
        }
        ignore = [
            "area",
            "country",
            "id",
            "isni-list",
            "life-span",
            "name",
            "sort-name",
            "type",
            "annotation",
            "begin-area",
            "end-area",
            "ipi",
            "ipi-list",
            "gender",
            "disambiguation",
        ]

        for ac in tac:
            sep = " "
            if "artist" in ac:
                if "name" in ac["artist"]:
                    artist = artist + ac["artist"]["name"]
                    # seems to be more than just this
                    self.newtags["artists"].append(ac["artist"]["name"])
                if "sort-name" in ac["artist"]:
                    artistsort = artistsort + ac["artist"]["sort-name"]
                if "id" in ac["artist"]:
                    self.newtags["musicbrainz_artistid"].append(ac["artist"]["id"])
                if ac["artist"]["id"] in self.mbcache:
                    mbartist = self.mbcache[ac["artist"]["id"]]
                else:
                    try:
                        signal.alarm(self.timeout)
                        mbartist = musicbrainzngs.get_artist_by_id(
                            ac["artist"]["id"], ["tags", "url-rels"]
                        )
                    except Exception as e:
                        _log.critical(
                            "get_artist_by_id failure %s: %s (%s)"
                            % (e, self.filename, ac["artist"]["id"])
                        )
                        mbartist = {}
                    finally:
                        signal.alarm(0)
                        self.mbcache[ac["artist"]["id"]] = mbartist
                if "artist" in mbartist:
                    self.gcs(
                        mbartist["artist"],
                        strings,
                        {},
                        funcs,
                        ignore,
                        "track_artist_credit",
                    )
            else:
                sep = ac
                artist = artist + sep
                artistsort = artistsort + sep
        self.newtags["artist"].append(artist)
        self.newtags["artistsort"].append(artistsort)

    def track_recording(self, recording):
        # picard seems to have a bug where it confuses trackid and recordingid
        # may have been a doco error http://forums.musicbrainz.org/viewtopic.php?pid=31645#p31645
        strings = {
            "title": "recording_title",
            "XXX id": "musicbrainz_trackid",
            "id": "musicbrainz_recordingid",
        }
        funcs = {
            "isrc-list": self.isrc_list,
            "work-relation-list": self.work_relation_list,
            "artist-credit-phrase": self.artist_credit_phrase,
            "artist-relation-list": self.artist_relation_list,
            "url-relation-list": self.track_url_relation_list,
            "recording-relation-list": self.recording_relation_list,
            "tag-list": self.tag_list,
        }
        ignore = [
            "artist-credit",
            "length",
            "disambiguation",
            "isrc-count",
            "place-relation-list",
            "label-relation-list",
            "release-relation-list",
            "video",
            "area-relation-list",
        ]

        # run through what we've got -- probably not much now that we've moved to sub-query
        self.gcs(recording, strings, {}, funcs, ignore, "track-recording (pass 1)")

        # some sanity checking
        if "length" not in recording:
            _log.error(
                "\nlength missing: %s %s\nhttp://musicbrainz.org/release/%s/edit"
                % (
                    self.filename,
                    datetime.timedelta(seconds=self.length),
                    self.flactags["musicbrainz_albumid"][0],
                )
            )
        # else:
        #    if timedelta(seconds=self.length) > timedelta(milliseconds=int(recording["length"])):
        #        x = timedelta(seconds=self.length) - timedelta(milliseconds=int(recording["length"]))
        #    else:
        #        x = timedelta(milliseconds=int(recording["length"])) - timedelta(seconds=self.length)
        # if x.seconds > 10 and "media" in self.flactags and "Vinyl" not in self.flactags["media"][0]: # find damaged CD tracks
        # if x.seconds > 10: # find damaged tracks
        #    _log.error("\nlength mismatch: %s %s vs %s (%d)\nhttp://musicbrainz.org/release/%s/edit" %
        #            (self.filename, timedelta(seconds=self.length),
        #                timedelta(milliseconds=int(recording["length"])),
        #                x.seconds, self.flactags["musicbrainz_albumid"][0]))

        # to quash some timeouts don't get the recording info with the tracklist, get it in a separate request
        if "id" in recording:
            # dont bother caching, won't have many re-hits
            includes = [
                "artists",
                "artist-credits",
                "isrcs",
                "area-rels",
                "artist-rels",
                "place-rels",
                "url-rels",
                "work-rels",
                "tags",
            ]
            try:
                signal.alarm(self.timeout)
                mbrecording = musicbrainzngs.get_recording_by_id(
                    recording["id"], includes
                )
            except Exception as e:
                _log.critical(
                    "get_recording_by_id failure %s: %s (%s)"
                    % (e, self.filename, recording["id"])
                )
                mbrecording = {}
            finally:
                signal.alarm(0)
        if "recording" in mbrecording:
            self.gcs(
                mbrecording["recording"],
                strings,
                {},
                funcs,
                ignore,
                "track-recording (pass 2)",
            )

    def recording_relation_list(self, rrl):
        # strings = { "phonographic copyright":"phonographic copyright" }
        # ignore = []
        # functs = {}
        for r in rrl:
            if "direction" not in r:
                _log.debug(
                    "recording_relation_list missing direction: %s" % pprint.pformat(r)
                )
            # self.gcs(r, strings, {}, functs, ignore, "recording-relation-list")

    def artist_credit_phrase(self, acp):
        if "artist" not in self.newtags:
            self.newtags["artist"] = []
        if acp not in self.newtags["artist"]:
            self.newtags["artist"].append(acp)

    def isrc_list(self, il):
        for isrc in il:
            if "isrc" not in self.newtags:
                self.newtags["isrc"] = []
            self.newtags["isrc"].append(isrc)

    def iswc_list(self, il):
        for iswc in il:
            if "iswc" not in self.newtags:
                self.newtags["iswc"] = []
            self.newtags["iswc"].append(iswc)

    def work_relation_list(self, wrl):
        # _log.debug(pprint.pformat(wrl))
        strings = {"id": "musicbrainz_workid"}
        ignore = [
            "type",
            "target",
            "type-id",
            "begin",
            "end",
            "ended",
            "direction",
            "attributes",
        ]  # attributes should be processed
        funcs = {"work": self.work, "attribute-list": self.attribute_list}

        for w in wrl:
            self.gcs(w, strings, {}, funcs, ignore, "work-relation-list")

    def work(self, w):
        # _log.info(pprint.pformat(w))
        strings = {"id": "musicbrainz_workid", "iswc": "iswc", "title": "work"}
        funcs = {
            "iswc-list": self.iswc_list,
            "artist-relation-list": self.artist_relation_list,
            "url-relation-list": self.work_url_relation_list,
            "recording-relation-list": self.recording_relation_list,
            "tag-list": self.tag_list,
            "attribute-list": self.work_attribute_list,
        }
        # "work-relation-list":self.work_relation_list, -- leads to some nasty recursion
        ignore = [
            "language",
            "disambiguation",
            "label-relation-list",
            "area-relation-list",
            "place-relation-list",
            "type",
            "work-relation-list",
        ]
        self.gcs(w, strings, {}, funcs, ignore, "work (pass 1)")

        if "id" in w:
            if w["id"] in self.mbcache:
                fullwork = self.mbcache[w["id"]]
            else:
                includes = [
                    "artist-rels",
                    "place-rels",
                    "url-rels",
                    "work-rels",
                    "tags",
                ]
                try:
                    signal.alarm(self.timeout)
                    fullwork = musicbrainzngs.get_work_by_id(w["id"], includes)
                except Exception as e:
                    _log.critical(
                        "get_work_by_id failure %s: %s (%s)"
                        % (e, self.filename, w["id"])
                    )
                    fullwork = {}
                finally:
                    signal.alarm(0)
                    self.mbcache[w["id"]] = fullwork
            if "work" in fullwork:
                self.gcs(fullwork["work"], strings, {}, funcs, ignore, "work (pass 2)")

    def work_attribute_list(self, wal):
        for a in wal:
            if (
                "attribute" in a
                and "value" in a
                and a["attribute"]
                in [
                    "ASCAP ID",
                    "APRA ID",
                    "BMI ID",
                    "BUMA/STEMRA ID",
                    "GEMA ID",
                    "JASRAC ID",
                    "SOCAN ID",
                    "CASH ID",
                    "SESAC ID",
                    "SACEM ID",
                    "AKM ID",
                    "SUISA ID",
                    "SPA ID",
                    "SGAE ID",
                    "SAYCO ID",
                    "SBAM ID",
                    "PRS tune code",
                    "ECAD ID",
                    "BUMA/STERMA ID",
                    "APDAYC ID",
                    "SAYCE ID",
                    "AGADU ID",
                    "SACVEN ID",
                    "SIAE ID",
                    "COMPASS ID",
                    "APA ID",
                    "SABAM ID",
                    "OSA ID",
                    "SADAIC ID"
                ]
            ):
                if a["attribute"] not in self.newtags:
                    self.newtags[a["attribute"]] = []
                self.newtags[a["attribute"]].append(a["value"])
            else:
                if "attribute" in a and a["attribute"] in ["Key"]:
                    _log.debug(
                        "work_attribute_list ignoring attribute: %s "
                        % pprint.pformat(a)
                    )
                else:
                    _log.warn(
                        "work_attribute_list unknown attribute: %s " % pprint.pformat(a)
                    )

    def area_relation_list(self, arl):
        strings = {}
        funcs = {}
        ignore = []
        _log.debug(pprint.pformat(arl))
        # self.gsc(XXX, strings, { }, funcs, ignore, "area_relation_list")

    def release_event_list(self, rel):
        ignore = ["date", "area", "direction"]
        for r in rel:
            self.gcs(r, {}, {}, {}, ignore, "release-event-list")

    def release_group(self, rg):
        strings = {"id": "musicbrainz_releasegroupid", "type": "musicbrainz_albumtype"}
        funcs = {"secondary-type-list": self.rg_secondary_type}
        ignore = [
            "primary-type",
            "type",
            "title",
            "artist-credit",
            "artist-credit-phrase",
            "disambiguation",
            "first-release-date",
        ]

        # not using gcs since these are lowercase and quirky
        if "primary-type" in rg:
            if "releasetype" not in self.newtags:
                self.newtags["releasetype"] = []
            self.newtags["releasetype"].append(str(rg["primary-type"]).lower())
        if "type" in rg:
            if "musicbrainz_albumtype" not in self.newtags:
                self.newtags["musicbrainz_albumtype"] = []
            # should be .lower() now but this just doubles-it up.
            self.newtags["musicbrainz_albumtype"].append(str(rg["type"]))
            # if rg["type"] == "Compilation":
            # if "compilation" not in self.newtags: self.newtags["compilation"] = []
            # self.newtags["compilation"].append(u"1")
            if "releasetype" not in self.newtags:
                self.newtags["releasetype"] = []
            self.newtags["releasetype"].append(str(rg["type"]).lower())
        if "first-release-date" in rg and rg["first-release-date"] != "":
            if self.filetype == "flac":  # mp3 does not get this
                if "originaldate" not in self.newtags:
                    self.newtags["originaldate"] = []
                self.newtags["originaldate"].append(rg["first-release-date"])
            if "originalyear" not in self.newtags:
                self.newtags["originalyear"] = []
            self.newtags["originalyear"] = [rg["first-release-date"][:4]]
        self.gcs(rg, strings, {}, funcs, ignore, "release-group")

    def rg_secondary_type(self, rgst):
        # not using gcs since these are lowercase
        for t in rgst:
            if "releasetype" not in self.newtags:
                self.newtags["releasetype"] = []
            self.newtags["releasetype"].append(str(t).lower())

    def release_relation_list(self, rrl):
        funcs = {"attributes": self.release_relation_attributes}
        ignore = [
            "release",
            "type-id",
            "type",
            "target",
            "direction",
            "attribute-list",
            "end",
            "begin",
            "ended",
            "release-relation-list",
        ]
        for r in rrl:
            self.gcs(r, {}, {}, funcs, ignore, "release-relation-list")

    def release_relation_attributes(self, rra):
        ignore = ["attribute"]
        for a in rra:
            if a["attribute"] == "bonus":
                _log.info(
                    "bonus tag: https://musicbrainz.org/release/%s"
                    % (self.flactags["musicbrainz_albumid"][0])
                )
            self.gcs(a, {}, {}, {}, ignore, "release-relation-attributes")

    def tag_list(self, tl):
        # _log.debug(pprint.pformat(tl))
        for tag in tl:
            if "count" in tag and int(tag["count"]) > 0:
                if "tag" not in self.newtags:
                    self.newtags["tag"] = []
                t = str(tag["name"].strip())
                ignore = False

                if t in self.newtags["tag"]:
                    ignore = True

                if ignore is False and t in self.lists.bogustags:
                    ignore = True
                    _log.debug(
                        "ignoring bogus tag: %s https://musicbrainz.org/tag/%s" % (t, t)
                    )

                for char in [";", "_"]:  # "/", " "
                    if ignore is False and char in t:
                        ignore = True
                        _log.debug(
                            "splitting tag with %s: %s https://musicbrainz.org/tag/%s"
                            % (char, t, t)
                        )
                        for chunk in t.split(char):
                            c = str(chunk.strip())
                            if (
                                c not in self.lists.bogustags
                                and c not in self.newtags["tag"]
                            ):
                                self.newtags["tag"].append(c)
                if ignore is False:
                    self.newtags["tag"].append(t)

    def attribute_list(self, al):
        # _log.debug(pprint.pformat(al))
        for attribute in al:
            if "tag" not in self.newtags:
                self.newtags["tag"] = []
            if str(attribute) not in self.newtags["tag"]:
                self.newtags["tag"].append(str(attribute))

    def text_representation(self, tr):
        strings = {"language": "language", "script": "script"}
        ignore = {}
        self.gcs(tr, strings, {}, {}, ignore, "text-representation")

    def artist_url_relation_list(self, urll):
        for url in urll:
            if "type" in url:
                if url["type"] == "allmusic" and "target" in url:
                    if "url_allmusic_artist_site" not in self.newtags:
                        self.newtags["url_allmusic_artist_site"] = []
                    self.newtags["url_allmusic_artist_site"].append(str(url["target"]))
                if url["type"] == "BBC Music page" and "target" in url:
                    if "url_bbc_artist_site" not in self.newtags:
                        self.newtags["url_bbc_artist_site"] = []
                    self.newtags["url_bbc_artist_site"].append(str(url["target"]))
            if "type" in url and url["type"] not in (
                "allmusic",
                "crowdfunding",
                "BBC Music page",
                "discography",
                "discogs",
                "last.fm",
                "lyrics",
                "lyrics",
                "official homepage",
                "other databases",
                "purchase for download",
                "social network",
                "social network",
                "streaming music",
                "download for free",
                "VIAF",
                "video channel",
                "wikidata",
                "wikipedia",
                "youtube",
                "secondhandsongs",
                "IMDb",
                "purevolume",
                "myspace",
                "fanpage",
                "image",
                "soundcloud",
                "purchase for mail-order",
                "biography",
                "bandcamp",
                "blog",
                "free streaming",
                "setlistfm",
                "songkick",
                "interview",
                "online community",
                "vgmdb",
                "IMSLP",
                "bandsintown",
                "streaming",
            ):
                _log.warn(
                    "unknown artist URL type: %s: %s" % (url["type"], self.filename)
                )

    def release_url_relation_list(self, urll):
        for url in urll:
            if "type" in url:
                if url["type"] == "discogs" and "target" in url:
                    if "url_discogs_release_site" not in self.newtags:
                        self.newtags["url_discogs_release_site"] = []
                    self.newtags["url_discogs_release_site"].append(str(url["target"]))
                if url["type"] == "amazon asin" and "target" in url:
                    if "asin" not in self.newtags:
                        self.newtags["asin"] = []
                    # only do the ASIN, not the full URL...
                    if len(url["target"]) == 11:  # and starts with B?
                        self.newtags["asin"].append(str(url["target"]))
                if url["type"] == "allmusic" and "target" in url:
                    if "url_allmusic_release_site" not in self.newtags:
                        self.newtags["url_allmusic_release_site"] = []
                    self.newtags["url_allmusic_release_site"].append(str(url["target"]))
                if url["type"] == "other database" and "target" in url:
                    if "url_other_database" not in self.newtags:
                        self.newtags["url_other_database"] = []
                    self.newtags["url_other_database"].append(str(url["target"]))
                if url["type"] == "download for free" and "target" in url:
                    if "url_download_free" not in self.newtags:
                        self.newtags["url_download_free"] = []
                    self.newtags["url_download_free"].append(str(url["target"]))
            if "type" in url and url["type"] not in (
                "discogs",
                "amazon asin",
                "free streaming",
                "allmusic",
                "discography entry",
                "purchase for download",
                "purchase for mail-order",
                "other databases",
                "cover art link",
                "secondhandsongs",
                "vgmdb",
                "streaming music",
                "download for free",
                "show notes",
                "license",
            ):
                _log.warn(
                    "unknown release URL type: %s: %s" % (url["type"], self.filename)
                )

    def track_url_relation_list(self, urll):
        for url in urll:
            if "type" in url:
                if url["type"] == "license" and "target" in url:
                    if "license" not in self.newtags:
                        self.newtags["license"] = []
                    self.newtags["license"].append(str(url["target"]))
                if url["type"] == "other databases" and "target" in url:
                    if "url_other_database" not in self.newtags:
                        self.newtags["url_other_database"] = []
                    self.newtags["url_other_database"].append(str(url["target"]))
                if url["type"] == "download for free" and "target" in url:
                    if "url_download_free" not in self.newtags:
                        self.newtags["url_download_free"] = []
                    self.newtags["url_download_free"].append(str(url["target"]))
            if "type" in url and url["type"] not in (
                "discogs",
                "IMDB samples",
                "free streaming",
                "streaming music",
                "other databases",
                "download for free",
                "license",
                "purchase for download",
            ):
                _log.warn(
                    "unknown track URL type: %s: %s" % (url["type"], self.filename)
                )

    def work_url_relation_list(self, urll):
        for url in urll:
            if "type" in url:
                if url["type"] == "license" and "target" in url:
                    if "license" not in self.newtags:
                        self.newtags["license"] = []
                    self.newtags["license"].append(str(url["target"]))
                if url["type"] == "lyrics" and "target" in url:
                    if "url_lyrics_site" not in self.newtags:
                        self.newtags["url_lyrics_site"] = []
                    self.newtags["url_lyrics_site"].append(str(url["target"]))
                if url["type"] == "wikipedia" and "target" in url:
                    if "url_wikipedia_song_site" not in self.newtags:
                        self.newtags["url_wikipedia_song_site"] = []
                    self.newtags["url_wikipedia_song_site"].append(str(url["target"]))
                if url["type"] == "wikidata" and "target" in url:
                    if "url_wikidata_song_site" not in self.newtags:
                        self.newtags["url_wikidata_song_site"] = []
                    self.newtags["url_wikidata_song_site"].append(str(url["target"]))
                if url["type"] == "allmusic" and "target" in url:
                    if "url_allmusic_song_site" not in self.newtags:
                        self.newtags["url_allmusic_song_site"] = []
                    self.newtags["url_allmusic_song_site"].append(str(url["target"]))
            if "type" in url and url["type"] not in (
                "wikipedia",
                "lyrics",
                "secondhandsongs",
                "wikidata",
                "songfacts",
                "allmusic",
                "license",
                "VIAF",
                "other databases",
                "misc",
                "score",
                "download for free",
            ):
                _log.warn(
                    "unknown work URL type: %s: %s" % (url["type"], self.filename)
                )

    def cover_art_archive(self, caa):
        # only seems to be a few booleans (artwork/back/front) and an integer (count)
        # pprint.pprint(caa)
        return None

    # grand central station / grind churn sift / graft chaff swill / gulp swallow chug
    def gcs(self, node, strings, ints, funcs, ignores, name):
        for k, v in list(node.items()):
            if k in strings:
                tagkey = strings[k]
                if len(v) > 0:
                    if tagkey not in self.newtags:
                        self.newtags[tagkey] = []
                    self.newtags[tagkey].append(str(v))
                    # _log.debug("%s: %s" % (tagkey, v))
            if k in ints:
                tagkey = ints[k]
                if tagkey not in self.newtags:
                    self.newtags[tagkey] = []
                self.newtags[tagkey].append(str(v))
                # _log.debug("%s: %s" % (tagkey, v))
            if k in funcs:
                # _log.debug("descending into %s" % (k))
                funcs[k](v)
                # _log.debug("ascending from %s" % (k))
            if (
                k not in ints
                and k not in strings
                and k not in funcs
                and k not in ignores
            ):
                _log.warn("unhandled %s node %s: %s [%s]" % (name, k, self.filename, v))
                # _log.debug(pprint.pformat(v))
        # _log.debug(pprint.pformat(self.newtags))

    def fetchDiscogs(self):
        url = self.newtags["url_discogs_release_site"][0]
        # _log.debug("fetching discogs: %s" % url)

        chunks = url.split("/")

        if (len(chunks) < 4 or chunks[3]) != "release":
            _log.warn("odd url_discogs_release_site: %s" % (url))
            return False

        dgid = int(chunks[4])
        if dgid not in self.dgcache:
            if len(self.dgcache) > self.mbcachesize:
                _log.debug("discogscache getting large: dumping")
                for k in list(self.dgcache.keys()):
                    del self.dgcache[k]
            try:
                signal.alarm(self.timeout)
                ddata = self.dgclient.release(dgid)
                self.dgcache[dgid] = ddata
            except Exception as e:
                _log.critical(
                    "Fetching Discogs threw an error: %s: %s %s"
                    % (e, url, self.filename)
                )
                return False
            finally:
                signal.alarm(0)

        release = self.dgcache[dgid]

        try:
            signal.alarm(self.timeout)
            mdata = release.master
            # _log.debug(dir(mdata))
            if mdata is not None and mdata.id:
                site = str("http://discogs.com/master/%s" % mdata.id)
                if "url_discogs_master_site" not in self.newtags:
                    self.newtags["url_discogs_master_site"] = []
                if site not in self.newtags["url_discogs_master_site"]:
                    self.newtags["url_discogs_master_site"].append(site)
        except Exception as e:
            _log.info(
                "Fetching Discogs Master info threw an error: %s %s"
                % (e, self.filename)
            )
        finally:
            signal.alarm(0)

        try:
            signal.alarm(self.timeout)
            if release.styles:
                for g in release.styles:
                    if "genre" not in self.newtags:
                        self.newtags["genre"] = []
                    if g not in self.newtags["genre"] and g in self.lists.validgenre:
                        self.newtags["genre"].append(g)
                        # mp3s only get one
                        if self.filetype == "mp3":
                            break

            if release.genres:
                for g in release.genres:
                    if "grouping" not in self.newtags:
                        self.newtags["grouping"] = []
                    if (
                        g not in self.newtags["grouping"]
                        and g in self.lists.validgrouping
                    ):
                        self.newtags["grouping"].append(g)
                        # mp3s only get one
                        if self.filetype == "mp3":
                            break

            # image URL does not get saved since it is tied to the logged in user
            if release.images:
                for img in release.images:
                    if img["type"] == "primary":
                        self.url_discogs_release_image = img["resource_url"]
        except Exception as e:
            _log.info("Fetching Discogs data threw an error: %s" % (e))
        finally:
            signal.alarm(0)

    def findDiscogs(self):
        try:
            signal.alarm(self.timeout)
            if "tracknumber" in self.newtags and self.newtags["tracknumber"][0] == "1":
                _log.warn(
                    "\nNeed a link to discogs for: %s\nhttp://musicbrainz.org/release/%s/edit"
                    % (self.filename, self.newtags["musicbrainz_albumid"][0])
                )
                dgsearch = "%s %s %s" % (
                    self.newtags["albumartist"][0]
                    if "albumartist" in self.newtags
                    else "",
                    self.newtags["album"][0] if "album" in self.newtags else "",
                    self.newtags["catalognumber"][0]
                    if "catalognumber" in self.newtags
                    else "",
                )
                _log.warn("searching for: %s" % dgsearch)
                dg = self.dgclient.search(dgsearch)
                for k in dg:
                    _log.warn(
                        "http://www.discogs.com/release/%s (%s %s %s %s)"
                        % (
                            k.id if "id" in list(k.data.keys()) else "",
                            k.title if "title" in list(k.data.keys()) else "",
                            k.data["catno"] if "catno" in list(k.data.keys()) else "",
                            k.data["country"]
                            if "country" in list(k.data.keys())
                            else "",
                            k.data["format"] if "format" in list(k.data.keys()) else "",
                        )
                    )
                if "barcode" in self.newtags:
                    dgsearch = "%s" % (self.newtags["barcode"][0])
                    _log.warn("searching for: %s" % dgsearch)
                    dg = self.dgclient.search(dgsearch)
                    for k in dg:
                        _log.warn(
                            "http://www.discogs.com/release/%s (%s %s %s %s)"
                            % (
                                k.id if "id" in list(k.data.keys()) else "",
                                k.title if "title" in list(k.data.keys()) else "",
                                k.data["catno"]
                                if "catno" in list(k.data.keys())
                                else "",
                                k.data["country"]
                                if "country" in list(k.data.keys())
                                else "",
                                k.data["format"]
                                if "format" in list(k.data.keys())
                                else "",
                            )
                        )
        except Exception as e:
            me = self.dgclient.identity()
            _log.error(
                "Error searching for discogs link: %s: %s (%s)"
                % (self.filename, e, me.username)
            )
        finally:
            signal.alarm(0)

    def fetchart(self):
        return
        #if "musicbrainz_albumid" not in self.flactags:
        #    return
        #if "tracknumber" in self.flactags and self.flactags["tracknumber"][0] != "1":
        #    return

        #ffiledir = os.path.dirname(self.filename)
        #ffound = []

        #fcaaartfile = os.path.joinf(
        #    self.artcache,
        #    str("%s-%s.jpg" % ("ca", self.flactags["musicbrainz_albumid"][0])),
        #)
        #if os.path.exists(caaartfile) == False or self.force == True:
        #    if self.fetchCAA(caaartfile):
        #        found.append((self.artsize(caaartfile), caaartfile))
        #    else:
        #        if self.fetchCAAGroup(caaartfile):
        #            found.append((self.artsize(caaartfile), caaartfile))
        #else:
        #    found.append((self.artsize(caaartfile), caaartfile))

        dgartfile = os.path.join(
            self.artcache,
            str("%s-%s.jpg" % ("dg", self.flactags["musicbrainz_albumid"][0])),
        )
        #if os.path.exists(dgartfile) == False or self.force == True:
        #    if self.fetchDiscogsImage(dgartfile):
        #        found.append((self.artsize(dgartfile), dgartfile))
        #else:
        #    found.append((self.artsize(dgartfile), dgartfile))

        # now figure out which is "best" (largest) and use that one
        #found.sort()
        #l = len(found)
        #if l > 0:
        #    x = found[l - 1]
        #    self.copyArtfile(x[1], os.path.join(filedir, self.coverart))

    #def artsize(self, artfile):
    #    i = Image.open(artfile)
    #    h, w = i.size
    #    s = h * w
    #    return s

    def fetchDiscogsImage(self, artfile):
        retval = False

        # this is what you get if no image set at discogs
        if not self.url_discogs_release_image:
            return retval

        # this is what you get if not logged in
        if self.url_discogs_release_image == "":
            return retval

        _log.debug(
            "checking discogs images for: %s (%s)"
            % (self.filename, self.url_discogs_release_image)
        )
        url = self.url_discogs_release_image
        toks = str.rsplit(url, ".", 1)
        # self.url_discogs_release_image = False

        _log.debug("requesting the image from discogs: %s %s" % (url, self.filename))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as DGtemp:
            try:
                if self.force != True and os.path.exists(artfile):
                    headers = dict(self.headers)
                    headers["If-Modified-Since"] = time.strftime(
                        "%a, %d %b %Y %H:%M:%S GMT",
                        time.gmtime(os.stat(artfile).st_mtime),
                    )
                else:
                    headers = dict(self.headers)
                signal.alarm(self.timeout)
                req = requests.get(url, headers=headers, timeout=self.timeout)
                req.raise_for_status()
                test = Image.open(BytesIO(req.content))
                test.save(DGtemp.name)
                self.copyArtfile(DGtemp.name, artfile)
                retval = True
            except requests.exceptions.HTTPError as e:
                if req.status_code != 404:
                    _log.warn("discogs image fetch failed (HTTP): %s %s" % (e, url))
            except OSError as e:
                _log.warn(
                    "Discogs install temp file failed: %s %s %s"
                    % (e, DGtemp.name, self.filename)
                )
            except IOError as e:
                _log.warn(
                    "Discogs save temp file failed: %s %s %s"
                    % (e, DGtemp.name, self.filename)
                )
            except Exception as e:
                _log.critical(
                    "Fetching Discogs image threw an error: %s %s" % (e, self.filename)
                )
            finally:
                signal.alarm(0)
        return retval

    def fetchCAA(self, artfile):
        retval = False

        if "musicbrainz_albumid" not in self.flactags:
            return retval

        _log.debug("checking CAA for: %s" % (self.filename))
        caaurl = str(
            "http://coverartarchive.org/release/"
            + self.flactags["musicbrainz_albumid"][0]
            + "/front"
        )

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as CAAtemp:
            try:
                if self.force != True and os.path.exists(artfile):
                    headers = dict(self.headers)
                    headers["If-Modified-Since"] = time.strftime(
                        "%a, %d %b %Y %H:%M:%S GMT",
                        time.gmtime(os.stat(artfile).st_mtime),
                    )
                else:
                    headers = dict(self.headers)
                signal.alarm(self.timeout)
                req = requests.get(caaurl, headers=headers, timeout=self.timeout)
                req.raise_for_status()
                if req.status_code == 304:
                    _log.critical("304 for MB %s" % artfile)
                    return True
                test = Image.open(BytesIO(req.content))
                # when python-musicbrainzngs in pip gets to 0.6
                #test = Image.open(BytesIO(musicbrainzngs.get_image_front(self.flactags["musicbrainz_albumid"][0])))
                test.save(CAAtemp.name)
                self.copyArtfile(CAAtemp.name, artfile)
                retval = True
            except requests.exceptions.HTTPError as e:
                if req.status_code != 404:
                    _log.warn("CAA fetch failed (HTTP): %s %s" % (e, caaurl))
            except IOError as e:
                _log.warn("CAA save temp file failed: %s %s" % (e, CAAtemp.name))
            except OSError as e:
                _log.warn(
                    "failed updating image (CAA) %s %s %s" % (CAAtemp.name, artfile, e)
                )
            except Exception as e:
                _log.critical("CAA image threw an error: %s" % (e))
            finally:
                signal.alarm(0)
        return retval

    def copyArtfile(self, tmpname, artfile):
        if os.path.exists(tmpname) and os.stat(tmpname).st_size > 0:
            if os.path.exists(artfile):
                if filecmp.cmp(artfile, tmpname):
                    _log.debug("already have the same image: %s" % (artfile))
                else:
                    _log.warn("updating the image: %s" % (artfile))
                    shutil.copyfile(tmpname, artfile)
            else:
                _log.warn("new image: %s" % (artfile))
                shutil.copyfile(tmpname, artfile)

    # def installArtfile(self, tmpname, artfile):
    #    if os.path.exists(tmpname) and os.stat(tmpname).st_size > 0:
    #        if os.path.exists(artfile) and filecmp.cmp(artfile, tmpname) == False:
    #            _log.warn("updating the image: %s" % (artfile))
    #            shutil.copyfile(tmpname, artfile)
    #        else:
    #            _log.warn("installing the image: %s %s" % (tmpname, artfile))
    #            shutil.copyfile(tmpname, artfile)

    def fetchCAAGroup(self, artfile):
        retval = False
        if "musicbrainz_releasegroupid" not in self.flactags:
            return retval

        _log.debug("checking CAA for group image: %s" % (self.filename))

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=True) as CAAtemp:
            try:
                url = str(
                    "http://coverartarchive.org/release-group/%s/"
                    % (self.flactags["musicbrainz_releasegroupid"][0])
                )
                # _log.debug("Checking release-group JSON: %s" % (url))
                signal.alarm(self.timeout)
                req = requests.get(url, headers=self.headers, timeout=self.timeout)
                req.raise_for_status()
                signal.alarm(0)
                jsonvars = req.json()
                for k, v in list(jsonvars.items()):
                    if k == "images" and "front" in v[0] and v[0]["front"]:
                        url = v[0]["image"]
                        _log.debug("Checking release-group image: %s" % (url))
                        signal.alarm(self.timeout)
                        req = requests.get(
                            url, headers=self.headers, timeout=self.timeout
                        )
                        req.raise_for_status()
                        test = Image.open(BytesIO(req.content))
                        test.save(CAAtemp.name)
                        self.copyArtfile(CAAtemp.name, artfile)
                        retval = True
                        break
            except requests.exceptions.HTTPError as e:
                if req.status_code != 404:
                    _log.warn("CAA release-group (JSON/image) failed: %s %s" % (e, url))
            except IOError as e:
                _log.warn(
                    "CAA release-group save temp file failed: %s %s" % (e, CAAtemp.name)
                )
            except OSError as e:
                _log.warn(
                    "installing the group image from the CAA %s %s %s"
                    % (CAAtemp.name, artfile, e)
                )
            except Exception as e:
                _log.critical("CAA group image threw an error: %s" % (e))
            finally:
                signal.alarm(0)
        return retval

    def fetchAcousticBrainz(self):
        mbid = self.newtags["musicbrainz_recordingid"][0]
        try:
            url = str("http://acousticbrainz.org/%s/low-level" % (mbid))
            # _log.debug("Checking AcoustiBrainz: %s" % (url))
            signal.alarm(self.timeout)
            req = requests.get(url, headers=self.headers, timeout=self.timeout)
            req.raise_for_status()
            signal.alarm(0)
            jsonvars = req.json()
            # _log.info(pprint.pformat(jsonvars))
            self.newtags["key"] = []
            self.newtags["key"].append(jsonvars["tonal"]["key_key"])
            self.newtags["scale"] = []
            self.newtags["scale"].append(jsonvars["tonal"]["key_scale"])
            self.newtags["tuning"] = []
            self.newtags["tuning"].append(str(jsonvars["tonal"]["tuning_frequency"]))
            self.newtags["bpm"] = []
            self.newtags["bpm"].append(str(jsonvars["rhythm"]["bpm"]))

            signal.alarm(self.timeout)
            url = str("http://acousticbrainz.org/%s/high-level" % (mbid))
            # _log.debug("Checking AcoustiBrainz: %s" % (url))
            req = requests.get(url, headers=self.headers, timeout=self.timeout)
            req.raise_for_status()
            jsonvars = req.json()
            # _log.info(pprint.pformat(jsonvars["highlevel"]))
            for mood in [
                "mood_party",
                "mood_aggressive",
                "mood_happy",
                "mood_sad",
                "timbre",
                "mood_relaxed",
            ]:
                # if mood in jsonvars["highlevel"]: pprint.pprint(jsonvars["highlevel"][mood])
                if (
                    mood in jsonvars["highlevel"]
                    and "not" not in jsonvars["highlevel"][mood]["value"]
                ):
                    if "mood" not in self.newtags:
                        self.newtags["mood"] = []
                    self.newtags["mood"].append(
                        str(jsonvars["highlevel"][mood]["value"])
                    )
        except requests.exceptions.HTTPError as e:
            if req.status_code != 404:
                _log.warn("AcousticBrainz recordingid JSON failed: %s %s" % (e, url))
        except Exception as e:
            _log.critical("AcousticBrainz threw an error: %s" % (e))
        finally:
            signal.alarm(0)

    def flactoid3(self):
        newtags = ID3()
        comments = []

        if "musicbrainz_albumid" not in self.flactags:
            _log.warn("Missing musicbrainz_albumid for: %s" % (self.filename))
            self.flactags["musicbrainz_albumid"] = "UNSET"

        if "artist" in self.flactags:
            bestartist = self.flactags["artist"][0]
        else:
            self.flactags["artist"] = "Unknown Artist"
            bestartist = "Unknown Artist"
        newtags.add(TPE1(encoding=3, text=bestartist))

        if "artists" in self.flactags:
            newtags.add(
                TXXX(
                    encoding=3, desc="artists", text="/".join(self.flactags["artists"])
                )
            )

        if "artistsort" in self.flactags:
            bestartist = self.flactags["artistsort"][0]
            newtags.add(TSOP(encoding=3, text=self.flactags["artistsort"][0]))

        if "albumartist" in self.flactags:
            bestartist = self.flactags["albumartist"][0]
            newtags.add(TPE2(encoding=3, text=self.flactags["albumartist"][0]))

        if "albumartistsort" in self.flactags:
            bestartist = self.flactags["albumartistsort"][0]
            newtags.add(TSO2(encoding=3, text=self.flactags["albumartistsort"][0]))

        if "album" not in self.flactags:
            _log.warn("album not set: %s" % (self.filename))
            self.flactags["album"][0] = "Unknown Album"
        newtags.add(TALB(encoding=3, text=self.flactags["album"][0]))

        if "albumsort" in self.flactags:
            albumsort = str(
                self.flactags["albumsort"][0]
                + " ["
                + self.flactags["musicbrainz_albumid"][0]
                + "]"
            )
        else:
            albumsort = str(
                self.flactags["album"][0]
                + " ["
                + self.flactags["musicbrainz_albumid"][0]
                + "]"
            )
        newtags.add(TSOA(encoding=3, text=albumsort))

        if "bpm" in self.flactags:
            newtags.add(TBPM(encoding=3, text=self.flactags["bpm"][0]))

        if "catalognumber" in self.flactags:
            # for picard compat it should be "/" instead of "; "
            catnumbers = "; ".join(self.flactags["catalognumber"])
            newtags.add(TXXX(encoding=3, desc="CATALOGNUMBER", text=catnumbers))
        else:
            catnumbers = ""

        if "comment" in self.flactags:
            for c in self.flactags["comment"]:
                comments.append(c)

        if "tag" in self.flactags:
            for t in self.flactags["tag"]:
                comments.append(t)

        if "compilation" in self.flactags:
            newtags.add(TCMP(encoding=3, text=self.flactags["compilation"][0]))

        if "composer" in self.flactags:
            composers = "/".join(sorted(self.flactags["composer"]))
            newtags.add(TCOM(encoding=3, text=composers))

        if "composersort" in self.flactags:
            composers = "/".join(sorted(self.flactags["composersort"]))
            newtags.add(TSOC(encoding=3, text=composers))

        if "conductor" in self.flactags:
            newtags.add(TPE3(encoding=3, text=self.flactags["conductor"][0]))

        if "copyright" in self.flactags:
            newtags.add(TCOP(encoding=3, text=self.flactags["copyright"][0]))

        if "date" in self.flactags:
            date = self.flactags["date"][0]
            newtags.add(TDRC(encoding=3, text=date))
        else:
            date = ""

        if "discnumber" in self.flactags:
            discnumber = self.flactags["discnumber"][0]
            # shortdiscnumber = self.flactags["discnumber"][0]
            if "disctotal" in self.flactags:
                discnumber = str(
                    self.flactags["discnumber"][0] + "/" + self.flactags["disctotal"][0]
                )
            newtags.add(TPOS(encoding=3, text=discnumber))
        # else:
        # shortdiscnumber = "1"

        if "discsubtitle" in self.flactags:
            newtags.add(TSST(encoding=3, text=self.flactags["discsubtitle"][0]))

        if "genre" in self.flactags and len(self.flactags["genre"]) > 0:
            # example for when iTunes can handle multi-value tags, just drop the [0]
            # newtags.add(TCON(encoding=3, text=self.flactags["genre"]))
            newtags.add(TCON(encoding=3, text=self.flactags["genre"][0]))
        else:
            if "grouping" in self.flactags:
                newtags.add(TCON(encoding=3, text=self.flactags["grouping"][0]))

        # TIT1 is for groupsings of songs (movements of a single work) not genre info
        # if "grouping" in self.flactags and len(self.flactags["grouping"]) > 0:
        #    newtags.add(TIT1(encoding=3, text=self.flactags["grouping"][0]))

        if "isrc" in self.flactags:
            # newtags.add(TSRC(encoding=3, text=self.flactags["isrc"][0]))
            newtags.add(TSRC(encoding=3, text="/".join(self.flactags["isrc"])))

        if "key" in self.flactags:
            newtags.add(TKEY(encoding=3, text=self.flactags["key"][0]))

        if "label" in self.flactags:
            # self.flactags["label"].sort()
            labels = "; ".join(sorted(self.flactags["label"]))
            newtags.add(TPUB(encoding=3, text=labels))
        else:
            labels = ""

        if "language" in self.flactags:
            newtags.add(TLAN(encoding=3, text=self.flactags["language"][0]))

        if "lyrics" in self.flactags:
            # XXX should not naively assume English
            newtags.add(
                USLT(
                    encoding=3,
                    lang="eng",
                    desc="desc",
                    text=self.flactags["lyrics"][0],
                )
            )

        if "lyricist" in self.flactags:
            lyricists = "/".join(sorted(self.flactags["lyricist"]))
            newtags.add(TEXT(encoding=3, text=lyricists))
            newtags.add(TOLY(encoding=3, text=lyricists))

        if "media" not in self.flactags:
            self.flactags["media"] = []
            self.flactags["media"][0] = "unset"
            _log.warn("media unset for: %s" % (self.filename))
        newtags.add(TMED(encoding=3, text=self.flactags["media"][0]))

        if "mood" in self.flactags:
            moods = "/".join(sorted(self.flactags["mood"]))
            newtags.add(TMOO(encoding=3, text=moods))

        if "musicbrainz_trackid" in self.flactags:
            newtags.add(
                UFID(
                    owner="http://musicbrainz.org",
                    data=bytes(self.flactags["musicbrainz_trackid"][0], 'utf-8'),
                )
            )

        if "original_album" in self.flactags:
            newtags.add(TOAL(encoding=3, text=self.flactags["original_album"][0]))

        if "original_artist" in self.flactags:
            newtags.add(TPOE(encoding=3, text=self.flactags["original_artist"][0]))

        if "originalyear" in self.flactags:
            newtags.add(TDOR(encoding=3, text=self.flactags["originalyear"][0]))
            newtags.add(
                TXXX(
                    encoding=3,
                    desc="Original Year",
                    text=self.flactags["originalyear"][0],
                )
            )

        if "performer" in self.flactags:
            tmpPerf = []
            for p in self.flactags["performer"]:
                if p.find("(") != -1:
                    (perf, role) = str.split(p, "(", 1)
                    role = role[:-1]
                    perf = perf[:-1]
                    tmpPerf.append([perf, role])
                else:
                    perf = p
                    tmpPerf.append([p])
            newtags.add(TMCL(encoding=3, people=tmpPerf))

        if "remixer" in self.flactags:
            # self.flactags["remixer"].sort()
            remixers = "/".join(sorted(self.flactags["remixer"]))
            newtags.add(TPE4(encoding=3, text=remixers))

        if "subtitle" in self.flactags:
            newtags.add(TIT3(encoding=3, text=self.flactags["subtitle"][0]))

        if "title" not in self.flactags:
            self.flactags["title"][0] = "Unknown Track"
        else:
            newtags.add(TIT2(encoding=3, text=self.flactags["title"][0]))

        if "titlesort" in self.flactags:
            newtags.add(TSOT(encoding=3, text=self.flactags["titlesort"][0]))

        if "tracknumber" in self.flactags:
            if int(self.flactags["tracknumber"][0]) <= 9:
                tracknumber = str("0" + self.flactags["tracknumber"][0])
            else:
                tracknumber = self.flactags["tracknumber"][0]

            if "tracktotal" in self.flactags:
                longtracknumber = str(
                    tracknumber + "/" + self.flactags["tracktotal"][0]
                )
            else:
                longtracknumber = self.flactags["tracknumber"][0]
        else:
            tracknumber = "0"
            longtracknumber = "0/0"
        newtags.add(TRCK(encoding=3, text=longtracknumber))

        for k, v in list(self.lists.wxxx.items()):
            if k in self.flactags:
                url = (self.flactags[k][0]).encode("ascii", "ignore")
                newtags.add(WXXX(encoding=0, desc=v, url=url))

        for k, v in list(self.lists.txxx.items()):
            if k in self.flactags and len(self.flactags[k]) > 0:
                if k in ["releasetype"]:
                    newtags.add(
                        TXXX(encoding=3, desc=v, text="/".join(self.flactags[k]))
                    )
                else:
                    newtags.add(TXXX(encoding=3, desc=v, text=self.flactags[k][0]))

        tipl = []
        for k, v in list(self.lists.tipl.items()):
            if k in self.flactags:
                self.flactags[k].sort()
                for a in self.flactags[k]:
                    tipl.append([v, a])
        if len(tipl) > 0:
            newtags.add(TIPL(encoding=3, people=tipl))

        if len(comments) > 0:
            newtags.add(
                COMM(
                    encoding=3,
                    desc="",
                    lang="eng",
                    text=("%s" % ", ".join(comments)),
                )
            )

        #if "replaygain_track_gain" in self.flactags:
        #    rtg = float(self.flactags["replaygain_track_gain"][0].split()[0])
        #    tg = pow(10, rtg * -0.1) * 1000
        #    htg = pow(10, rtg * -0.25) * 2500
        #    if "replaygain_track_peak" in self.flactags:
        #        rtp = float(self.flactags["replaygain_track_peak"][0].split()[0])
        #    else:
        #        rtp = 0.02
        #    tp = rtp * 32768
        #    newtags.add(
        #        COMM(
        #            encoding=3,
        #            desc="iTunesNORM",
        #            text=str(
        #                "%08X %08X %08X %08X %08X %08X %08X %08X %08X %08X"
        #                % (tg, tg, htg, htg, 0, 0, tp, tp, 0, 0)
        #            ),
        #        )
        #    )

        # _log.warn(pprint.pformat(newtags))
        return newtags

    def id3toflac(self, mp3tag):
        self.flactags = {}

        for id3tag, ftag in list(self.lists.xlist.items()):
            for t in mp3tag.getall(id3tag):
                if ftag not in self.flactags:
                    self.flactags[ftag] = []
                # when iTunes quits being stupid with multi-value tags, start here, this flattens them
                # this could actually be smarter now, but flactoid3 cannot (at least for values which iTunes uses)
                value = ("%s" % t) #.decode("utf-8", "ignore")
                if id3tag == "TRCK":
                    chunks = value.split("/")
                    value = "%s" % (int(chunks[0]))
                    if len(chunks) > 1:
                        if "tracktotal" not in self.flactags:
                            self.flactags["tracktotal"] = []
                        self.flactags["tracktotal"].append("%s" % chunks[1])
                if id3tag == "TPOS":
                    chunks = value.split("/")
                    value = "%s" % (int(chunks[0]))
                    if len(chunks) > 1:
                        if "disctotal" not in self.flactags:
                            self.flactags["disctotal"] = []
                        self.flactags["disctotal"].append("%s" % chunks[1])
                # ignore things addressed below
                if ftag not in ["releasetype", "composer", "composersort"]:
                    self.flactags[ftag].append(value)

        for x in mp3tag.getall("TCOM"):
            y = "%s" % x
            chunks = y.split("/")
            for c in chunks:
                if "composer" not in self.flactags:
                    self.flactags["composer"] = []
                self.flactags["composer"].append("%s" % c) #.decode("utf-8", "ignore"))

        #        for x in mp3tag.getall("TSOC"):
        #            y = ("%s" % x)
        #            chunks = y.split("/")
        #            for c in chunks:
        #                if "composersort" not in self.flactags: self.flactags["composersort"] = []
        #                self.flactags["composersort"].append(u"%s" % c)

        for isrcs in mp3tag.getall("TSRC"):
            isrc = "%s" % isrcs
            chunks = isrc.split("/")
            for c in chunks:
                if "isrc" not in self.flactags:
                    self.flactags["isrc"] = []
                self.flactags["isrc"].append("%s" % c.strip())

        for moods in mp3tag.getall("TMOO"):
            mood = "%s" % moods
            chunks = mood.split("/")
            for c in chunks:
                if "mood" not in self.flactags:
                    self.flactags["mood"] = []
                self.flactags["mood"].append("%s" % c)

        for unexploded in mp3tag.getall("TXXX:artists"):
            if "artists" not in self.flactags:
                self.flactags["artists"] = []
            tmp = "%s" % (unexploded)
            for x in tmp.split("/"):
                self.flactags["artists"].append(x)

        for unexploded in mp3tag.getall("TXXX:Release Type"):
            if "releasetype" not in self.flactags:
                self.flactags["releasetype"] = []
            tmp = "%s" % (unexploded)
            for x in tmp.split("/"):
                self.flactags["releasetype"].append(x.strip().lower())

        for t in mp3tag.getall("TIPL"):
            for p in t.people:
                if p[0] in self.lists.tipl:
                    if self.lists.tipl[p[0]] not in self.flactags:
                        self.flactags[self.lists.tipl[p[0]]] = []
                    self.flactags[self.lists.tipl[p[0]]].append(p[1])
                else:
                    _log.info("unknown TIPL: %s %s" % (p[0], self.filename))

        for t in mp3tag.getall("TMCL"):
            for p in t.people:
                # _log.debug("found TMCL %s %s %s" % (p[0], p[1], self.filename))
                if "performer" not in self.flactags:
                    self.flactags["performer"] = []
                if p[1]:
                    self.flactags["performer"].append("%s (%s)" % (p[0], p[1]))
                else:
                    self.flactags["performer"].append("%s" % (p[0]))

        # XXX this is not right. -- how so?, yes, I often talk to myself in code comments
        for c in mp3tag.getall("COMM:"):
            # _log.debug("COMM: %s" % c)
            comm = "%s" % c
            if "," in comm:
                if "tag" not in self.flactags:
                    self.flactags["tag"] = []
                for t in comm.split(","):
                    tag = t.strip()
                    # _log.debug("tag: %s" % tag)
                    if (
                        tag not in self.flactags["tag"]
                        and tag not in self.lists.bogustags
                    ):
                        self.flactags["tag"].append(str(tag))
            else:
                # _log.debug("comment: %s" % c)
                if "comment" not in self.flactags:
                    self.flactags["comment"] = []
                self.flactags["comment"].append("%s" % c)
        return

    def flactom4a(self):
        newtags = MP4()
        comments = []
        dir(newtags)

        if "musicbrainz_albumid" not in self.flactags:
            _log.warn("Missing musicbrainz_albumid for: %s" % (self.filename))
            self.flactags["musicbrainz_albumid"] = "UNSET"

        if "acousticid_fingerprint" in self.flactags:
            newtags["----:com.apple.iTunes:Acoustid Fingerprint"] = self.flactags["acousticid_fingerprint"][0]

        if "acousticid_id" in self.flactags:
            newtags["----:com.apple.iTunes:Acoustid id"] = self.flactags["acousticid_id"][0]

        if "artist" in self.flactags:
            bestartist = self.flactags["artist"][0]
        else:
            self.flactags["artist"] = "Unknown Artist"
            bestartist = "Unknown Artist"
        newtags["©ART"] = bestartist

        if "artists" in self.flactags:
            newtags["----:com.apple.iTunes:ARTISTS"] = "; ".join(self.flactags["artists"]).encode('utf-8')

        if "artistsort" in self.flactags:
            newtags["soar"] = "; ".join(sorted(self.flactags["artistsort"]))

        if "albumartist" in self.flactags:
            newtags["aART"] = "; ".join(sorted(self.flactags["albumartist"]))

        if "albumartistsort" in self.flactags:
            newtags["soaa"] = "; ".join(sorted(self.flactags["albumartistsort"]))

        if "album" not in self.flactags:
            _log.warn("album not set: %s" % (self.filename))
            self.flactags["album"][0] = "Unknown Album"
        newtags["©alb"] = self.flactags["album"][0]

        if "albumsort" in self.flactags:
            albumsort = str(
                self.flactags["albumsort"][0]
                + " ["
                + self.flactags["musicbrainz_albumid"][0]
                + "]"
            )
        else:
            albumsort = str(
                self.flactags["album"][0]
                + " ["
                + self.flactags["musicbrainz_albumid"][0]
                + "]"
            )
        newtags["soal"] = albumsort

        if "arranger" in self.flactags:
            newtags["----:com.apple.iTunes:ARRANGER"] = "; ".join(self.flactags["arranger"]).encode('utf-8')

        if "asin" in self.flactags:
            newtags["----:com.apple.iTunes:ASIN"] = "; ".join(self.flactags["asin"]).encode('utf-8')

        if "barcode" in self.flactags:
            newtags["----:com.apple.iTunes:BARCODE"] = self.flactags["barcode"][0].encode('utf-8')

        #if "bpm" in self.flactags:
        #    newtags["tmpo"] = self.flactags["bpm"][0].encode('utf-8')

        if "catalognumber" in self.flactags:
            # for picard compat it should be "/" instead of "; "
            catnumbers = "; ".join(self.flactags["catalognumber"]).encode('utf-8')
            newtags["----:com.apple.iTunes:CATALOGNUMBER"] = catnumbers
        else:
            catnumbers = ""

        if "comment" in self.flactags:
            for c in self.flactags["comment"]:
                comments.append(c)

        if "tag" in self.flactags:
            for t in self.flactags["tag"]:
                comments.append(t)

        if "compilation" in self.flactags:
            newtags["cpil"] = self.flactags["compilation"][0]

        if "composer" in self.flactags:
            composers = "/".join(sorted(self.flactags["composer"]))
            newtags["©wrt"] = composers

        if "composersort" in self.flactags:
            composers = "/".join(sorted(self.flactags["composersort"]))
            newtags["soco"] = composers

        if "conductor" in self.flactags:
            newtags["----:com.apple.iTunes:CONDUCTOR"] = "; ".join(self.flactags["conductor"]).encode('utf-8')

        if "copyright" in self.flactags:
            newtags["cprt"] = self.flactags["copyright"][0]

        if "country" in self.flactags:
            newtags["----:com.apple.iTunes:Country"] = self.flactags["country"][0].encode('utf-8')

        if "date" in self.flactags:
            date = self.flactags["date"][0]
            newtags["©day"] = date
        else:
            date = ""

        if "discnumber" in self.flactags and "disctotal" in self.flactags:
            dn = int(self.flactags["discnumber"][0])
            td = int(self.flactags["disctotal"][0])
            newtags["disk"] = ([dn,td], [dn,td]) # what insanity is this?

        if "url_discogs_artist_site" in self.flactags:
            newtags["----:com.apple.iTunes:URL_DISCOGS_ARTIST_SITE"] = self.flactags["url_discogs_artist_site"][0].encode('utf-8')

        if "url_discogs_release_site" in self.flactags:
            newtags["----:com.apple.iTunes:URL_DISCOGS_RELEASE_SITE"] = self.flactags["url_discogs_release_site"][0].encode('utf-8')

        if "djmixer" in self.flactags:
            newtags["----:com.apple.iTunes:DJMIXER"] = self.flactags["djmixer"][0].encode('utf-8')

        if "engineer" in self.flactags:
            newtags["----:com.apple.iTunes:ENGINEER"] = "; ".join(sorted(self.flactags["engineer"])).encode('utf-8')

        if "fbpm" in self.flactags:
            newtags["----:com.apple.iTunes:fBPM"] = self.flactags["fbpm"][0]

        if "genre" in self.flactags and len(self.flactags["genre"]) > 0:
            newtags["©gen"] = self.flactags["genre"][0]

        if "grouping" in self.flactags:
            newtags["©grp"] = self.flactags["grouping"][0]

        if "isrc" in self.flactags:
            newtags["----:com.apple.iTunes:ISRC"] = "; ".join(sorted(self.flactags["isrc"])).encode('utf-8')

        if "key" in self.flactags:
            newtags["----:com.apple.iTunes:KEY"] = self.flactags["key"][0].encode('utf-8')

        if "label" in self.flactags:
            newtags["----:com.apple.iTunes:LABEL"] = "; ".join(sorted(self.flactags["label"])).encode('utf-8')
        else:
            labels = ""

        if "language" in self.flactags:
            newtags["----:com.apple.iTunes:LANGUAGE"] = self.flactags["language"][0].encode('utf-8')

        if "lyrics" in self.flactags:
            newtags["©lyr"] = self.flactags["lyrics"][0] # .encode('utf-8')

        if "lyricist" in self.flactags:
            newtags["----:com.apple.iTunes:LYRICIST"] = "; ".join(sorted(self.flactags["lyricist"])).encode('utf-8')

        if "url_lyrics_site" in self.flactags:
            newtags["----:com.apple.iTunes:URL_LYRICS_SITE"] = self.flactags["url_lyrics_site"][0].encode('utf-8')

        if "media" not in self.flactags:
            self.flactags["media"] = []
            self.flactags["media"][0] = "unset"
            _log.warn("media unset for: %s" % (self.filename))
        newtags["----:com.apple.iTunes:MEDIA"] = self.flactags["media"][0].encode('utf-8')

        if "mixer" in self.flactags:
            newtags["----:com.apple.iTunes:MIXER"] = "; ".join(sorted(self.flactags["mixer"])).encode('utf-8')

        if "mood" in self.flactags:
            newtags["----:com.apple.iTunes:MOOD"] = "; ".join(sorted(self.flactags["mood"])).encode('utf-8')

        if "musicbrainz_artistid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Artist Id"] = self.flactags["musicbrainz_artistid"][0].encode('utf-8')

        if "musicbrainz_discid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Disc Id"] = self.flactags["musicbrainz_discid"][0].encode('utf-8')

        if "musicbrainz_originalalbumid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Original Album Id"] = self.flactags["musicbrainz_originalalbumid"][0].encode('utf-8')

        if "musicbrainz_albumartistid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Album Artist Id"] = self.flactags["musicbrainz_albumartistid"][0].encode('utf-8')

        if "musicbrainz_releasegroupid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Release Group Id"] = self.flactags["musicbrainz_releasegroupid"][0].encode('utf-8')

        if "musicbrainz_albumid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Album Id"] = self.flactags["musicbrainz_albumid"][0].encode('utf-8')

        if "musicbrainz_trackid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Track Id"] = self.flactags["musicbrainz_trackid"][0].encode('utf-8')

        if "musicbrainz_releasetrackid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Track Id"] = self.flactags["musicbrainz_releasetrackid"][0].encode('utf-8')
            newtags["----:com.apple.iTunes:MusicBrainz Release Track Id"] = self.flactags["musicbrainz_releasetrackid"][0].encode('utf-8')

        if "musicbrainz_workid" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Work Id"] = self.flactags["musicbrainz_workid"][0].encode('utf-8')

        if "occasion" in self.flactags:
            newtags["----:com.apple.iTunes:occasion"] = self.flactags["occasion"][0].encode('utf-8')

        if "url_offical_artist_site" in self.flactags:
            newtags["----:com.apple.iTunes:URL_OFFICIAL_ARTIST_SITE"] = self.flactags["url_official_artist_site"][0].encode('utf-8')

        if "url_offical_release_site" in self.flactags:
            newtags["----:com.apple.iTunes:URL_OFFICIAL_RELEASE_SITE"] = self.flactags["url_official_release_site"][0].encode('utf-8')

        if "original_album" in self.flactags:
            newtags["----:com.apple.iTunes:ORIGINAL_ALBUM"] = self.flactags["original_album"][0].encode('utf-8')

        if "original_artist" in self.flactags:
            newtags["----:com.apple.iTunes:ORIGINAL_ARTIST"] = self.flactags["original_artist"][0].encode('utf-8')

        if "original_lyricist" in self.flactags:
            newtags["----:com.apple.iTunes:ORIGINAL_LYRICIST"] = self.flactags["original_lyricist"][0].encode('utf-8')

        if "originalyear" in self.flactags:
            newtags["----:com.apple.iTunes:ORIGINALYEAR"] = self.flactags["originalyear"][0].encode('utf-8')

        if "originaldate" in self.flactags:
            newtags["----:com.apple.iTunes:ORIGINALDATE"] = self.flactags["originaldate"][0].encode('utf-8')

        if "url_wikipedia_release_site" in self.flactags:
            newtags["pcst"] = self.flactags["url_wikipedia_release_site"][0].encode('utf-8')

        if "url_official_artist_site" in self.flactags:
            newtags["purl"] = self.flactags["url_official_artist_site"][0].encode('utf-8')

        if "producer" in self.flactags:
            newtags["----:com.apple.iTunes:PRODUCER"] = self.flactags["producer"][0].encode('utf-8')

        if "quality" in self.flactags:
            newtags["----:com.apple.iTunes:QUALITY"] = self.flactags["quality"][0].encode('utf-8')

        if "rate" in self.flactags:
            newtags["rate"] = self.flactags["rate"][0].encode('utf-8')

        if "releasecountry" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Album Release Country"] = self.flactags["releasecountry"][0].encode('utf-8')

        if "releasestatus" in self.flactags:
            newtags["----:com.apple.iTunes:RELEASESTATUS"] = "; ".join(self.flactags["releasestatus"]).encode('utf-8').lower()

        if "musicbrainz_albumtype" in self.flactags:
            newtags["----:com.apple.iTunes:MusicBrainz Album Type"] = "; ".join(self.flactags["musicbrainz_albumtype"]).encode('utf-8').lower()

        if "remixer" in self.flactags:
            remixers = "/".join(sorted(self.flactags["remixer"])).encode('utf-8')
            newtags["----:com.apple.iTunes:REMIXER"] = remixers

        if "script" in self.flactags:
            newtags["----:com.apple.iTunes:SCRIPT"] = self.flactags["script"][0].encode('utf-8')

        if "tempo" in self.flactags:
            newtags["----:com.apple.iTunes:QUALITY"] = self.flactags["tempo"][0].encode('utf-8')

        if "title" not in self.flactags:
            self.flactags["title"][0] = "Unknown Track"
        newtags["©nam"] = self.flactags["title"][0]

        if "titlesort" in self.flactags:
            newtags["sonm"] = self.flactags["titlesort"][0].encode('utf-8')

        if "tracknumber" in self.flactags:
            tn = int(self.flactags["tracknumber"][0])
            tt = 0
            if "tracktotal" in self.flactags:
                tt = int(self.flactags["tracktotal"][0])
            newtags["trkn"] = ([tn,tt], [tn,tt])

        if "vinyldigitizer" in self.flactags:
            newtags["----:com.apple.iTunes:VINYLDIGITIZER"] = self.flactags["vinyldigitizer"][0].encode('utf-8')

        if "work" in self.flactags:
            newtags["----:com.apple.iTunes:WORK"] = self.flactags["work"][0].encode('utf-8')

        if "writer" in self.flactags:
            newtags["----:com.apple.iTunes:WRITER"] = "; ".join(sorted(self.flactags["writer"][0])).encode('utf-8')

        if "digitize_date" in self.flactags:
            newtags["----:com.apple.iTunes:DIGITIZE_DATE"] = self.flactags["digitize_date"][0].encode('utf-8')

        if "digitize_info" in self.flactags:
            newtags["----:com.apple.iTunes:DIGITIZE_INFO"] = self.flactags["digitize_info"][0].encode('utf-8')
            comments.append(self.flactags["digitize_info"][0])

        if len(comments) > 0:
            newtags["©cmt"] = ", ".join(comments) # .encode('utf-8')

        #pprint.pprint(newtags)
        return newtags

    # does this need to be here or can it be in the calling apps?
    def transcodePath(self, root, windows, outformat="mp3"):
        if windows:
            bad = '/:*?;"<>|'
        else:
            bad = "/"

        # is this the best place to do this?
        # if "releasetype" in self.flactags:
            #for t in ["interview", "audiobook", "spokenword"]:
            #    if t in self.flactags["releasetype"]:
            #        _log.debug("skipping %s: %s" % (t, self.filename))
            #        return False
            #if (
            #    "live" in self.flactags["releasetype"]
            #    and "bootleg" in self.flactags["releasestatus"]
            #):
            #    _log.debug("skipping: %s" % (self.filename))
            #    return False

        maxlen = 240 - len(root)
        bestartist = "Unknown Artist"
        if "artist" in self.flactags:
            bestartist = self.flactags["artist"][0]
        if "artistsort" in self.flactags:
            bestartist = self.flactags["artistsort"][0]
        if "albumartist" in self.flactags:
            bestartist = self.flactags["albumartist"][0]
        if "albumartistsort" in self.flactags:
            bestartist = self.flactags["albumartistsort"][0]
        bestname = "".join([(s in bad and "_") or s for s in bestartist])
        maxlen = maxlen - len(bestname)

        album = "Unknown Album"
        if "album" in self.flactags:
            album = self.flactags["album"][0]
        date = ""
        if "date" in self.flactags:
            date = self.flactags["date"][0]
        media = ""
        if "media" in self.flactags:
            media = self.flactags["media"][0]
        releasecountry = ""
        if "releasecountry" in self.flactags:
            releasecountry = self.flactags["releasecountry"][0]
        labels = ""
        if "label" in self.flactags:
            labels = "; ".join(self.flactags["label"])
        catnumbers = ""
        if "catalognumber" in self.flactags:
            catnumbers = "; ".join(self.flactags["catalognumber"])

        albumname = "".join(
            map(
                lambda s: (s in bad and "_") or s,
                str(
                    album
                    + " ["
                    + date
                    + ","
                    + media
                    + ","
                    + releasecountry
                    + ","
                    + labels
                    + ","
                    + catnumbers
                    + "]"
                ),
            )
        )
        maxlen = maxlen - len(albumname)

        discnumber = "1"
        if "discnumber" in self.flactags:
            discnumber = self.flactags["discnumber"][0]
        tracknumber = "1"
        if "tracknumber" in self.flactags:
            if int(self.flactags["tracknumber"][0]) <= 9:
                tracknumber = str("0" + self.flactags["tracknumber"][0])
            else:
                tracknumber = self.flactags["tracknumber"][0]

        trackname = "".join(
            map(
                lambda s: (s in bad and "_") or s,
                str(
                    discnumber
                    + "-"
                    + tracknumber
                    + " "
                    + (self.flactags["title"][0])[:maxlen]
                    + "."
                    + outformat
                ),
            )
        )
        outdir = os.path.join(root, bestname, albumname)
        # XXX this doesn't belong here, instead return (outdir, trackname) and let the caller create the path
        if os.path.exists(outdir) == False:
            os.makedirs(outdir)
        outfile = os.path.join(outdir, trackname)
        return outfile

    def verify(self):
        _log.debug("verifying %s" % (self.filename))
        if self.filetype == "flac":
            out = subprocess.check_output(["flac", "-t", "-s", self.filename])
            if out != "":
                _log.warn("%s: %s" % (out, self.filename))
        if self.filetype == "mp3":
            _log.debug("verifying mp3 unfinished")
            # verify mp3

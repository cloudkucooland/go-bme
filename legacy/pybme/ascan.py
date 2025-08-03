#!/usr/bin/python3
# -*- coding: utf-8 -*-
# this file is public domain - more free than free

import acoustid
import os
import stat
import string
import pprint
import signal
from mutagen.flac import FLAC
from optparse import OptionParser


def main():
    usage = "usage: %prog [options] file.flac|dir [...]"
    parser = OptionParser(usage=usage)
    (options, args) = parser.parse_args()
    signal.signal(signal.SIGALRM, timeouthandler)

    slop = 10

    if len(args) == 0:
        return ()

    incoming = buildfilelist(args)
    incoming = list(set(incoming))  # remove duplicates

    count = len(incoming)
    print(("found %d files" % (count)))
    incoming.sort()

    for filename in incoming:
        outbuf = ""
        changed = 0
        fn, fe = os.path.splitext(filename)
        if fe != ".flac":
            print(("not FLAC file: %s" % (filename)))
            continue

        try:
            tags = FLAC(filename)
            length = tags.info.length
            # if length < 30: return
        except Exception as e:
            print(("Error reading tags from: %s %s" % (filename, e)))
            continue

        try:
            if "acoustid_fingerprint" not in tags:
                (dur, fp) = acoustid.fingerprint_file(filename)
                print(("adding fingerprint to %s" % filename))
                tags["acoustid_fingerprint"] = [fp]
                changed = 1
            else:
                fp = tags["acoustid_fingerprint"][0]
                dur = tags.info.length
        except Exception as e:
            print(("error scanning: %s" % e))
            continue

        try:
            signal.alarm(30)
            res = acoustid.lookup("79O94Yyl", fp, dur)
        except Exception as e:
            print(("lookup failed: %s" % e))
            continue
        finally:
            signal.alarm(0)

        if "results" not in res:
            print(("no result found: %s" % (filename)))
        else:
            if len(res["results"]) == 0:
                print(("result zero length: %s" % (filename)))

        acoustid_ids = []
        if (
            "results" in res
            and res["status"] == "ok"
            and len(res["results"]) > 0
            and "musicbrainz_recordingid" in tags
        ):
            acoustid_ids = []
            items = len(res["results"])
            if items == 0:
                print(("zero acoustIDs found: %s" % (items, filename)))
                # pprint.pprint(res)
            # if items > 1:
            #    print ("%s acoustIDs found: %s" % (items, filename))
            # pprint.pprint(res)
            for item in res["results"]:
                # if items > 1:
                #    print("+++ https://acoustid.org/track/%s\n... https://musicbrainz.org/recording/%s\n... https://musicbrainz.org/release/%s" % (item["id"], tags["musicbrainz_recordingid"][0], tags["musicbrainz_albumid"][0]))
                if "recordings" in item:
                    for rec in item["recordings"]:
                        if "title" in rec and "title" in tags:
                            x = rec["title"].lower()
                            y = tags["title"][0].lower()
                            z = min(len(x), len(y))
                            # if rec["title"].lower() != tags["title"][0].lower():
                            if x.find(y, 0, z) == -1 and y.find(x, 0, z) == -1:
                                print((
                                    'title "%s" does not match expected "%s"'
                                    % (rec["title"], tags["title"][0])
                                ))
                                print((
                                    "\thttps://acoustid.org/track/%s\n\thttps://musicbrainz.org/recording/%s\n\thttps://musicbrainz.org/release/%s"
                                    % (
                                        item["id"],
                                        tags["musicbrainz_recordingid"][0],
                                        tags["musicbrainz_albumid"][0],
                                    )
                                ))
                        if ("duration" in rec) and (
                            rec["duration"] < (dur - slop)
                            or rec["duration"] > (dur + slop)
                        ):
                            x, y = divmod(rec["duration"], 60)
                            h, m = divmod(dur, 60)
                            print((
                                "duration %02d:%02d does not match expected %02d:%02d"
                                % (x, y, h, m)
                            ))
                            print((
                                "\thttps://acoustid.org/track/%s\n\thttps://musicbrainz.org/recording/%s\n\thttps://musicbrainz.org/release/%s"
                                % (
                                    item["id"],
                                    tags["musicbrainz_recordingid"][0],
                                    tags["musicbrainz_albumid"][0],
                                )
                            ))
                        # repeat for artist
                        if rec["id"] == tags["musicbrainz_recordingid"][0]:
                            if item["id"] not in acoustid_ids:
                                # print("adding https://acoustid.org/track/%s" % (item["id"]))
                                acoustid_ids.append(item["id"])

        if len(acoustid_ids) > 0:
            if "acoustid_id" not in tags:
                print(("%s: [unset] -> %s" % (filename, acoustid_ids)))
                tags["acoustid_id"] = acoustid_ids
                changed = 1
            else:
                if sorted(acoustid_ids) != sorted(tags["acoustid_id"]):
                    print((
                        "%s: %s -> %s" % (filename, tags["acoustid_id"], acoustid_ids)
                    ))
                    tags["acoustid_id"] = acoustid_ids
                    changed = 1
        else:
            print(("no acoustIDs for %s" % (filename)))
            if "acoustid_ids" in tags:
                del tags["acoustid_ids"]
                changed = 1

        if changed != 0:
            try:
                print(("saving %s" % filename))
                tags.save()
            except Exception as e:
                print(("save failed: %s" % e))
                continue


def buildfilelist(args):
    srcfiles = []
    for item in args:
        try:
            iteminfo = os.stat(item)
        except (IOError, OSError):
            print(("File not found: %s" % (item)))
            continue

        if stat.S_ISREG(iteminfo.st_mode):
            filename, extension = os.path.splitext(item)
            if extension == ".flac":
                srcfiles.append(os.path.realpath(item))
        if stat.S_ISDIR(iteminfo.st_mode):
            for root, dirs, files in os.walk(item):
                for f in files:
                    filename, extension = os.path.splitext(f)
                    if extension == ".flac":
                        srcfiles.append(os.path.realpath(os.path.join(root, f)))
    return srcfiles


def timeouthandler(signum, frame):
    raise Exception("timeout reached")


if __name__ == "__main__":
    main()

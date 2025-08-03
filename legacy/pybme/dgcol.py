#!/usr/bin/python3
# -*- coding: utf-8 -*-
# written by Scot C. Bontrager, March 2016
# this file is public domain - more free than free
import os
import sys
import logging
import csv
import signal

# import pprint
# import string, stat
import pybme
from optparse import OptionParser

logger = logging.getLogger()
# import inspect, pprint


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

    (options, args) = parser.parse_args()

    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)

    if options.debug:
        logger.setLevel(logging.DEBUG)

    # I can't imagine anything other than the flac dir..., but if we need to expand we can
    options.srcdir = "/home/data"
    dirs = [os.path.join(options.srcdir, "flac")]

    collection = ""
    user = ""
    existing = []
    done = []

    params = {}
    # params['Content-Type'] = 'application/json'
    # params['Content-Type'] = 'application/x-www-form-urlencoded'
    # if bme could be initialized without a file, this would get cleaner...

    for dir in dirs:
        for sourcefile in sourcefiles(dir):
            bme = pybme.bmefile(sourcefile.encode("utf-8", "ignore"))
            if user is "":
                user = bme.dgclient.identity()
            if collection is "":
                collection = user.collection_folders
                logger.warn("getting existing collection...")
                for r in collection[0].releases:
                    # pprint.pprint(inspect.getmembers(r))
                    existing.append(r.id)
                logger.warn("existing: %s items", len(existing))
                # pprint.pprint(inspect.getmembers(collection[0]))
            if (
                "tracknumber" in bme.flactags
                and bme.flactags["tracknumber"][0] == "1"
                and "discnumber" in bme.flactags
                and bme.flactags["discnumber"][0] == "1"
            ):
                if "url_discogs_release_site" in bme.flactags:
                    url = bme.flactags["url_discogs_release_site"][0]
                    chunks = url.split("/")
                    dgid = int(chunks[4])
                    done.append(dgid)
                    if dgid not in existing:
                        logger.warn(
                            "adding: https://www.discogs.com/release/%s\n%s"
                            % (dgid, sourcefile)
                        )
                        try:
                            bme.dgclient._fetcher.fetch(
                                bme,
                                "POST",
                                "{0}/users/{1}/collection/folders/1/releases/{2}".format(
                                    bme.dgclient._base_url, "scot", dgid
                                ),
                            )
                            # bme.dgclient._fetcher.fetch(bme, 'POST', '{0}/users/{1}/collection/folders/1/releases/{2}'.format(bme.dgclient._base_url, "scot", dgid), headers=params, data={"username": "scot"})
                            # bme.dgclient._post('{0}/users/{1}/collection/folders/1/releases/{2}'.format(bme.dgclient._base_url, "scot", dgid), data={"username": "scot"}, headers=params)
                        except Exception as e:
                            logger.warn(
                                "discogs threw error: %s for %s %s"
                                % (e, dgid, sourcefile)
                            )

    # now make sure nothing was removed/changed, etc
    for dgid in existing:
        if dgid not in done:
            logger.warn(
                "{0} in discogs collection but not found locally; removing from collection".format(
                    dgid
                )
            )
            try:
                bme.dgclient._delete(
                    "{0}/users/{1}/collection/folders/1/releases/{2}/instances/0".format(
                        bme.dgclient._base_url, "scot", dgid
                    )
                )
            except Exception as e:
                logger.warn(
                    "discogs threw error: %s\nhttps://www.discogs.com/release/%s"
                    % (e, dgid)
                )


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

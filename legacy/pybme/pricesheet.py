#!/usr/bin/python3
# -*- coding: utf-8 -*-
# written by Scot C. Bontrager, March 2016
# this file is public domain - more free than free
import os
import sys
import logging
import csv
import signal
import pprint

# import string, stat
import pybme
from optparse import OptionParser
from amazonproduct import API
from amazonproduct import errors as AWSerrors
import inspect
import time

logger = logging.getLogger()

# import urllib3
# import certifi
# import urllib3.contrib.pyopenssl
# urllib3.contrib.pyopenssl.inject_into_urllib3()
# urllib3.disable_warnings()
# http = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_certs=certifi.where())


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
        "-O",
        "--csv",
        help="output CSV file (/home/data/bme-working/pricelist.csv)",
        action="store",
        type="string",
        dest="outfile",
        default="/home/data/bme-working/pricelist.csv",
    )

    (options, args) = parser.parse_args()

    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARN)
    logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.WARN)
    logging.getLogger("oauthlib.oauth1.rfc5849").setLevel(logging.WARN)
    logging.getLogger("musicbrainzngs").setLevel(logging.WARN)

    if options.debug:
        logger.setLevel(logging.DEBUG)

    options.srcdir = "/home/data"
    dirs = [os.path.join(options.srcdir, "flac")]

    with open(options.outfile, "wb") as csvfile:
        outfile = csv.writer(csvfile, dialect="excel")
        outfile.writerow(
            [
                "Artist",
                "Release",
                "Medium",
                "Record Label",
                "Catalog Number",
                "Discogs URL",
                "Discogs Suggested Price",
                "Amazon ASIN",
                "Amazon Price",
                "Value",
            ]
        )

        for dir in dirs:
            for sourcefile in sourcefiles(dir):
                dgprice = 0
                url = ""
                artist = ""
                album = ""
                media = ""
                label = ""
                catno = ""
                asin = "unset"
                azprice = 0
                value = 0
                bme = pybme.bmefile(sourcefile.encode("utf-8", "ignore"))
                bme.amazon = True
                bme.newtags = bme.flactags
                if (
                    "tracknumber" in bme.flactags
                    and bme.flactags["tracknumber"][0] == "1"
                    and "discnumber" in bme.flactags
                    and bme.flactags["discnumber"][0] == "1"
                ):
                    if "url_discogs_release_site" in bme.flactags:
                        url = bme.flactags["url_discogs_release_site"][0]
                        try:
                            chunks = url.split("/")
                            dgid = int(chunks[4])
                            signal.alarm(bme.timeout)
                            prices = bme.dgclient._get(
                                "{0}/marketplace/price_suggestions/{1}".format(
                                    bme.dgclient._base_url, dgid
                                )
                            )
                            price_exp = prices["Very Good Plus (VG+)"]
                            dgprice = "{0:.2f}".format(price_exp["value"])
                        except Exception as e:
                            logger.info("Fetching discogs price: %s" % (e))
                        finally:
                            signal.alarm(0)
                    else:
                        bme.findDiscogs()

                    if "asin" in bme.flactags:
                        index = 0
                        while bme.flactags["asin"][index].startswith("http://"):
                            index = index + 1
                        asin = bme.flactags["asin"][index].encode("utf-8")
                        api = API(locale="us")
                        try:
                            logger.debug("checking Amazon for: %s" % (bme.filename))
                            result = api.item_lookup(
                                asin, ResponseGroup="OfferFull", Condition="All"
                            )
                            for item in result.Items.Item:
                                time.sleep(1)
                                # logger.warn(pprint.pprint(inspect.getmembers(item.OfferSummary)))
                                if (
                                    "LowestCollectiblePrice"
                                    in item.OfferSummary.__dict__
                                    and item.OfferSummary.LowestCollectiblePrice.Amount
                                    > 0
                                ):
                                    azprice = (
                                        float(
                                            item.OfferSummary.LowestCollectiblePrice.Amount
                                        )
                                        / 100
                                    )
                                if (
                                    azprice == 0
                                    and "LowestUsedPrice" in item.OfferSummary.__dict__
                                    and item.OfferSummary.LowestUsedPrice.Amount > 0
                                ):
                                    azprice = (
                                        float(item.OfferSummary.LowestUsedPrice.Amount)
                                        / 100
                                    )
                                if (
                                    azprice == 0
                                    and "LowestNewPrice" in item.OfferSummary.__dict__
                                    and item.OfferSummary.LowestNewPrice.Amount > 0
                                ):
                                    azprice = (
                                        float(item.OfferSummary.LowestNewPrice.Amount)
                                        / 100
                                    )
                        except Exception as e:
                            logger.debug("amazon threw error: %s" % (e))
                    else:
                        time.sleep(3)
                        bme.findAmazon()

                    if azprice > dgprice:
                        value = azprice
                    else:
                        value = dgprice

                    if "artist" in bme.flactags:
                        artist = bme.flactags["artist"][0].encode("utf-8")
                    if "album" in bme.flactags:
                        album = bme.flactags["album"][0].encode("utf-8")
                    if "media" in bme.flactags:
                        media = bme.flactags["media"][0].encode("utf-8")
                    if "label" in bme.flactags:
                        label = bme.flactags["label"][0].encode("utf-8")
                    if "catalognumber" in bme.flactags:
                        catno = bme.flactags["catalognumber"][0].encode("utf-8")
                    logger.info(
                        "%s %s %s %s %s %s %s %s %s"
                        % (
                            artist,
                            album,
                            media,
                            label,
                            catno,
                            dgprice,
                            asin,
                            azprice,
                            value,
                        )
                    )
                    outfile.writerow(
                        [
                            artist,
                            album,
                            media,
                            label,
                            catno,
                            url,
                            dgprice,
                            asin,
                            azprice,
                            value,
                        ]
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

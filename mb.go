package bme

import (
	// "fmt"
	"log/slog"
	"strings"
	"unsafe"
)

type mb_release struct {
	DiscID       string // done
	ReleaseID    string // done
	AlbumArtist  string // done
	Title        string // done
	DiscPosition int    // done
	Tracks       []mb_track
}

type mb_track struct {
	Position int    // done
	TrackID  string // get from recording?
	Artist   string //
	Title    string // done
}

// https://github.com/metabrainz/libmusicbrainz/blob/4efbed3afae11ef68281816088d7cf3d0f704dfe/tests/ctest.c
func mb_lookup_discid(mbid string) mb_release {
	var mbr mb_release

	mbr.DiscID = mbid

	query := mb5_query_new("bme-tag-0.0", "musicbrainz.org", 0)
	if query == nil {
		slog.Error("mb_lookup_discid", "unable to get query")
		return mbr
	}

	metadata1 := mb5_query_query(query, "discid", mbid, "", 0, nil, nil)
	metadata1 = mb5_metadata_clone(metadata1)
	defer mb5_metadata_delete(metadata1)

	result := mb5_query_get_lastresult(query)
	if result != 0 {
		mb_error_message("last query result", query)
		return mbr
	}
	if metadata1 == nil {
		slog.Info("mb_lookup_discid", "msg", "no results")
		return mbr
	}

	disc := mb5_metadata_get_disc(metadata1)
	if disc == nil {
		mb_error_message("get_disc", query)
		return mbr
	}

	disc = mb5_disc_clone(disc)
	defer mb5_disc_delete(disc)

	rl := mb5_disc_get_releaselist(disc)
	if rl == nil {
		mb_error_message("get_releaselist", query)
		return mbr
	}
	rl = mb5_release_list_clone(rl)
	defer mb5_release_list_delete(rl)

	rcount := mb5_release_list_size(rl)
	for e := 0; e < rcount; e++ {
		shortrelease := mb5_release_list_item(rl, e)

		shortrelease = mb5_release_clone(shortrelease)
		defer mb5_release_delete(shortrelease)

		var releaseID [37]byte
		mb5_release_get_id(shortrelease, unsafe.Pointer(&releaseID[0]), 37)
		mbr.ReleaseID = strings.Trim(string(releaseID[:]), "\x00")

		var title [256]byte
		mb5_release_get_title(shortrelease, unsafe.Pointer(&title[0]), 256)
		mbr.Title = strings.Trim(string(title[:]), "\x00")

		var params [1]*byte
		p1 := []byte("inc")
		params[0] = &p1[0]

		var values [1]*byte
		v1 := []byte("artists labels recordings release-groups url-rels discids artist-credits")
		values[0] = &v1[0]

		metadata2 := mb5_query_query(query, "release", mbr.ReleaseID, "", 1, unsafe.Pointer(&params), unsafe.Pointer(&values))
		if metadata2 == nil {
			mb_error_message("metadata2 nil", query)
			continue
		}
		metadata2 = mb5_metadata_clone(metadata2)
		defer mb5_metadata_delete(metadata2)

		fullrelease := mb5_metadata_get_release(metadata2)
		if fullrelease == nil {
			mb_error_message("full release nil", query)
			continue
		}
		// clone/delete

		medialist := mb5_release_media_matching_discid(fullrelease, mbid)
		if medialist == nil {
			mb_error_message("medialist nil", query)
			continue
		}

		mls := mb5_medium_list_size(medialist)
		if mls == 0 {
			mb_error_message("zero medialist items", query)
			continue
		}

		medium := mb5_medium_list_item(medialist, 0)
		if medium == nil {
			mb_error_message("medium nil", query)
			continue
		}
		mbr.DiscPosition = mb5_medium_get_position(medium)

		tracklist := mb5_medium_get_tracklist(medium)
		if tracklist == nil {
			continue
		}
		tracklist = mb5_track_list_clone(tracklist)
		defer mb5_track_list_delete(tracklist)

		trackcount := mb5_track_list_get_count(tracklist)
		// slog.Info("mb_lookup_discid", "trackcount from tracklist", trackcount)

		for j := 0; j < trackcount; j++ {
			var tmp mb_track

			track := mb5_track_list_item(tracklist, j)
			// slog.Info("mb_lookup_discid", "track", track)
			if track == nil {
				continue
			}

			tmp.Position = mb5_track_get_position(track)

			rec := mb5_track_get_recording(track)
			if rec != nil {
				var buf [256]byte
				mb5_recording_get_id(rec, &buf[0], 255)
				tmp.TrackID = strings.Trim(string(buf[:]), "\x00")

				var title [256]byte
				mb5_recording_get_title(rec, &title[0], 255)
				tmp.Title = strings.Trim(string(title[:]), "\x00")
				// slog.Info("mb_lookup_discid", "recordingID", tmp.TrackID, "title", tmp.Title)
			} else {
				var title [256]byte
				mb5_track_get_title(track, &title[0], 255)
				tmp.Title = strings.Trim(string(title[:]), "\x00")
				// slog.Info("mb_lookup_discid", "track title", tmp.Title)
			}

			ac := mb5_track_get_artistcredit(track)
			// slog.Info("mb_lookup_discid", "artist credit", ac)
			if ac != nil {
				var fullartistname strings.Builder

				ncl := mb5_artistcredit_get_namecreditlist(ac)
				slog.Info("mb_lookup_discid", "name credit list", ncl)
				// clone/delete ?
				credits := mb5_namecredit_list_get_count(ncl)
				slog.Info("mb_lookup_discid", "credits", credits)
				for k := 0; k < credits; k++ {
					nc := mb5_namecredit_list_item(ncl, k)
					if nc == nil {
						continue
					}

					var buf [256]byte
					mb5_namecredit_get_name(nc, &buf[0], 256)
					n := strings.Trim(string(buf[:]), "\x00")
					if n != "" {
						fullartistname.WriteString(n)
					}
					mb5_namecredit_get_joinphrase(nc, &buf[0], 256)
					n = strings.Trim(string(buf[:]), "\x00")
					if n != "" {
						fullartistname.WriteString(n)
					}
				}
				tmp.Artist = fullartistname.String()
				slog.Info("mb_lookup_discid", "full artist name", tmp.Artist)
			}
			mbr.Tracks = append(mbr.Tracks, tmp)
		}
	}

	return mbr
}

func mb_error_message(msg string, query mb5_query) {
	result := mb5_query_get_lastresult(query)
	slog.Info("mb_lookup_discid", "last query result", result)

	var errbuf [256]byte
	mb5_query_get_lasterrormessage(query, &errbuf[0], 256)
	slog.Info("mb_lookup_discid", "msg", msg, "err", strings.Trim(string(errbuf[:]), "\x00"))
}

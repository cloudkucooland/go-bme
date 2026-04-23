package bme

import (
	"testing"
	"unsafe"
)

func TestArtistCreditJoining(t *testing.T) {
	// Mock mb5 functions
	old_mb5_query_new := mb5_query_new
	old_mb5_query_query := mb5_query_query
	old_mb5_metadata_clone := mb5_metadata_clone
	old_mb5_metadata_delete := mb5_metadata_delete
	old_mb5_query_get_lastresult := mb5_query_get_lastresult
	old_mb5_metadata_get_disc := mb5_metadata_get_disc
	old_mb5_disc_clone := mb5_disc_clone
	old_mb5_disc_delete := mb5_disc_delete
	old_mb5_disc_get_releaselist := mb5_disc_get_releaselist
	old_mb5_release_list_clone := mb5_release_list_clone
	old_mb5_release_list_delete := mb5_release_list_delete
	old_mb5_release_list_size := mb5_release_list_size
	old_mb5_release_list_item := mb5_release_list_item
	old_mb5_release_clone := mb5_release_clone
	old_mb5_release_delete := mb5_release_delete
	old_mb5_release_get_id := mb5_release_get_id
	old_mb5_release_get_title := mb5_release_get_title
	old_mb5_release_media_matching_discid := mb5_release_media_matching_discid
	old_mb5_medium_list_size := mb5_medium_list_size
	old_mb5_medium_list_item := mb5_medium_list_item
	old_mb5_medium_get_position := mb5_medium_get_position
	old_mb5_medium_get_tracklist := mb5_medium_get_tracklist
	old_mb5_track_list_clone := mb5_track_list_clone
	old_mb5_track_list_delete := mb5_track_list_delete
	old_mb5_track_list_get_count := mb5_track_list_get_count
	old_mb5_track_list_item := mb5_track_list_item
	old_mb5_track_get_position := mb5_track_get_position
	old_mb5_track_get_recording := mb5_track_get_recording
	old_mb5_recording_get_id := mb5_recording_get_id
	old_mb5_recording_get_title := mb5_recording_get_title
	old_mb5_recording_get_artistcredit := mb5_recording_get_artistcredit
	old_mb5_artistcredit_get_namecreditlist := mb5_artistcredit_get_namecreditlist
	old_mb5_namecredit_list_get_count := mb5_namecredit_list_get_count
	old_mb5_namecredit_list_item := mb5_namecredit_list_item
	old_mb5_namecredit_get_name := mb5_namecredit_get_name
	old_mb5_namecredit_get_joinphrase := mb5_namecredit_get_joinphrase
	old_mb5_metadata_get_release := mb5_metadata_get_release
	old_mb5_namecredit_get_artist := mb5_namecredit_get_artist
	old_mb5_artist_get_name := mb5_artist_get_name

	defer func() {
		mb5_query_new = old_mb5_query_new
		mb5_query_query = old_mb5_query_query
		mb5_metadata_clone = old_mb5_metadata_clone
		mb5_metadata_delete = old_mb5_metadata_delete
		mb5_query_get_lastresult = old_mb5_query_get_lastresult
		mb5_metadata_get_disc = old_mb5_metadata_get_disc
		mb5_disc_clone = old_mb5_disc_clone
		mb5_disc_delete = old_mb5_disc_delete
		mb5_disc_get_releaselist = old_mb5_disc_get_releaselist
		mb5_release_list_clone = old_mb5_release_list_clone
		mb5_release_list_delete = old_mb5_release_list_delete
		mb5_release_list_size = old_mb5_release_list_size
		mb5_release_list_item = old_mb5_release_list_item
		mb5_release_clone = old_mb5_release_clone
		mb5_release_delete = old_mb5_release_delete
		mb5_release_get_id = old_mb5_release_get_id
		mb5_release_get_title = old_mb5_release_get_title
		mb5_release_media_matching_discid = old_mb5_release_media_matching_discid
		mb5_medium_list_size = old_mb5_medium_list_size
		mb5_medium_list_item = old_mb5_medium_list_item
		mb5_medium_get_position = old_mb5_medium_get_position
		mb5_medium_get_tracklist = old_mb5_medium_get_tracklist
		mb5_track_list_clone = old_mb5_track_list_clone
		mb5_track_list_delete = old_mb5_track_list_delete
		mb5_track_list_get_count = old_mb5_track_list_get_count
		mb5_track_list_item = old_mb5_track_list_item
		mb5_track_get_position = old_mb5_track_get_position
		mb5_track_get_recording = old_mb5_track_get_recording
		mb5_recording_get_id = old_mb5_recording_get_id
		mb5_recording_get_title = old_mb5_recording_get_title
		mb5_recording_get_artistcredit = old_mb5_recording_get_artistcredit
		mb5_artistcredit_get_namecreditlist = old_mb5_artistcredit_get_namecreditlist
		mb5_namecredit_list_get_count = old_mb5_namecredit_list_get_count
		mb5_namecredit_list_item = old_mb5_namecredit_list_item
		mb5_namecredit_get_name = old_mb5_namecredit_get_name
		mb5_namecredit_get_joinphrase = old_mb5_namecredit_get_joinphrase
		mb5_metadata_get_release = old_mb5_metadata_get_release
		mb5_namecredit_get_artist = old_mb5_namecredit_get_artist
		mb5_artist_get_name = old_mb5_artist_get_name
	}()

	realDummy := 1
	dummy := unsafe.Pointer(&realDummy)

	mb5_query_new = func(a, b string, c int) mb5_query { return mb5_query(dummy) }
	mb5_query_query = func(a mb5_query, b, c, d string, e int, f, g unsafe.Pointer) mb5_metadata { return mb5_metadata(dummy) }
	mb5_metadata_clone = func(a mb5_metadata) mb5_metadata { return a }
	mb5_metadata_delete = func(a mb5_metadata) {}
	mb5_query_get_lastresult = func(a mb5_query) mb5_tQueryResult { return 0 }
	mb5_metadata_get_disc = func(a mb5_metadata) mb5_disc { return mb5_disc(dummy) }
	mb5_disc_clone = func(a mb5_disc) mb5_disc { return a }
	mb5_disc_delete = func(a mb5_disc) {}
	mb5_disc_get_releaselist = func(a mb5_disc) mb5_release_list { return mb5_release_list(dummy) }
	mb5_release_list_clone = func(a mb5_release_list) mb5_release_list { return a }
	mb5_release_list_delete = func(a mb5_release_list) {}
	mb5_release_list_size = func(a mb5_release_list) int { return 1 }
	mb5_release_list_item = func(a mb5_release_list, b int) mb5_release { return mb5_release(dummy) }
	mb5_release_clone = func(a mb5_release) mb5_release { return a }
	mb5_release_delete = func(a mb5_release) {}
	mb5_release_get_id = func(a mb5_release, b unsafe.Pointer, c int) {
		buf := (*[37]byte)(b)
		for i := range buf {
			buf[i] = 0
		}
		copy(buf[:], "release-id-123")
	}
	mb5_release_get_title = func(a mb5_release, b unsafe.Pointer, c int) {
		buf := (*[256]byte)(b)
		for i := range buf {
			buf[i] = 0
		}
		copy(buf[:], "Test Album")
	}
	mb5_metadata_get_release = func(a mb5_metadata) mb5_release { return mb5_release(dummy) }
	mb5_release_media_matching_discid = func(a mb5_release, b string) mb5_media_list { return mb5_media_list(dummy) }
	mb5_medium_list_size = func(a mb5_media_list) int { return 1 }
	mb5_medium_list_item = func(a mb5_media_list, b int) mb5_medium { return mb5_medium(dummy) }
	mb5_medium_get_position = func(a mb5_medium) int { return 1 }
	mb5_medium_get_tracklist = func(a mb5_medium) mb5_track_list { return mb5_track_list(dummy) }
	mb5_track_list_clone = func(a mb5_track_list) mb5_track_list { return a }
	mb5_track_list_delete = func(a mb5_track_list) {}
	mb5_track_list_get_count = func(a mb5_track_list) int { return 1 }
	mb5_track_list_item = func(a mb5_track_list, b int) mb5_track { return mb5_track(dummy) }
	mb5_track_get_position = func(a mb5_track) int { return 1 }
	mb5_track_get_recording = func(a mb5_track) mb5_recording { return mb5_recording(dummy) }
	mb5_recording_get_id = func(a mb5_recording, b *byte, c int) {
		buf := (*[37]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
		copy(buf[:], "recording-id-456")
	}
	mb5_recording_get_title = func(a mb5_recording, b *byte, c int) {
		buf := (*[256]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
		copy(buf[:], "Test Track")
	}
	mb5_recording_get_artistcredit = func(a mb5_recording) mb5_artist_credit { return mb5_artist_credit(dummy) }
	mb5_artistcredit_get_namecreditlist = func(a mb5_artist_credit) mb5_namecreditlist { return mb5_namecreditlist(dummy) }

	artists := []string{"Artist A", "Artist B"}
	joins := []string{" & ", " "}

	mb5_namecredit_list_get_count = func(a mb5_namecreditlist) int { return 2 }
	mb5_namecredit_list_item = func(a mb5_namecreditlist, b int) mb5_namecredit {
		return mb5_namecredit(uintptr(dummy) + uintptr(b))
	}
	mb5_namecredit_get_name = func(a mb5_namecredit, b *byte, c int) {
		idx := int(uintptr(a) - uintptr(dummy))
		buf := (*[256]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
		copy(buf[:], artists[idx])
	}
	mb5_namecredit_get_joinphrase = func(a mb5_namecredit, b *byte, c int) {
		idx := int(uintptr(a) - uintptr(dummy))
		buf := (*[256]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
		copy(buf[:], joins[idx])
	}
	mb5_namecredit_get_artist = func(a mb5_namecredit) mb5_artist { return mb5_artist(dummy) }
	mb5_artist_get_name = func(a mb5_artist, b *byte, c int) {
		buf := (*[256]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
	}

	mbr := mb_lookup_discid("test-discid")

	if mbr.Title != "Test Album" {
		t.Errorf("expected title Test Album, got %s", mbr.Title)
	}

	if len(mbr.Tracks) != 1 {
		t.Fatalf("expected 1 track, got %d", len(mbr.Tracks))
	}

	expectedArtist := "Artist A & Artist B "
	if mbr.Tracks[0].Artist != expectedArtist {
		t.Errorf("expected artist %s, got %s", expectedArtist, mbr.Tracks[0].Artist)
	}
}

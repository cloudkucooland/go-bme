package bme

import (
	"strings"
	"testing"
	"unsafe"
)

func TestMBLookup(t *testing.T) {
	// Mock implementation for testing
	dummy := 1
	mb5_query_new = func(a, b string, c int) mb5_query { return mb5_query(unsafe.Pointer(&dummy)) }
	mb5_query_query = func(a mb5_query, b, c, d string, e int, f, g unsafe.Pointer) mb5_metadata {
		return mb5_metadata(unsafe.Pointer(&dummy))
	}
	mb5_metadata_clone = func(a mb5_metadata) mb5_metadata { return a }
	mb5_metadata_delete = func(a mb5_metadata) {}
	mb5_query_get_lastresult = func(a mb5_query) mb5_tQueryResult { return 0 }
	mb5_metadata_get_disc = func(a mb5_metadata) mb5_disc { return mb5_disc(unsafe.Pointer(&dummy)) }
	mb5_disc_clone = func(a mb5_disc) mb5_disc { return a }
	mb5_disc_delete = func(a mb5_disc) {}
	mb5_disc_get_releaselist = func(a mb5_disc) mb5_release_list { return mb5_release_list(unsafe.Pointer(&dummy)) }
	mb5_release_list_clone = func(a mb5_release_list) mb5_release_list { return a }
	mb5_release_list_delete = func(a mb5_release_list) {}
	mb5_release_list_size = func(a mb5_release_list) int { return 1 }
	mb5_release_list_item = func(a mb5_release_list, b int) mb5_release { return mb5_release(unsafe.Pointer(&dummy)) }
	mb5_release_clone = func(a mb5_release) mb5_release { return a }
	mb5_release_delete = func(a mb5_release) {}
	mb5_release_get_id = func(a mb5_release, b unsafe.Pointer, c int) {
		copy((*[37]byte)(b)[:], "test-release-id")
	}
	mb5_release_get_title = func(a mb5_release, b unsafe.Pointer, c int) {
		copy((*[256]byte)(b)[:], "Test Album")
	}
	mb5_metadata_get_release = func(a mb5_metadata) mb5_release { return mb5_release(unsafe.Pointer(&dummy)) }
	mb5_release_get_country = func(a mb5_release, b unsafe.Pointer, c int) {}
	mb5_release_get_barcode = func(a mb5_release, b unsafe.Pointer, c int) {}
	mb5_release_get_disambiguation = func(a mb5_release, b unsafe.Pointer, c int) {}
	mb5_release_media_matching_discid = func(a mb5_release, b string) mb5_media_list {
		return mb5_media_list(unsafe.Pointer(&dummy))
	}
	mb5_medium_list_size = func(a mb5_media_list) int { return 1 }
	mb5_medium_list_item = func(a mb5_media_list, b int) mb5_medium { return mb5_medium(unsafe.Pointer(&dummy)) }
	mb5_medium_get_tracklist = func(a mb5_medium) mb5_track_list { return mb5_track_list(unsafe.Pointer(&dummy)) }
	mb5_track_list_clone = func(a mb5_track_list) mb5_track_list { return a }
	mb5_track_list_delete = func(a mb5_track_list) {}
	mb5_track_list_get_count = func(a mb5_track_list) int { return 1 }
	mb5_medium_get_position = func(a mb5_medium) int { return 1 }
	mb5_track_list_item = func(a mb5_track_list, b int) mb5_track { return mb5_track(unsafe.Pointer(&dummy)) }
	mb5_track_get_position = func(a mb5_track) int { return 1 }
	mb5_track_get_recording = func(a mb5_track) mb5_recording { return mb5_recording(unsafe.Pointer(&dummy)) }
	mb5_recording_get_id = func(a mb5_recording, b *byte, c int) {}
	mb5_recording_get_title = func(a mb5_recording, b *byte, c int) {
		copy((*[256]byte)(unsafe.Pointer(b))[:], "Test Track")
	}
	mb5_recording_get_artistcredit = func(a mb5_recording) mb5_artist_credit {
		return mb5_artist_credit(unsafe.Pointer(&dummy))
	}
	mb5_artistcredit_get_namecreditlist = func(a mb5_artist_credit) mb5_namecreditlist {
		return mb5_namecreditlist(unsafe.Pointer(&dummy))
	}
	mb5_namecredit_list_get_count = func(a mb5_namecreditlist) int {
		return 2
	}

	names := []string{"Artist A", "Artist B"}
	joins := []string{" & ", ""}
	mb5_namecredit_list_item = func(a mb5_namecreditlist, b int) mb5_namecredit {
		return mb5_namecredit(uintptr(b + 1)) // Shift by 1 to avoid 0 (nil)
	}
	mb5_namecredit_get_name = func(a mb5_namecredit, b *byte, c int) {
		idx := int(uintptr(unsafe.Pointer(a))) - 1
		buf := (*[256]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
		if idx >= 0 && idx < len(names) {
			copy(buf[:], names[idx])
		}
	}
	mb5_namecredit_get_joinphrase = func(a mb5_namecredit, b *byte, c int) {
		idx := int(uintptr(unsafe.Pointer(a))) - 1
		buf := (*[256]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
		if idx >= 0 && idx < len(joins) {
			copy(buf[:], joins[idx])
		}
	}
	mb5_namecredit_get_artist = func(a mb5_namecredit) mb5_artist { return mb5_artist(unsafe.Pointer(&dummy)) }
	mb5_artist_get_name = func(a mb5_artist, b *byte, c int) {
		buf := (*[256]byte)(unsafe.Pointer(b))
		for i := range buf {
			buf[i] = 0
		}
	}

	releases := mb_lookup_discid("test-discid", 1)

	if len(releases) != 1 {
		t.Fatalf("expected 1 release, got %d", len(releases))
	}

	mbr := releases[0]
	if mbr.Title != "Test Album" {
		t.Errorf("expected title Test Album, got %s", mbr.Title)
	}

	if len(mbr.Tracks) != 1 {
		t.Fatalf("expected 1 track, got %d", len(mbr.Tracks))
	}

	expectedArtist := "Artist A & Artist B"
	if strings.TrimSpace(mbr.Tracks[0].Artist) != expectedArtist {
		t.Errorf("expected artist %s, got '%s'", expectedArtist, mbr.Tracks[0].Artist)
	}
}

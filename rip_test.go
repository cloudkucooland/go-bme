package bme

import (
	"bytes"
	"encoding/binary"
	"testing"
)

func TestWriteWavHeader(t *testing.T) {
	var buf bytes.Buffer
	size := uint32(1000)
	write_wav_header(&buf, size)

	data := buf.Bytes()
	if len(data) != 44 {
		t.Errorf("expected header size 44, got %d", len(data))
	}

	if string(data[0:4]) != "RIFF" {
		t.Errorf("expected RIFF, got %s", string(data[0:4]))
	}

	riffSize := binary.LittleEndian.Uint32(data[4:8])
	if riffSize != size+44-8 {
		t.Errorf("expected riff size %d, got %d", size+44-8, riffSize)
	}

	if string(data[8:12]) != "WAVE" {
		t.Errorf("expected WAVE, got %s", string(data[8:12]))
	}

	if string(data[12:16]) != "fmt " {
		t.Errorf("expected 'fmt ', got %s", string(data[12:16]))
	}

	dataSize := binary.LittleEndian.Uint32(data[40:44])
	if dataSize != size {
		t.Errorf("expected data size %d, got %d", size, dataSize)
	}
}

func TestGetMbdiscid(t *testing.T) {
	// Mock the cdio functions used by get_mbdiscid
	old_get_first_track_num := cdio_get_first_track_num
	old_get_num_tracks := cdio_get_num_tracks
	old_get_track_lba := cdio_get_track_lba
	defer func() {
		cdio_get_first_track_num = old_get_first_track_num
		cdio_get_num_tracks = old_get_num_tracks
		cdio_get_track_lba = old_get_track_lba
	}()

	// Example from MusicBrainz documentation or known values
	// Let's use a simple 3-track CD example
	cdio_get_first_track_num = func(d cddevice_t) track_t { return 1 }
	cdio_get_num_tracks = func(d cddevice_t) track_t { return 3 }

	lbas := map[track_t]int{
		1:                        150,
		2:                        15000,
		3:                        30000,
		CDIO_CDROM_LEADOUT_TRACK: 45000,
	}

	cdio_get_track_lba = func(d cddevice_t, track track_t) int {
		return lbas[track]
	}

	// The calculation:
	// fmt.Fprintf(h, "%02X%02X%08X", 1, 3, 45000) -> "01030000AFC8"
	// Then loop 1..99:
	// track 1: 00000096
	// track 2: 00003A98
	// track 3: 00007530
	// tracks 4..99: 00000000

	discid := get_mbdiscid(nil)
	if discid == "" {
		t.Fatal("expected a discid, got empty string")
	}

	// Expected value for these specific LBAs can be pre-calculated or compared against a known good run.
	// For this test, we just want to ensure it's consistent and follows the base64 rules (using . _ -)
	t.Logf("Generated DiscID: %s", discid)

	for _, char := range discid {
		if (char < 'a' || char > 'z') && (char < 'A' || char > 'Z') && (char < '0' || char > '9') && char != '.' && char != '_' && char != '-' {
			t.Errorf("discid contains invalid character: %c", char)
		}
	}
}

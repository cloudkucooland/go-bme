package bme

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/Sorrow446/go-mp4tag"
	"log/slog"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

// Channel for TUI to send selection back to tagger
var selectionChan = make(chan mb_release)

func tagger(ctx context.Context, p *tea.Program) {
	if p != nil {
		p.Send(StatusMsg{"tagger", "Starting"})
	}

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if err := tag_process_directories(ctx, p); err != nil {
				slog.Error("tagger failed", "error", err)
				if p != nil {
					p.Send(StatusMsg{"tagger", fmt.Sprintf("Error: %v", err)})
				}
			}
		case <-ctx.Done():
			if p != nil {
				p.Send(StatusMsg{"tagger", "Stopped"})
			}
			return
		}
	}
}

func tag_process_directories(ctx context.Context, p *tea.Program) error {
	albums, err := os.ReadDir(tagdir)
	if err != nil {
		return fmt.Errorf("unable to read tag directory: %w", err)
	}
	if len(albums) == 0 {
		if p != nil {
			// p.Send(StatusMsg{"tagger", "Idle"})
		}
		return nil
	}

	for i := range albums {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		mbid := albums[i].Name()
		if p != nil {
			p.Send(ProgressMsg{"tagger", 0.0})
			p.Send(StatusMsg{"tagger", fmt.Sprintf("Tagging %s...", mbid)})
		}
		if err := tag_process_directory(ctx, mbid, p); err != nil {
			slog.Error("failed to process directory", "mbid", mbid, "error", err)
			if p != nil {
				p.Send(StatusMsg{"tagger", fmt.Sprintf("Error [%s]: %v", mbid, err)})
			}
		}
	}
	return nil
}

func tag_process_directory(ctx context.Context, mbid string, p *tea.Program) error {
	d := filepath.Join(tagdir, mbid)
	files, err := os.ReadDir(d)
	if err != nil {
		return fmt.Errorf("unable to read directory %s: %w", d, err)
	}

	ripdata := load_ripdata(tagdir, mbid)
	var mbdata mb_release

	// Check if we already have a selection
	selectedPath := filepath.Join(d, "selected_mbdata.json")
	if data, err := os.ReadFile(selectedPath); err == nil {
		json.Unmarshal(data, &mbdata)
	} else {
		releases := mb_lookup_discid(mbid, int(ripdata.Trackcount))
		if len(releases) == 0 {
			if p != nil {
				p.Send(StatusMsg{"tagger", "No MB matches, using CD-Text"})
			}
			// Fallback: Create mbdata from ripdata
			mbdata = mb_release{
				DiscID:      mbid,
				AlbumArtist: ripdata.Performer,
				Title:       ripdata.Title,
				Tracks:      make([]mb_track, len(ripdata.Tracks)),
			}
			for i, rt := range ripdata.Tracks {
				mbdata.Tracks[i] = mb_track{
					Position: int(rt.ID),
					Title:    rt.Title,
					Artist:   rt.Performer,
				}
			}
		} else if len(releases) == 1 {
			mbdata = releases[0]
		} else {
			// Multiple matches - trigger TUI menu
			if p != nil {
				p.Send(MBMatchesMsg{MBID: mbid, Releases: releases})
				// Wait for selection
				select {
				case mbdata = <-selectionChan:
					// save for next time
					if bytes, err := json.Marshal(mbdata); err == nil {
						os.WriteFile(selectedPath, bytes, 0644)
					}
				case <-ctx.Done():
					return ctx.Err()
				case <-time.After(time.Minute * 10):
					return fmt.Errorf("timeout waiting for release selection for %s", mbid)
				}
			} else {
				mbdata = releases[0]
			}
		}
	}

	// do work
	processed := 0
	total := 0
	for _, f := range files {
		if strings.HasSuffix(f.Name(), ".m4a") {
			total++
		}
	}

	for _, f := range files {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		if !strings.HasSuffix(f.Name(), ".m4a") {
			continue
		}

		if err := tag_file(d, f.Name(), mbid, ripdata, mbdata); err != nil {
			slog.Error("failed to tag file", "file", f.Name(), "error", err)
		} else {
			processed++
			if p != nil {
				p.Send(StatusMsg{"tagger", fmt.Sprintf("[%s] %d/%d", mbid, processed, total)})
				p.Send(ProgressMsg{"tagger", float64(processed) / float64(total)})
			}
		}
	}

	// move to done directory
	if p != nil {
		p.Send(StatusMsg{"tagger", "Finishing..."})
	}
	t := filepath.Join(finaldir, mbid)
	if err := os.Rename(d, t); err != nil {
		return fmt.Errorf("failed to move to final directory: %w", err)
	}
	return nil
}

func tag_file(d, filename, mbid string, ripdata ripdisc_t, mbdata mb_release) error {
	newtags := mp4tag.MP4Tags{
		ItunesAdvisory: 0,
		ItunesAlbumID:  -1,
		ItunesArtistID: -1,
	}

	newtags.Custom = make(map[string]string)
	newtags.Custom["MusicBrainz Disc Id"] = mbid
	if ripdata.TOC != "" {
		newtags.Custom["TOC"] = ripdata.TOC
	}

	if ripdata.MCN != "" {
		newtags.Custom["MCN"] = ripdata.MCN
	}
	if ripdata.UPC_EAN != "" {
		newtags.Custom["UPC"] = ripdata.UPC_EAN
	}

	if mbdata.ReleaseID != "" {
		newtags.Custom["MusicBrainz Album Id"] = mbdata.ReleaseID
	}
	if mbdata.AlbumArtist != "" {
		newtags.AlbumArtist = mbdata.AlbumArtist
	}
	if mbdata.Title != "" {
		newtags.Album = mbdata.Title
	}
	if mbdata.DiscPosition != 0 {
		newtags.DiscNumber = int16(mbdata.DiscPosition)
	}

	if ripdata.Genre != "" {
		newtags.Custom["Genre"] = ripdata.Genre
	}
	if ripdata.Trackcount != 0 {
		newtags.TrackTotal = int16(ripdata.Trackcount)
	}

	pos, err := strconv.Atoi(filename[0:2])
	if err != nil {
		return fmt.Errorf("invalid track number prefix in %s: %w", filename, err)
	}

	newtags.TrackNumber = int16(pos)

	for _, t := range mbdata.Tracks {
		if t.Position == pos {
			if t.Title != "" {
				newtags.Title = t.Title
			}
			if t.TrackID != "" {
				newtags.Custom["MusicBrainz Release Track Id"] = t.TrackID
				newtags.Custom["MusicBrainz Track Id"] = t.TrackID
			}
			if t.Artist != "" {
				newtags.Artist = t.Artist
			}
		}
	}

	for _, t := range ripdata.Tracks {
		if int(t.ID) == pos {
			if t.ISRC != "" {
				newtags.Custom["ISRC"] = t.ISRC
			}
			if t.Composer != "" {
				newtags.Custom["Composer"] = t.Composer
			}
			if t.Songwriter != "" {
				newtags.Custom["Songwriter"] = t.Songwriter
			}
		}
	}

	if ripdata.Composer != "" && newtags.Custom["Composer"] == "" {
		newtags.Custom["Composer"] = ripdata.Composer
	}
	if ripdata.Songwriter != "" && newtags.Custom["Songwriter"] == "" {
		newtags.Custom["Songwriter"] = ripdata.Songwriter
	}

	fullpath := filepath.Join(d, filename)
	mp4, err := mp4tag.Open(fullpath)
	if err != nil {
		return fmt.Errorf("unable to open mp4 file %s: %w", fullpath, err)
	}
	defer mp4.Close()

	mp4.UpperCustom(false)

	_, err = mp4.Read()
	if err != nil {
		return fmt.Errorf("unable to read mp4 metadata from %s: %w", fullpath, err)
	}

	if err := mp4.Write(&newtags, []string{}); err != nil {
		return fmt.Errorf("failed writing tags to %s: %w", fullpath, err)
	}

	return nil
}

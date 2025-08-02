package bme

import (
	"context"
	// "fmt"
	"github.com/Sorrow446/go-mp4tag"
	"log/slog"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

func tagger(ctx context.Context) {
	slog.Info("starting batch tagger")

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			tag_process_directories()
		case <-ctx.Done():
			slog.Info("shutdown: stopping batch tagger")
		}
	}

	slog.Info("batch tagger done")
}

func tag_process_directories() {
	albums, err := os.ReadDir(tagdir)
	if err != nil {
		slog.Error("unable to read tag directory", "err", err.Error())
		panic(err.Error())
	}
	if len(albums) == 0 {
		slog.Debug("no directories to tag, sleeping")
		time.Sleep(60 * time.Second)
		return
	}

	for i := range albums {
		mbid := albums[i].Name()
		tag_process_directory(mbid)
	}
}

func tag_process_directory(mbid string) {
	d := filepath.Join(tagdir, mbid)
	files, err := os.ReadDir(d)
	if err != nil {
		slog.Error("unable to read directory", "err", err.Error(), "dir", d)
		panic(err.Error())
	}

	ripdata := load_ripdata(tagdir, string(mbid))
	mbdata := mb_lookup_discid(mbid)
	slog.Info("mb_data", "data", mbdata)

	// do work
	for _, f := range files {
		if !strings.HasSuffix(f.Name(), ".m4a") {
			continue
		}

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

		newtags.Custom["MusicBrainz Disc Id"] = mbid

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

		pos, err := strconv.Atoi(string(f.Name())[0:2]) // convert []bytes to string just to take 2 bytes?
		if err != nil {
			slog.Error(err.Error(), "file", string(f.Name()))
			continue
		}
		for _, t := range mbdata.Tracks {
			if t.Position == pos {
				if t.Title != "" {
					newtags.Title = t.Title
				}
				if t.TrackID != "" {
					newtags.Custom["MusicBrainz Release Track Id"] = t.TrackID // deprecated?
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
			}
		}

		fullpath := filepath.Join(d, string(f.Name()))
		mp4, err := mp4tag.Open(fullpath)
		if err != nil {
			slog.Error("unable to open mp4 file", "error", err.Error(), "file", fullpath)
			continue
		}
		defer mp4.Close()
		mp4.UpperCustom(false)

		_, err = mp4.Read()
		if err != nil {
			slog.Error("unable to read mp4 metadata", "err", err.Error(), "file", fullpath)
			continue
		}

		if err := mp4.Write(&newtags, []string{}); err != nil {
			slog.Error("saving", "error", err.Error())
			panic(err.Error())
		}
	}

	// move to tag directory
	t := filepath.Join(finaldir, mbid)
	if err != os.Rename(d, t) {
		panic(err.Error())
	}
}

package bme

import (
	"bufio"
	"context"
	"crypto/sha1"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unsafe"
	// github.com/michiwend/gomusicbrainz
)

type BufWriter interface {
	Write([]byte) (int, error)
	WriteString(string) (int, error)
}

type ripdisc_t struct {
	Firsttrack track_t
	Trackcount track_t
	MBdiscid   string
	MCN        string
	TOC        string

	// from cdtext
	Title      string
	Performer  string
	Songwriter string
	Composser  string
	Message    string
	Arranger   string
	Text_ISRC  string
	UPC_EAN    string
	Genre      string
	Discid     string

	Tracks []riptrack_t
}

type riptrack_t struct {
	ID track_t

	// from cdtext
	Title      string
	Performer  string
	Songwriter string
	Composser  string
	Message    string
	Arranger   string
	Text_ISRC  string
	UPC_EAN    string
	Genre      string
	Discid     string

	// from subchannel
	ISRC string
}

func cdio(ctx context.Context) {
	slog.Info("starting CD ripping")

	devicename := cdio_get_default_device(nil)

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	// _ = cdio_get_media_changed(cddevice)
	for {
		select {
		case <-ticker.C:
			cddevice := cdio_open(devicename, unsafe.Pointer(uintptr(0)))

			if opened := mmc_get_tray_status(cddevice); opened {
				// slog.Info("tray open")
				continue
			}

			state := mmc_test_unit_ready(cddevice, 3600)
			slog.Debug("mmc_test_unit_ready", "state", state)
			if state == 0 {
				ripdisc(cddevice)
				<-ticker.C // drain any pending ticks
			}

			cdio_destroy(cddevice)
		case <-ctx.Done():
			slog.Info("shutdown: stopping CD ripping")
			return
		}
	}
}

func ripdisc(cddevice cddevice_t) {
	d := ripdisc_t{}

	d.MBdiscid = get_mbdiscid(cddevice)
	fullpath := filepath.Join(ripdir, strings.ReplaceAll(d.MBdiscid, "/", "_"))
	_, err := os.Stat(fullpath)
	if err == nil {
		slog.Info("work directory already exists, skipping this CD", "path", fullpath)
		mmc_eject_media(cddevice)
		return
	}
	if err != nil && !strings.Contains(err.Error(), "no such file or directory") {
		panic(err.Error())
	}

	if err := os.MkdirAll(fullpath, 0755); err != nil {
		panic(err.Error())
	}

	// get whatever data we can from the disc
	get_cdtext(&d, cddevice)
	slog.Info("disc", "d", d)

	// save to ripdata.json
	ripdatapath := filepath.Join(fullpath, "ripdata.json")
	ripdata, err := os.OpenFile(ripdatapath, os.O_RDWR|os.O_CREATE, 0644)
	if err != nil {
		panic(err.Error())
	}
	defer ripdata.Close()
	enc := json.NewEncoder(ripdata)
	enc.Encode(d)

	// how to do paranoia_init when we've already opened the libcdio device
	cdda := cdio_cddap_identify_cdio(cddevice, CDDA_MESSAGE_FORGETIT, unsafe.Pointer(uintptr(0)))
	if cdda == nil {
		slog.Error("unable to init cdda")
		return
	}

	cdio_cddap_verbose_set(cdda, CDDA_MESSAGE_FORGETIT, CDDA_MESSAGE_FORGETIT)
	cddap := cdio_cddap_open(cdda)
	if cddap != 0 {
		slog.Error("unable to open audio cd")
		return
	}

	// just a sanity check to make sure the disc is valid
	firstsector := cdio_cddap_disc_firstsector(cdda)
	if firstsector < 0 {
		slog.Error("cdio_cddap_disc_firstsector returned error")
		return
	}

	para := cdio_paranoia_init(cdda)
	if para == nil {
		slog.Error("unable to init paranoia")
		return
	}

	cdio_paranoia_modeset(para, PARANOIA_MODE_FULL^PARANOIA_MODE_NEVERSKIP)

	for _, t := range d.Tracks {
		fs := cdio_cddap_track_firstsector(cdda, t.ID)
		ls := cdio_cddap_track_lastsector(cdda, t.ID)

		cleantitle := strings.ReplaceAll(t.Title, "/", "_")
		cleantitle = strings.ReplaceAll(cleantitle, "?", "_")
		cleantitle = strings.ReplaceAll(cleantitle, ":", "_")
		cleantitle = strings.ReplaceAll(cleantitle, ">", "_")
		cleantitle = strings.ReplaceAll(cleantitle, "\"", "_")

		filename := fmt.Sprintf("%02d %s.wav", t.ID, cleantitle)
		rippath := filepath.Join(fullpath, filename)
		rip, err := os.OpenFile(rippath, os.O_RDWR|os.O_CREATE, 0644)
		if err != nil {
			slog.Error("unable to open file", "error", err.Error())
			continue
		}

		// modest gains if track 1 starts at sector 0, otherwise useless
		buffer := bufio.NewWriterSize(rip, 1000*CDIO_CD_FRAMESIZE_RAW)
		slog.Info("paranoia", "first sector", fs, "last sector", ls, "file", rippath)

		write_wav_header(buffer, uint32(ls-fs)*uint32(CDIO_CD_FRAMESIZE_RAW))

		cdio_paranoia_seek(para, fs, SEEK_SET)
		msg := cdio_cddap_messages(cdda)
		merr := cdio_cddap_errors(cdda)
		if msg != "" || merr != "" {
			slog.Info("paranoia", "message", msg, "error", merr)
		}

		for i := fs; i <= ls; i++ {
			if debug && i%1000 == 0 {
				slog.Debug("paranoia", "sector", i)
			}
			bufptr := cdio_paranoia_read_limited(para, unsafe.Pointer(uintptr(0)), 20)
			buffer.Write(bufptr[:])
			msg := cdio_cddap_messages(cdda)
			merr := cdio_cddap_errors(cdda)
			if msg != "" || merr != "" {
				slog.Info("paranoia", "message", msg, "error", merr)
			}
		}
		buffer.Flush()
		rip.Close()
	}

	// cleanup paranoia
	cdio_paranoia_free(para)
	cdio_cddap_close_no_free_cdio(cdda)

	// move files from rip to encode dir
	move_ripdir(&d, fullpath)

	mmc_eject_media(cddevice)
}

// https://musicbrainz.org/doc/Disc_ID_Calculation
func get_mbdiscid(cddevice cddevice_t) string {
	h := sha1.New()

	first_track := cdio_get_first_track_num(cddevice)
	totaltracks := cdio_get_num_tracks(cddevice)
	leadout := cdio_get_track_lba(cddevice, CDIO_CDROM_LEADOUT_TRACK)

	fmt.Fprintf(h, "%02X%02X%08X", first_track, totaltracks, leadout)

	for i := first_track; i < 100; i++ {
		lba := 0
		if i <= totaltracks {
			lba = cdio_get_track_lba(cddevice, i)
		}
		fmt.Fprintf(h, "%08X", lba)
	}

	sum := h.Sum(nil)
	b := base64.StdEncoding.EncodeToString(sum)

	b = strings.ReplaceAll(b, "+", ".")
	b = strings.ReplaceAll(b, "/", "_")
	b = strings.ReplaceAll(b, "=", "-")

	slog.Info("mb-discid", "b", b)
	return b
}

func write_wav_header(out BufWriter, size uint32) {
	i := make([]byte, 4) // scratch for for int32
	s := make([]byte, 2) // scratch for for int16

	out.WriteString("RIFF")
	binary.LittleEndian.PutUint32(i, uint32(size+44-8))
	out.Write(i)
	out.WriteString("WAVEfmt ")
	binary.LittleEndian.PutUint32(i, uint32(16)) // size of proceeding
	out.Write(i)
	binary.LittleEndian.PutUint16(s, uint16(1)) // 1 is PCM
	out.Write(s)
	binary.LittleEndian.PutUint16(s, uint16(2)) // 2 channels
	out.Write(s)
	binary.LittleEndian.PutUint32(i, uint32(44100)) // sample rate
	out.Write(i)
	binary.LittleEndian.PutUint32(i, uint32(44100*2*2)) // (Sample Rate * BitsPerSample * Channels) / 8
	out.Write(i)
	binary.LittleEndian.PutUint16(s, uint16(4)) // (BitsPerSample * Channels) / 8
	out.Write(s)
	binary.LittleEndian.PutUint16(s, uint16(16)) // BitsPerSample
	out.Write(s)
	out.WriteString("data")
	binary.LittleEndian.PutUint32(i, uint32(size)) // data size
	out.Write(i)
}

func get_cdtext(d *ripdisc_t, cddevice cddevice_t) {
	d.Firsttrack = cdio_get_first_track_num(cddevice)
	d.Trackcount = cdio_get_num_tracks(cddevice)

	cdtext := cdio_get_cdtext(cddevice)
	d.Title = cdtext_get(cdtext, 0, 0)
	d.Performer = cdtext_get(cdtext, 1, 0)
	d.Songwriter = cdtext_get(cdtext, 2, 0)
	d.Composser = cdtext_get(cdtext, 3, 0)
	d.Message = cdtext_get(cdtext, 4, 0)
	d.Arranger = cdtext_get(cdtext, 5, 0)
	d.Text_ISRC = cdtext_get(cdtext, 6, 0)
	d.UPC_EAN = cdtext_get(cdtext, 7, 0)
	d.Genre = cdtext_get(cdtext, 8, 0)
	d.Discid = cdtext_get(cdtext, 9, 0)

	for i := d.Firsttrack; i <= d.Trackcount; i++ {
		a := riptrack_t{}
		a.ID = i
		a.Title = cdtext_get(cdtext, 0, i)
		a.Performer = cdtext_get(cdtext, 1, i)
		a.Songwriter = cdtext_get(cdtext, 2, i)
		a.Composser = cdtext_get(cdtext, 3, i)
		a.Message = cdtext_get(cdtext, 4, i)
		a.Arranger = cdtext_get(cdtext, 5, i)
		a.Text_ISRC = cdtext_get(cdtext, 6, i)
		a.UPC_EAN = cdtext_get(cdtext, 7, i)
		a.Genre = cdtext_get(cdtext, 8, i)
		a.Discid = cdtext_get(cdtext, 9, i)

		a.ISRC = mmc_get_track_isrc(cddevice, i)

		d.Tracks = append(d.Tracks, a)
	}

	d.MCN = mmc_get_mcn(cddevice)
	get_toc(d, cddevice)
}

func get_toc(d *ripdisc_t, cddevice cddevice_t) {
	var toc strings.Builder

	leadout := cdio_get_track_lba(cddevice, CDIO_CDROM_LEADOUT_TRACK)

	fmt.Fprintf(&toc, "%d %d %d", d.Firsttrack, d.Trackcount, leadout)

	for i := d.Firsttrack; i <= d.Trackcount; i++ {
		lba := cdio_get_track_lba(cddevice, i)
		fmt.Fprintf(&toc, " %d", lba)
	}
	d.TOC = toc.String()
}

func move_ripdir(d *ripdisc_t, rippath string) {
	encodepath := filepath.Join(encodedir, strings.ReplaceAll(d.MBdiscid, "/", "_"))
	if _, err := os.Stat(encodepath); err == nil { // no err means file exists
		slog.Info("encode directory already exists, skipping move", "path", encodepath)
		return
	}

	if err := os.Rename(rippath, encodepath); err != nil {
		panic(err.Error())
	}
}

func load_ripdata(workdir string, mbid string) ripdisc_t {
	var o ripdisc_t

	ripdatapath := filepath.Join(workdir, mbid, "ripdata.json")
	ripdata, err := os.ReadFile(ripdatapath)
	if err != nil {
		panic(err.Error())
	}
	if err := json.Unmarshal(ripdata, &o); err != nil {
		panic(err.Error())
	}
	return o
}

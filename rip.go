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

	tea "github.com/charmbracelet/bubbletea"
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
	Composer   string
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
	Composer   string
	Message    string
	Arranger   string
	Text_ISRC  string
	UPC_EAN    string
	Genre      string
	Discid     string

	// from subchannel
	ISRC string
}

func cdio(ctx context.Context, p *tea.Program) {
	if p != nil {
		p.Send(StatusMsg{"ripper", "Starting"})
	}

	devicename := cdio_get_default_device(nil)

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			cddevice := cdio_open(devicename, unsafe.Pointer(uintptr(0)))
			if cddevice == nil {
				continue
			}

			if opened := mmc_get_tray_status(cddevice); opened {
				if p != nil {
					p.Send(StatusMsg{"ripper", "Tray open"})
				}
				cdio_destroy(cddevice)
				continue
			}

			state := mmc_test_unit_ready(cddevice, 3600)
			if state == 0 {
				if p != nil {
					p.Send(StatusMsg{"ripper", "Disc detected"})
				}
				if err := ripdisc(ctx, cddevice, p); err != nil {
					slog.Error("ripping failed", "error", err)
					if p != nil {
						p.Send(StatusMsg{"ripper", fmt.Sprintf("Error: %v", err)})
					}
				}
				// Drain any pending ticks
				select {
				case <-ticker.C:
				default:
				}
				mmc_eject_media(cddevice)
			} else {
				if p != nil {
					p.Send(StatusMsg{"ripper", "Checking tray..."})
				}
			}

			cdio_destroy(cddevice)
		case <-ctx.Done():
			if p != nil {
				p.Send(StatusMsg{"ripper", "Stopped"})
			}
			return
		}
	}
}

func ripdisc(ctx context.Context, cddevice cddevice_t, p *tea.Program) error {
	d := ripdisc_t{}

	if p != nil {
		p.Send(ProgressMsg{"ripper", 0.0})
		p.Send(StatusMsg{"ripper", "Calculating DiscID..."})
	}
	d.MBdiscid = get_mbdiscid(cddevice)
	if p != nil {
		p.Send(StatusMsg{"ripper", fmt.Sprintf("ID: %s", d.MBdiscid)})
	}

	mbid_safe := strings.ReplaceAll(d.MBdiscid, "/", "_")
	fullpath := filepath.Join(ripdir, mbid_safe)
	_, err := os.Stat(fullpath)
	if err == nil {
		if p != nil {
			p.Send(StatusMsg{"ripper", "Already ripped, skipping"})
		}
		mmc_eject_media(cddevice)
		return nil
	}
	if err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("stat failed for %s: %w", fullpath, err)
	}

	if err := os.MkdirAll(fullpath, 0755); err != nil {
		return fmt.Errorf("failed to create directory %s: %w", fullpath, err)
	}

	// get whatever data we can from the disc
	if p != nil {
		p.Send(StatusMsg{"ripper", "Reading CD-Text..."})
	}
	get_cdtext(&d, cddevice)

	// save to ripdata.json
	ripdatapath := filepath.Join(fullpath, "ripdata.json")
	ripdata, err := os.OpenFile(ripdatapath, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0644)
	if err != nil {
		return fmt.Errorf("unable to open %s: %w", ripdatapath, err)
	}
	defer ripdata.Close()
	enc := json.NewEncoder(ripdata)
	if err := enc.Encode(d); err != nil {
		return fmt.Errorf("failed to encode ripdata: %w", err)
	}

	// how to do paranoia_init when we've already opened the libcdio device
	cdda := cdio_cddap_identify_cdio(cddevice, CDDA_MESSAGE_FORGETIT, unsafe.Pointer(uintptr(0)))
	if cdda == nil {
		return fmt.Errorf("unable to init cdda")
	}

	if debug {
		cdio_cddap_verbose_set(cdda, CDDA_MESSAGE_PRINTIT, CDDA_MESSAGE_PRINTIT)
	} else {
		cdio_cddap_verbose_set(cdda, CDDA_MESSAGE_FORGETIT, CDDA_MESSAGE_FORGETIT)
	}
	cddap := cdio_cddap_open(cdda)
	if cddap != 0 {
		return fmt.Errorf("unable to open audio cd (code %d)", cddap)
	}

	// just a sanity check to make sure the disc is valid
	firstsector := cdio_cddap_disc_firstsector(cdda)
	if firstsector < 0 {
		return fmt.Errorf("cdio_cddap_disc_firstsector returned error")
	}

	para := cdio_paranoia_init(cdda)
	if para == nil {
		return fmt.Errorf("unable to init paranoia")
	}
	defer cdio_paranoia_free(para)

	cdio_paranoia_modeset(para, paranoiaLevel)

	for i, t := range d.Tracks {
		select {
		case <-ctx.Done():
			cdio_cddap_close_no_free_cdio(cdda)
			os.RemoveAll(fullpath)
			return ctx.Err()
		default:
		}

		if p != nil {
			if i == 0 {
				p.Send(StatusMsg{"ripper", "Initializing drive (this may take a moment)..."})
			}
			p.Send(StatusMsg{"ripper", fmt.Sprintf("Track %d/%d", t.ID, d.Trackcount)})
		}
		fs := cdio_cddap_track_firstsector(cdda, t.ID)
		ls := cdio_cddap_track_lastsector(cdda, t.ID)

		cleantitle := strings.NewReplacer("/", "_", "?", "_", ":", "_", ">", "_", "\"", "_").Replace(t.Title)

		filename := fmt.Sprintf("%02d %s.wav", t.ID, cleantitle)
		rippath := filepath.Join(fullpath, filename)
		rip, err := os.OpenFile(rippath, os.O_RDWR|os.O_CREATE|os.O_TRUNC, 0644)
		if err != nil {
			slog.Error("unable to open file", "error", err, "path", rippath)
			continue
		}

		// modest gains if track 1 starts at sector 0, otherwise useless
		buffer := bufio.NewWriterSize(rip, 1000*CDIO_CD_FRAMESIZE_RAW)
		write_wav_header(buffer, uint32(ls-fs)*uint32(CDIO_CD_FRAMESIZE_RAW))

		cdio_paranoia_seek(para, fs, SEEK_SET)

		for j := fs; j <= ls; j++ {
			select {
			case <-ctx.Done():
				buffer.Flush()
				rip.Close()
				cdio_cddap_close_no_free_cdio(cdda)
				os.RemoveAll(fullpath)
				return ctx.Err()
			default:
			}

			bufptr := cdio_paranoia_read_limited(para, unsafe.Pointer(uintptr(0)), 20)
			if bufptr != nil {
				buffer.Write(bufptr[:])
			}

			if p != nil && j%50 == 0 {
				p.Send(ProgressMsg{"ripper", float64(j-fs) / float64(ls-fs)})
			}
		}
		if p != nil {
			p.Send(ProgressMsg{"ripper", 1.0})
		}
		buffer.Flush()
		rip.Close()
	}

	cdio_cddap_close_no_free_cdio(cdda)

	// move files from rip to encode dir
	if p != nil {
		p.Send(StatusMsg{"ripper", "Moving to encode queue..."})
	}
	if err := move_ripdir(&d, fullpath); err != nil {
		return err
	}

	mmc_eject_media(cddevice)
	if p != nil {
		p.Send(StatusMsg{"ripper", "Complete. Ejecting."})
	}
	return nil
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

	slog.Debug("mb-discid", "b", b)
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
	d.Composer = cdtext_get(cdtext, 3, 0)
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
		a.Composer = cdtext_get(cdtext, 3, i)
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

func move_ripdir(d *ripdisc_t, rippath string) error {
	mbid_safe := strings.ReplaceAll(d.MBdiscid, "/", "_")
	encodepath := filepath.Join(encodedir, mbid_safe)
	if _, err := os.Stat(encodepath); err == nil {
		slog.Debug("encode directory already exists, skipping move", "path", encodepath)
		return nil
	}

	if err := os.Rename(rippath, encodepath); err != nil {
		return fmt.Errorf("failed to move %s to %s: %w", rippath, encodepath, err)
	}
	return nil
}

func load_ripdata(workdir string, mbid string) ripdisc_t {
	var o ripdisc_t

	ripdatapath := filepath.Join(workdir, mbid, "ripdata.json")
	ripdata, err := os.ReadFile(ripdatapath)
	if err != nil {
		slog.Error("failed to read ripdata", "path", ripdatapath, "error", err)
		return o
	}
	if err := json.Unmarshal(ripdata, &o); err != nil {
		slog.Error("failed to unmarshal ripdata", "error", err)
	}
	return o
}

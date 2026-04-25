package bme

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

type job struct {
	id       int
	filename string
	track    track_t
	tracks   track_t
	ripdata  ripdisc_t
}

type result struct {
	id  int
	err error
}

func encoder(ctx context.Context, p *tea.Program) {
	if p != nil {
		p.Send(StatusMsg{"encoder", "Starting"})
	}

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if err := process_directory(p); err != nil {
				slog.Error("encoder failed", "error", err)
				if p != nil {
					p.Send(StatusMsg{"encoder", fmt.Sprintf("Error: %v", err)})
				}
			}
		case <-ctx.Done():
			if p != nil {
				p.Send(StatusMsg{"encoder", "Stopped"})
			}
			return
		}
	}
}

func process_directory(p *tea.Program) error {
	joblimit := runtime.NumCPU()

	// get all rips waiting to be encoded
	albums, err := os.ReadDir(encodedir)
	if err != nil {
		return fmt.Errorf("unable to read encode directory: %w", err)
	}
	if len(albums) == 0 {
		if p != nil {
			// p.Send(StatusMsg{"encoder", "Idle"})
		}
		return nil
	}

	// uses the first directory alphabetically, by MB_discid
	mbid := albums[0].Name()
	d := filepath.Join(encodedir, mbid)
	if p != nil {
		p.Send(StatusMsg{"encoder", fmt.Sprintf("Encoding %s...", mbid)})
	}

	files, err := os.ReadDir(d)
	if err != nil {
		return fmt.Errorf("unable to read directory %s: %w", d, err)
	}
	rd := load_ripdata(encodedir, mbid)

	tracks := 0
	for _, file := range files {
		if strings.HasSuffix(file.Name(), ".wav") {
			tracks++
		}
	}

	jobs := make(chan job, tracks)
	results := make(chan result, tracks)
	var wg sync.WaitGroup

	// start workers
	for i := 1; i <= joblimit; i++ {
		wg.Add(1)
		go worker(i, jobs, results, &wg, p)
	}

	// pass all the jobs into the queue as quickly as it can
	for i, file := range files {
		if !strings.HasSuffix(file.Name(), ".wav") {
			continue
		}

		tracknum, err := strconv.Atoi(file.Name()[0:2])
		if err != nil {
			slog.Error("invalid track number prefix", "file", file.Name(), "error", err)
			continue
		}

		jobs <- job{id: i, filename: filepath.Join(d, file.Name()), ripdata: rd, track: track_t(tracknum), tracks: track_t(tracks)}
	}
	close(jobs)

	// when the workers are done, close the results channel
	go func() {
		wg.Wait()
		close(results)
	}()

	// read the results as each job finishes
	var encodeError bool
	completed := 0
	for r := range results {
		if r.err != nil {
			slog.Error("job failed", "job id", r.id, "error", r.err)
			encodeError = true
		} else {
			completed++
			if p != nil {
				p.Send(StatusMsg{"encoder", fmt.Sprintf("[%s] %d/%d", mbid, completed, tracks)})
			}
		}
	}

	if encodeError {
		return fmt.Errorf("one or more encoding jobs failed for %s", mbid)
	}

	// move to tag directory
	if p != nil {
		p.Send(StatusMsg{"encoder", "Moving to tagger..."})
	}
	t := filepath.Join(tagdir, mbid)
	if err := os.Rename(d, t); err != nil {
		return fmt.Errorf("failed to move to tag directory: %w", err)
	}
	return nil
}

func worker(id int, jobs <-chan job, results chan<- result, wg *sync.WaitGroup, p *tea.Program) {
	defer wg.Done()

	for job := range jobs {
		alacname := strings.ReplaceAll(job.filename, ".wav", ".m4a")

		trackarg := fmt.Sprintf("--track=%d/%d", job.track, job.tracks)
		args := []string{"-q", trackarg}

		if job.ripdata.Title != "" {
			args = append(args, fmt.Sprintf("--album=%s", job.ripdata.Title))
		}

		if job.ripdata.Performer != "" {
			args = append(args, fmt.Sprintf("--albumArtist=%s", job.ripdata.Performer))
		}

		for _, trackdata := range job.ripdata.Tracks {
			if trackdata.ID == job.track {
				if trackdata.Performer != "" {
					args = append(args, fmt.Sprintf("--artist=%s", trackdata.Performer))
				}
				if trackdata.Title != "" {
					args = append(args, fmt.Sprintf("--title=%s", trackdata.Title))
				}
			}
		}

		args = append(args, job.filename, alacname)
		slog.Debug("alacenc args", "args", args)

		cmd := exec.Command("/usr/local/bin/alacenc", args...)
		if err := cmd.Run(); err != nil {
			slog.Error("alacenc failed", "error", err, "file", job.filename)
			results <- result{id: job.id, err: err}
			continue
		}
		if err := os.Remove(job.filename); err != nil {
			slog.Error("failed to remove wav file", "error", err, "file", job.filename)
		}
		results <- result{id: job.id, err: nil}
	}
}

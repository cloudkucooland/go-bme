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

func encoder(ctx context.Context) {
	slog.Info("starting batch encoder")

	ticker := time.NewTicker(time.Second * 10)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			process_directory()
		case <-ctx.Done():
			slog.Info("shutdown: stopping batch encoder")
		}
	}

	slog.Info("batch encoder done")
}

func process_directory() {
	joblimit := runtime.NumCPU()

	// get all rips waiting to be encoded
	albums, err := os.ReadDir(encodedir)
	if err != nil {
		slog.Error("unable to read encode directory", "err", err.Error())
		panic(err.Error())
	}
	if len(albums) == 0 {
		slog.Debug("no directories to encode, sleeping")
		time.Sleep(60 * time.Second)
		return
	}

	// uses the first directory alphabetically, by MB_discid
	d := filepath.Join(encodedir, string(albums[0].Name()))
	files, err := os.ReadDir(d)
	if err != nil {
		slog.Error("unable to read directory", "err", err.Error(), "dir", d)
		panic(err.Error())
	}
	rd := load_ripdata(encodedir, string(albums[0].Name()))

	//
	tracks := 0
	for _, file := range files {
		if strings.HasSuffix(file.Name(), ".wav") {
			tracks++
		}
	}

	jobs := make(chan job, tracks)
	results := make(chan result, joblimit)
	var wg sync.WaitGroup

	// start workers
	for i := 1; i <= joblimit; i++ {
		wg.Add(1)
		go worker(i, jobs, results, &wg)
	}

	// pass all the jobs into the queue as quickly as it can
	for i, file := range files {
		if !strings.HasSuffix(file.Name(), ".wav") {
			continue
		}

		tracknum, err := strconv.Atoi(file.Name()[0:2])
		if err != nil {
			panic(err)
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
	for r := range results {
		slog.Info("job done", "job id", r.id)
		if err != nil {
			slog.Error("job", "error", r.err.Error())
		}
	}

	// move to tag directory
	t := filepath.Join(tagdir, string(albums[0].Name()))
	if err != os.Rename(d, t) {
		panic(err.Error())
	}
}

func worker(id int, jobs <-chan job, results chan<- result, wg *sync.WaitGroup) {
	defer wg.Done()

	for job := range jobs {
		slog.Info("processing job", "worker", id, "job", job.id, "file", job.filename)
		alacname := strings.ReplaceAll(job.filename, ".wav", ".m4a")

		trackarg := fmt.Sprintf("--track=%d/%d", job.track, job.tracks)
		args := []string{"-q", trackarg}

		if job.ripdata.Title != "" {
			tmp := fmt.Sprintf("--album=%s", job.ripdata.Title)
			args = append(args, tmp)
		}

		if job.ripdata.Performer != "" {
			tmp := fmt.Sprintf("--albumArtist=%s", job.ripdata.Performer)
			args = append(args, tmp)
		}

		for _, trackdata := range job.ripdata.Tracks {
			if trackdata.ID == job.track {
				if trackdata.Performer != "" {
					tmp := fmt.Sprintf("--artist=%s", trackdata.Performer)
					args = append(args, tmp)
				}

				if trackdata.Title != "" {
					tmp := fmt.Sprintf("--title=%s", trackdata.Title)
					args = append(args, tmp)
				}
			}
		}

		args = append(args, job.filename)
		args = append(args, alacname)

		slog.Info("args", "args", args)

		cmd := exec.Command("/usr/local/bin/alacenc", args...)
		if err := cmd.Run(); err != nil {
			slog.Error("alac", "error", err.Error(), "cmd", cmd)
			results <- result{id: job.id, err: err}
			panic(err.Error())
		}
		if err := os.Remove(job.filename); err != nil {
			slog.Error("remove", "error", err.Error())
			results <- result{id: job.id, err: err}
			continue
		}
		results <- result{id: job.id, err: nil}
	}
}

package bme

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"

	tea "github.com/charmbracelet/bubbletea"
)

var debug bool
var ripdir string
var encodedir string
var tagdir string
var finaldir string

func Debug(d bool) {
	if d {
		slog.Info("enabling debug")
		slog.SetLogLoggerLevel(slog.LevelDebug)
	}
	debug = d
}

func Start(wd string, p *tea.Program) error {
	ripdir = filepath.Join(wd, "rip")
	encodedir = filepath.Join(wd, "encode")
	tagdir = filepath.Join(wd, "tag")
	finaldir = filepath.Join(wd, "done")

	if err := os.MkdirAll(ripdir, 0755); err != nil {
		return fmt.Errorf("failed to create rip directory %s: %w", ripdir, err)
	}
	if err := os.MkdirAll(encodedir, 0755); err != nil {
		return fmt.Errorf("failed to create encode directory %s: %w", encodedir, err)
	}
	if err := os.MkdirAll(tagdir, 0755); err != nil {
		return fmt.Errorf("failed to create tag directory %s: %w", tagdir, err)
	}
	if err := os.MkdirAll(finaldir, 0755); err != nil {
		return fmt.Errorf("failed to create final directory %s: %w", finaldir, err)
	}

	loadlibs()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	var wg sync.WaitGroup

	// start batch ripper
	wg.Add(1)
	go func() {
		defer wg.Done()
		cdio(ctx, p)
	}()

	// start batch encoder
	wg.Add(1)
	go func() {
		defer wg.Done()
		encoder(ctx, p)
	}()

	// start batch tagger
	wg.Add(1)
	go func() {
		defer wg.Done()
		tagger(ctx, p)
	}()

	sigch := make(chan os.Signal, 1)
	signal.Notify(sigch, syscall.SIGINT, syscall.SIGQUIT, syscall.SIGTERM, syscall.SIGHUP, os.Interrupt)

	select {
	case sig := <-sigch:
		slog.Info("shutdown requested by signal", "signal", sig)
		if p != nil {
			p.Send(StatusMsg{"system", "Shutdown requested"})
		}
	case <-ctx.Done():
	}

	cancel()
	slog.Info("waiting for background processes to finish")
	wg.Wait()
	slog.Info("shutdown complete")
	return nil
}

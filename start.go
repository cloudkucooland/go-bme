package bme

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"
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

func Start(wd string) error {
	ripdir = filepath.Join(wd, "rip")
	encodedir = filepath.Join(wd, "encode")
	tagdir = filepath.Join(wd, "tag")
	finaldir = filepath.Join(wd, "done")

	if err := os.MkdirAll(ripdir, 0755); err != nil {
		slog.Error("rip directory does not exist, cannot create", "dir", ripdir)
		panic(err.Error())
	}
	if err := os.MkdirAll(encodedir, 0755); err != nil {
		slog.Error("encode directory does not exist, cannot create", "dir", encodedir)
		panic(err.Error())
	}
	if err := os.MkdirAll(tagdir, 0755); err != nil {
		slog.Error("tag directory does not exist, cannot create", "dir", tagdir)
		panic(err.Error())
	}
	if err := os.MkdirAll(finaldir, 0755); err != nil {
		slog.Error("final directory does not exist, cannot create", "dir", tagdir)
		panic(err.Error())
	}

	loadlibs()
	ctx, cancel := context.WithCancel(context.Background())
	var wg sync.WaitGroup

	// start batch ripper
	wg.Add(1)
	go func() {
		defer wg.Done()
		go cdio(ctx)
	}()

	// start batch encoder
	wg.Add(1)
	go func() {
		defer wg.Done()
		go encoder(ctx)
	}()

	// start batch tagger
	wg.Add(1)
	go func() {
		defer wg.Done()
		go tagger(ctx)
	}()

	sigch := make(chan os.Signal, 3)
	signal.Notify(sigch, syscall.SIGINT, syscall.SIGQUIT, syscall.SIGTERM, syscall.SIGHUP, os.Interrupt)
	sig := <-sigch
	slog.Info("shutdown requested by signal", "signal", sig)
	cancel()

	slog.Info("waiting for shutdown")
	wg.Wait()
	return nil
}

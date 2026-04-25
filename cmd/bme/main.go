package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/cloudkucooland/go-bme"
	"github.com/urfave/cli/v3"
)

func main() {
	app := &cli.Command{
		Name:    "bme",
		Version: "v0.0.0",
		Authors: []any{
			"Scot C. Bontrager <cloudkucooland@gmail.com>",
		},
		Copyright: "© 2022 Scot C. Bontrager",

		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:    "dir",
				Aliases: []string{"d"},
				Value:   "/home/data/bme",
				Usage:   "directory for work files",
			},
			&cli.BoolFlag{
				Name:    "debug",
				Aliases: []string{"V"},
				Usage:   "verbose info dumps",
			},
		},
		Action: func(ctx context.Context, cmd *cli.Command) error {
			bme.Debug(cmd.Bool("debug"))
			dir := cmd.String("dir")

			// Catch OS signals for graceful shutdown
			ctx, cancel := signal.NotifyContext(ctx, os.Interrupt, syscall.SIGTERM, syscall.SIGQUIT)
			defer cancel()

			p := tea.NewProgram(bme.NewModel(), tea.WithAltScreen())

			// Start logic in a goroutine
			go func() {
				if err := bme.Start(ctx, dir, p); err != nil {
					p.Send(bme.StatusMsg{Component: "system", Status: err.Error()})
				}
				p.Quit()
			}()

			if _, err := p.Run(); err != nil {
				return err
			}

			return nil
		},
	}

	if err := app.Run(context.Background(), os.Args); err != nil {
		log.Fatal(err)
	}
}

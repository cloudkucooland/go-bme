package main

import (
	"log"
	"os"

	"github.com/cloudkucooland/go-bme"
	"github.com/urfave/cli/v2"
)

func main() {
	app := &cli.App{
		Name:    "bme",
		Version: "v0.0.0",
		Authors: []*cli.Author{
			{
				Name:  "Scot C. Bontrager",
				Email: "cloudkucooland@gmail.com",
			},
		},
		Copyright: "© 2022 Scot C. Bontrager",
		HelpName:  "bme",

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
		Action: func(cCtx *cli.Context) error {
			bme.Debug(cCtx.Bool("debug"))

			dir := cCtx.String("dir")
			if err := bme.Start(dir); err != nil {
				log.Panic(err)
			}

			return nil
		},
	}

	if err := app.Run(os.Args); err != nil {
		log.Fatal(err)
	}
}

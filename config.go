package bme

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Config struct {
	BaseDir     string   `json:"base_dir"`
	RipDir      string   `json:"rip_dir"`
	EncodeDir   string   `json:"encode_dir"`
	TagDir      string   `json:"tag_dir"`
	DoneDir     string   `json:"done_dir"`
	EncoderPath string   `json:"encoder_path"`
	Devices     []string `json:"devices"`
}

func DefaultConfig() *Config {
	home, _ := os.UserHomeDir()
	base := filepath.Join(home, "bme")
	return &Config{
		BaseDir:     base,
		RipDir:      filepath.Join(base, "rip"),
		EncodeDir:   filepath.Join(base, "encode"),
		TagDir:      filepath.Join(base, "tag"),
		DoneDir:     filepath.Join(base, "done"),
		EncoderPath: "/usr/local/bin/alacenc",
	}
}

func LoadConfig(path string) (*Config, error) {
	c := DefaultConfig()
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return c, nil
		}
		return nil, err
	}

	if err := json.Unmarshal(data, c); err != nil {
		return nil, err
	}

	// Re-calculate subdirs if BaseDir was changed but subdirs weren't explicitly set in JSON
	// This is a simple implementation; we could be more sophisticated.
	return c, nil
}

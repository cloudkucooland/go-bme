package bme

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Messages
type StatusMsg struct {
	Component string
	Status    string
}

type MBMatchesMsg struct {
	MBID     string
	Releases []mb_release
}

type MBSelectedMsg struct {
	Release mb_release
}

// Styles
var (
	headerStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#FAFAFA")).
			Background(lipgloss.Color("#7D56F4")).
			Padding(0, 1).
			Bold(true)

	statusStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			Padding(0, 1).
			MarginRight(1)

	selectedStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#EE6FF8")).
			Bold(true)
)

type model struct {
	ripperStatus  string
	encoderStatus string
	taggerStatus  string

	mbMatches []mb_release
	mbList    list.Model
	selecting bool

	logs   []string
	width  int
	height int
}

func NewModel() model {
	return model{
		ripperStatus:  "Idle",
		encoderStatus: "Idle",
		taggerStatus:  "Idle",
		logs:          make([]string, 0),
	}
}

func (m model) Init() tea.Cmd {
	return nil
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case StatusMsg:
		switch msg.Component {
		case "ripper":
			m.ripperStatus = msg.Status
		case "encoder":
			m.encoderStatus = msg.Status
		case "tagger":
			m.taggerStatus = msg.Status
		}
		m.logs = append(m.logs, fmt.Sprintf("[%s] %s", msg.Component, msg.Status))
		if len(m.logs) > 10 {
			m.logs = m.logs[1:]
		}

	case MBMatchesMsg:
		m.mbMatches = msg.Releases
		m.selecting = true
		items := make([]list.Item, len(msg.Releases))
		for i, r := range msg.Releases {
			items[i] = mbItem{r}
		}
		m.mbList = list.New(items, list.NewDefaultDelegate(), 0, 0)
		m.mbList.Title = "Select MusicBrainz Release"

	case tea.KeyMsg:
		if m.selecting {
			switch msg.String() {
			case "enter":
				selected := m.mbList.SelectedItem().(mbItem).release
				m.selecting = false
				// Send back to tagger
				go func() {
					selectionChan <- selected
				}()
				return m, nil
			}
			m.mbList, cmd = m.mbList.Update(msg)
			return m, cmd
		}

		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit
		}
	}

	return m, nil
}

func (m model) View() string {
	header := headerStyle.Render("BME: Batch Music Encoder")

	statusCol := lipgloss.JoinVertical(lipgloss.Left,
		statusStyle.Render(fmt.Sprintf("Ripper: %s", m.ripperStatus)),
		statusStyle.Render(fmt.Sprintf("Encoder: %s", m.encoderStatus)),
		statusStyle.Render(fmt.Sprintf("Tagger: %s", m.taggerStatus)),
	)

	logView := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		Width(40).
		Height(10).
		Render(strings.Join(m.logs, "\n"))

	mainView := lipgloss.JoinHorizontal(lipgloss.Top, statusCol, logView)

	if m.selecting {
		m.mbList.SetSize(m.width-10, m.height-15)
		return lipgloss.JoinVertical(lipgloss.Left,
			header,
			mainView,
			"\n",
			m.mbList.View(),
		)
	}

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		mainView,
		"\nPress 'q' to quit",
	)
}

type mbItem struct {
	release mb_release
}

func (i mbItem) Title() string { return i.release.Title }
func (i mbItem) Description() string {
	return fmt.Sprintf("ID: %s | Artist: %s", i.release.ReleaseID, i.release.AlbumArtist)
}
func (i mbItem) FilterValue() string { return i.release.Title }

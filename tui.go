package bme

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/progress"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Messages
type StatusMsg struct {
	Component string
	Status    string
}

type ProgressMsg struct {
	Component string
	Percent   float64
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
			Width(44)

	ripperStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#00FF00"))
	encoderStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#00FFFF"))
	taggerStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFFF00"))
	systemStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#FF00FF"))

	logStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder()).
			Padding(0, 1)
)

type model struct {
	ripperStatus  string
	encoderStatus string
	taggerStatus  string
	paranoiaMode  string

	ripperProgress  progress.Model
	encoderProgress progress.Model
	taggerProgress  progress.Model

	mbMatches []mb_release
	mbList    list.Model
	selecting bool

	logs   []string
	width  int
	height int
}

func NewModel() model {
	return model{
		ripperStatus:    "Idle",
		encoderStatus:   "Idle",
		taggerStatus:    "Idle",
		paranoiaMode:    GetParanoiaName(),
		ripperProgress:  progress.New(progress.WithDefaultGradient()),
		encoderProgress: progress.New(progress.WithDefaultGradient()),
		taggerProgress:  progress.New(progress.WithDefaultGradient()),
		logs:            make([]string, 0),
	}
}

func (m model) Init() tea.Cmd {
	return nil
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	var cmd tea.Cmd
	var cmds []tea.Cmd

	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.ripperProgress.Width = 40
		m.encoderProgress.Width = 40
		m.taggerProgress.Width = 40

	case StatusMsg:
		var styledStatus string
		switch msg.Component {
		case "ripper":
			m.ripperStatus = msg.Status
			styledStatus = ripperStyle.Render(fmt.Sprintf("[%s] %s", msg.Component, msg.Status))
		case "encoder":
			m.encoderStatus = msg.Status
			styledStatus = encoderStyle.Render(fmt.Sprintf("[%s] %s", msg.Component, msg.Status))
		case "tagger":
			m.taggerStatus = msg.Status
			styledStatus = taggerStyle.Render(fmt.Sprintf("[%s] %s", msg.Component, msg.Status))
		default:
			styledStatus = systemStyle.Render(fmt.Sprintf("[%s] %s", msg.Component, msg.Status))
		}

		m.logs = append(m.logs, styledStatus)
		if len(m.logs) > 50 {
			m.logs = m.logs[1:]
		}

	case ProgressMsg:
		switch msg.Component {
		case "ripper":
			cmds = append(cmds, m.ripperProgress.SetPercent(msg.Percent))
		case "encoder":
			cmds = append(cmds, m.encoderProgress.SetPercent(msg.Percent))
		case "tagger":
			cmds = append(cmds, m.taggerProgress.SetPercent(msg.Percent))
		}

	case progress.FrameMsg:
		newRipper, ripperCmd := m.ripperProgress.Update(msg)
		m.ripperProgress = newRipper.(progress.Model)
		cmds = append(cmds, ripperCmd)

		newEncoder, encoderCmd := m.encoderProgress.Update(msg)
		m.encoderProgress = newEncoder.(progress.Model)
		cmds = append(cmds, encoderCmd)

		newTagger, taggerCmd := m.taggerProgress.Update(msg)
		m.taggerProgress = newTagger.(progress.Model)
		cmds = append(cmds, taggerCmd)

	case MBMatchesMsg:
		m.mbMatches = msg.Releases
		m.selecting = true
		items := make([]list.Item, len(msg.Releases))
		for i, r := range msg.Releases {
			items[i] = mbItem{r}
		}
		m.mbList = list.New(items, list.NewDefaultDelegate(), m.width-10, m.height-15)
		m.mbList.Title = fmt.Sprintf("Select Release for DiscID: %s", msg.MBID)

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
		case "p":
			mode := ToggleParanoia()
			m.paranoiaMode = GetParanoiaName()
			m.logs = append(m.logs, systemStyle.Render(fmt.Sprintf("[system] Paranoia set to: %s", mode)))
		case "ctrl+l":
			return m, tea.ClearScreen
		case "X":
			PurgeDirectories()
			m.logs = append(m.logs, systemStyle.Render("[system] Working directories purged"))
		case "q", "ctrl+c":
			return m, tea.Quit
		}
	}

	return m, tea.Batch(cmds...)
}

func (m model) View() string {
	header := headerStyle.Render("BME: Batch Music Encoder Dashboard")

	ripperView := ripperStyle.Render("Ripper:   ") + m.ripperStatus
	encoderView := encoderStyle.Render("Encoder:  ") + m.encoderStatus
	taggerView := taggerStyle.Render("Tagger:   ") + m.taggerStatus
	paranoiaView := systemStyle.Render("Paranoia: ") + m.paranoiaMode

	// Calculate heights
	mainHeight := m.height - 6
	if mainHeight < 10 {
		mainHeight = 10
	}
	if mainHeight > 20 {
		mainHeight = 20
	}

	statusCol := statusStyle.
		Height(mainHeight).
		Render(lipgloss.JoinVertical(lipgloss.Left,
			ripperView,
			m.ripperProgress.View(),
			encoderView,
			m.encoderProgress.View(),
			taggerView,
			m.taggerProgress.View(),
			"\n"+paranoiaView,
		))

	// Take last N lines of logs that fit in height
	availableLogLines := mainHeight - 2
	if availableLogLines < 1 {
		availableLogLines = 1
	}

	displayLogs := m.logs
	if len(displayLogs) > availableLogLines {
		displayLogs = displayLogs[len(displayLogs)-availableLogLines:]
	}
	logContent := strings.Join(displayLogs, "\n")

	logView := logStyle.
		Width(m.width - 49).
		Height(mainHeight).
		Render(logContent)

	mainView := lipgloss.JoinHorizontal(lipgloss.Top, statusCol, logView)

	if m.selecting {
		return lipgloss.JoinVertical(lipgloss.Left,
			header,
			"\n",
			m.mbList.View(),
		)
	}

	help := "\n[q] quit | [p] toggle paranoia | [ctrl+l] redraw | [X] purge work dirs"

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		"\n",
		mainView,
		help,
	)
}

type mbItem struct {
	release mb_release
}

func (i mbItem) Title() string { return i.release.Title }
func (i mbItem) Description() string {
	return fmt.Sprintf("Tracks: %d | Artist: %s | Title: %s | Country: %s | Barcode: %s | Disambig: %s", len(i.release.Tracks), i.release.AlbumArtist, i.release.Title, i.release.Country, i.release.Barcode, i.release.Disambiguation)
}
func (i mbItem) FilterValue() string { return i.release.Title }

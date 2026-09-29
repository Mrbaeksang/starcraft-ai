//go:build windows

package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"math"
	"os"
	"syscall"
	"unsafe"
)

const (
	processVMRead                  = 0x0010
	processQueryLimitedInformation = 0x1000
)

var (
	user32                     = syscall.NewLazyDLL("user32.dll")
	kernel32                   = syscall.NewLazyDLL("kernel32.dll")
	findWindowW                = user32.NewProc("FindWindowW")
	getWindowThreadProcessID   = user32.NewProc("GetWindowThreadProcessId")
	openProcess                = kernel32.NewProc("OpenProcess")
	closeHandle                = kernel32.NewProc("CloseHandle")
	queryFullProcessImageNameW = kernel32.NewProc("QueryFullProcessImageNameW")
)

type attachResult struct {
	Schema                string  `json:"schema"`
	ManifestVersion       string  `json:"manifest_version"`
	ClientSHA256          string  `json:"client_sha256"`
	PID                   uint32  `json:"pid"`
	WindowHandle          uintptr `json:"window_handle"`
	ProcessImage          string  `json:"process_image"`
	VersionLockedAttach   bool    `json:"version_locked_attach"`
	ReadGameStateProven   bool    `json:"read_game_state_proven"`
	IssueCommandsProven   bool    `json:"issue_commands_proven"`
	MultiplayerSyncProven bool    `json:"multiplayer_sync_proven"`
}

func attach(pid uint32, manifest ClientManifest) (attachResult, error) {
	windowTitle, err := syscall.UTF16PtrFromString("Brood War")
	if err != nil {
		return attachResult{}, err
	}
	window, _, _ := findWindowW.Call(0, uintptr(unsafe.Pointer(windowTitle)))
	if window == 0 {
		return attachResult{}, errors.New("Brood War window not found")
	}
	var windowPID uint32
	getWindowThreadProcessID.Call(window, uintptr(unsafe.Pointer(&windowPID)))
	if windowPID != pid {
		return attachResult{}, fmt.Errorf("window PID %d does not match requested PID %d", windowPID, pid)
	}
	handle, _, openErr := openProcess.Call(processVMRead|processQueryLimitedInformation, 0, uintptr(pid))
	if handle == 0 {
		return attachResult{}, fmt.Errorf("OpenProcess: %w", openErr)
	}
	defer closeHandle.Call(handle)
	imageBuffer := make([]uint16, 32768)
	imageLength := uint32(len(imageBuffer))
	ret, _, queryErr := queryFullProcessImageNameW.Call(
		handle,
		0,
		uintptr(unsafe.Pointer(&imageBuffer[0])),
		uintptr(unsafe.Pointer(&imageLength)),
	)
	if ret == 0 {
		return attachResult{}, fmt.Errorf("QueryFullProcessImageNameW: %w", queryErr)
	}
	imagePath := syscall.UTF16ToString(imageBuffer[:imageLength])
	hash, err := verifyImage(manifest, imagePath)
	if err != nil {
		return attachResult{}, err
	}
	return attachResult{
		Schema:                "scai-remastered-attach-v1",
		ManifestVersion:       manifest.Version,
		ClientSHA256:          hash,
		PID:                   pid,
		WindowHandle:          window,
		ProcessImage:          imagePath,
		VersionLockedAttach:   true,
		ReadGameStateProven:   false,
		IssueCommandsProven:   false,
		MultiplayerSyncProven: false,
	}, nil
}

func main() {
	manifestPath := flag.String("manifest", "", "exact client build manifest")
	processID := flag.Uint("pid", 0, "running StarCraft PID")
	flag.Parse()
	if *manifestPath == "" || *processID == 0 || *processID > math.MaxUint32 {
		fmt.Fprintln(os.Stderr, "usage: remastered-adapter -manifest <path> -pid <pid>")
		os.Exit(2)
	}
	manifest, err := loadManifest(*manifestPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	result, err := attach(uint32(*processID), manifest)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
